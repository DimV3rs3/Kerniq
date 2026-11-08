"""Host system capabilities for model recommendation."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from Kerniq.sandbox.proc import hidden_run


@dataclass
class SystemInfo:
    os: str
    os_release: str
    arch: str
    cpu_count: int
    memory_total_gb: Optional[float]
    memory_available_gb: Optional[float]
    vram_total_gb: Optional[float]
    python_version: str
    has_gpu_hint: bool
    notes: List[str]
    vram_used_gb: Optional[float] = None
    gpu_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _windows_memory() -> tuple[Optional[float], Optional[float], List[str]]:
    notes: List[str] = []
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total = round(stat.ullTotalPhys / (1024**3), 2)
            avail = round(stat.ullAvailPhys / (1024**3), 2)
            return total, avail, notes
        notes.append("GlobalMemoryStatusEx failed")
    except Exception as e:
        notes.append(f"windows mem: {e}")
    return None, None, notes


def _linux_memory() -> tuple[Optional[float], Optional[float], List[str]]:
    notes: List[str] = []
    mem_total = None
    mem_avail = None
    try:
        if os.path.exists("/proc/meminfo"):
            data = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        data[key] = int(val)
            if "MemTotal" in data:
                mem_total = round(data["MemTotal"] / (1024 * 1024), 2)
            if "MemAvailable" in data:
                mem_avail = round(data["MemAvailable"] / (1024 * 1024), 2)
    except Exception as e:
        notes.append(f"meminfo: {e}")
    return mem_total, mem_avail, notes


def _nvidia_smi_bin() -> Optional[str]:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    if os.name != "nt":
        return None
    for candidate in (
        r"C:\Windows\System32\nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def parse_nvidia_query(text: str) -> tuple[Optional[float], Optional[float], str]:
    """CSV rows: name, total MiB, used MiB."""
    total = used = 0
    names: List[str] = []
    seen = False
    for line in (text or "").splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            continue
        numbers = []
        label = ""
        for part in parts:
            token = part.split()[0] if part else ""
            if token.replace(".", "", 1).isdigit():
                numbers.append(float(token))
            elif part and not label:
                label = part
        if len(numbers) < 1:
            continue
        seen = True
        total += numbers[0]
        if len(numbers) > 1:
            used += numbers[1]
        if label:
            names.append(label)
    if not seen:
        return None, None, ""
    return round(total / 1024.0, 2), round(used / 1024.0, 2), ", ".join(names)


def _nvidia_gpu() -> tuple[Optional[float], Optional[float], str, List[str]]:
    notes: List[str] = []
    binary = _nvidia_smi_bin()
    if not binary:
        return None, None, "", notes
    try:
        out = hidden_run(
            [binary, "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
            timeout=4,
            text=True,
            stderr=subprocess.DEVNULL,
            check=False,
        ).stdout
    except Exception as exc:
        notes.append(f"nvidia-smi failed: {exc}")
        return None, None, "", notes
    total, used, name = parse_nvidia_query(out or "")
    if total is None:
        notes.append("nvidia-smi returned no VRAM figure")
        return None, None, "", notes
    notes.append(f"VRAM about {total} GB from nvidia-smi" + (f" ({name})" if name else "") + ".")
    return total, used, name, notes


def _drm_sysfs() -> tuple[Optional[float], Optional[float], str, List[str]]:
    """AMD amdgpu and Intel discrete cards expose VRAM under /sys/class/drm."""
    notes: List[str] = []
    root = "/sys/class/drm"
    if not os.path.isdir(root):
        return None, None, "", notes
    total = used = 0
    found = False
    names: List[str] = []
    for card in sorted(os.listdir(root)):
        if not card.startswith("card") or not card[4:].isdigit():
            continue
        device = os.path.join(root, card, "device")
        paths = [
            os.path.join(device, "mem_info_vram_total"),
            os.path.join(device, "tile0", "vram", "physical_vram_size_bytes"),
            os.path.join(device, "tile1", "vram", "physical_vram_size_bytes"),
        ]
        for path in paths:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    total += int(handle.read().strip() or "0")
                found = True
            except (OSError, ValueError):
                continue
            used_path = path.replace("mem_info_vram_total", "mem_info_vram_used")
            if used_path != path and os.path.isfile(used_path):
                try:
                    with open(used_path, "r", encoding="utf-8") as handle:
                        used += int(handle.read().strip() or "0")
                except (OSError, ValueError):
                    pass
            break
        vendor = os.path.join(device, "vendor")
        if os.path.isfile(vendor):
            try:
                with open(vendor, "r", encoding="utf-8") as handle:
                    code = handle.read().strip().lower()
                names.append({"0x1002": "AMD", "0x8086": "Intel", "0x10de": "NVIDIA"}.get(code, code))
            except OSError:
                pass
    if not found or total <= 0:
        return None, None, "", notes
    total_gb = round(total / (1024 ** 3), 2)
    used_gb = round(used / (1024 ** 3), 2) if used else None
    name = ", ".join(dict.fromkeys(names))
    notes.append(f"VRAM about {total_gb} GB from the graphics driver" + (f" ({name})" if name else "") + ".")
    return total_gb, used_gb, name, notes


def parse_windows_vram_rows(text: str) -> tuple[Optional[float], str]:
    """Lines of `name|bytes` from the Windows display-class registry."""
    total = 0
    names: List[str] = []
    for line in (text or "").splitlines():
        if "|" not in line:
            continue
        label, raw = line.split("|", 1)
        token = raw.strip().split()[0] if raw.strip() else ""
        if not token.isdigit():
            continue
        size = int(token)
        if size <= 0:
            continue
        total += size
        if label.strip():
            names.append(label.strip())
    if total <= 0:
        return None, ""
    return round(total / (1024 ** 3), 2), ", ".join(names)


def _windows_registry_vram() -> tuple[Optional[float], str, List[str]]:
    notes: List[str] = []
    if platform.system() != "Windows":
        return None, "", notes
    script = (
        "Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}' "
        "-ErrorAction SilentlyContinue | ForEach-Object { "
        "$p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue; "
        "if ($p.qwMemorySize) { Write-Output ($p.DriverDesc + '|' + $p.qwMemorySize) } }"
    )
    try:
        out = hidden_run(
            ["powershell", "-NoProfile", "-Command", script],
            timeout=8,
            text=True,
            stderr=subprocess.DEVNULL,
            check=False,
        ).stdout
    except Exception as exc:
        notes.append(f"Windows GPU memory lookup failed: {exc}")
        return None, "", notes
    total, name = parse_windows_vram_rows(out or "")
    if total is None:
        return None, "", notes
    notes.append(f"VRAM about {total} GB from the Windows display driver" + (f" ({name})" if name else "") + ".")
    return total, name, notes


def measure_gpu() -> tuple[Optional[float], Optional[float], str, List[str]]:
    """NVIDIA first, then AMD/Intel sysfs, then the Windows driver record."""
    total, used, name, notes = _nvidia_gpu()
    if total is not None:
        return total, used, name, notes
    total, used, name, extra = _drm_sysfs()
    notes.extend(extra)
    if total is not None:
        return total, used, name, notes
    total, name, extra = _windows_registry_vram()
    notes.extend(extra)
    if total is not None:
        return total, None, name, notes
    notes.append("No measured VRAM. NVIDIA, AMD, and Intel were checked. Do not assume a model fits.")
    return None, None, "", notes


def _nvidia_vram_gb() -> tuple[Optional[float], List[str]]:
    """Read total GPU memory. This is not a promise that a model fits."""
    notes: List[str] = []
    if not shutil.which("nvidia-smi"):
        return None, notes
    try:
        out = hidden_run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            timeout=4,
            text=True,
            stderr=subprocess.DEVNULL,
            check=True,
        ).stdout
    except Exception as exc:
        notes.append(f"nvidia-smi failed: {exc}")
        return None, notes
    if not out:
        notes.append("nvidia-smi returned no output")
        return None, notes
    mib = []
    for line in out.splitlines():
        token = line.strip().split()[0] if line.strip() else ""
        if token.isdigit():
            mib.append(int(token))
    if not mib:
        notes.append("nvidia-smi returned no VRAM figure")
        return None, notes
    total = round(sum(mib) / 1024, 2)
    notes.append(
        f"VRAM total about {total} GB from nvidia-smi (sum of GPUs). "
        "This does not mean a model will fit in GPU memory."
    )
    return total, notes


def collect_system_info() -> SystemInfo:
    notes: List[str] = []
    mem_total = None
    mem_avail = None

    system = platform.system()
    if system == "Windows":
        mem_total, mem_avail, n = _windows_memory()
        notes.extend(n)
    else:
        mem_total, mem_avail, n = _linux_memory()
        notes.extend(n)

    has_gpu = False
    vram_gb, vram_used, gpu_name, vram_notes = measure_gpu()
    notes.extend(vram_notes)
    if vram_gb is not None or gpu_name:
        has_gpu = True

    return SystemInfo(
        os=system,
        os_release=platform.release(),
        arch=platform.machine(),
        cpu_count=os.cpu_count() or 1,
        memory_total_gb=mem_total,
        memory_available_gb=mem_avail,
        vram_total_gb=vram_gb,
        python_version=platform.python_version(),
        has_gpu_hint=has_gpu,
        notes=notes,
        vram_used_gb=vram_used,
        gpu_name=gpu_name,
    )


def recommend_for_lm_studio(
    system: SystemInfo,
    models: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    recs: List[str] = []
    mem = system.memory_total_gb

    if mem is None:
        recs.append("RAM unknown (estimate only): use 3–7B Q4 until RAM is measured.")
        size_hint = "3B-7B"
    elif mem < 8:
        recs.append("Low RAM (<8 GB): prefer 1–3B quantized models (Q4/Q5).")
        size_hint = "1B-3B"
    elif mem < 16:
        recs.append("8–16 GB RAM: 3–7B Q4/Q5 models are a practical default.")
        size_hint = "3B-7B"
    elif mem < 32:
        recs.append("16–32 GB RAM: 7–13B models, or 13–20B heavily quantized.")
        size_hint = "7B-13B"
    else:
        recs.append("32+ GB RAM: larger models (13B–34B) possible depending on GPU.")
        size_hint = "13B+"

    if system.vram_total_gb:
        recs.append(
            f"Measured VRAM is about {system.vram_total_gb} GB. "
            "That is not a guarantee the selected model fits on the GPU."
        )
    elif system.has_gpu_hint:
        recs.append("GPU hint only: VRAM was not measured, so GPU fit is unknown.")
    else:
        recs.append("No clear GPU and no VRAM reading. Expect CPU inference and keep context modest.")

    recs.append(f"CPU cores: {system.cpu_count}. Parallel tool calls stay sequential.")
    preferred_model = None
    if models:
        keywords = {
            "1B-3B": ["1b", "2b", "3b", "phi", "tiny", "mini"],
            "3B-7B": ["3b", "7b", "llama", "mistral", "qwen"],
            "7B-13B": ["7b", "8b", "9b", "13b", "12b"],
            "13B+": ["13b", "14b", "20b", "30b", "34b", "70b"],
        }
        keys = keywords.get(size_hint, [])
        for m in models:
            mid = str(m.get("id") or m.get("name") or "").lower()
            if any(k in mid for k in keys):
                preferred_model = m.get("id") or m.get("name")
                break
        if preferred_model is None and models:
            preferred_model = models[0].get("id") or models[0].get("name")

    return {
        "system": system.to_dict(),
        "size_hint": size_hint,
        "preferred_model": preferred_model,
        "recommendations": recs,
        "models_seen": len(models or []),
    }
