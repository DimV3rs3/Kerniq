"""Host system capabilities for model recommendation."""

from __future__ import annotations

import os
import platform
import shutil
import struct
import ctypes
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class SystemInfo:
    os: str
    os_release: str
    arch: str
    cpu_count: int
    memory_total_gb: Optional[float]
    memory_available_gb: Optional[float]
    python_version: str
    has_gpu_hint: bool
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _windows_memory() -> tuple[Optional[float], Optional[float], List[str]]:
    notes: List[str] = []
    try:
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
    try:
        if shutil.which("nvidia-smi"):
            has_gpu = True
            notes.append("nvidia-smi present")
        elif os.path.exists("/dev/nvidia0"):
            has_gpu = True
    except Exception:
        pass

    return SystemInfo(
        os=system,
        os_release=platform.release(),
        arch=platform.machine(),
        cpu_count=os.cpu_count() or 1,
        memory_total_gb=mem_total,
        memory_available_gb=mem_avail,
        python_version=platform.python_version(),
        has_gpu_hint=has_gpu,
        notes=notes,
    )


def recommend_for_lm_studio(
    system: SystemInfo,
    models: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    recs: List[str] = []
    mem = system.memory_total_gb

    if mem is None:
        recs.append("RAM unknown: use 3–7B Q4 as a safe default until measured.")
        size_hint = "3B-7B"
        mem = 16.0
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

    if system.has_gpu_hint:
        recs.append("GPU detected (hint): enable GPU offload in LM Studio for speed.")
    else:
        recs.append("No clear GPU: expect slower CPU inference; keep context modest.")

    recs.append(f"CPU cores: {system.cpu_count}. Parallel tool calls stay sequential in v0.1.")
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
