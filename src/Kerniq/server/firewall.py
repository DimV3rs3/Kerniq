"""Which addresses a remote computer can use, and whether the firewall is in the way."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from typing import Iterable


def _private(ip: str) -> bool:
    text = str(ip or "")
    if text.startswith("10.") or text.startswith("192.168."):
        return True
    if text.startswith("172."):
        try:
            second = int(text.split(".")[1])
        except (IndexError, ValueError):
            return False
        return 16 <= second <= 31
    return False


def lan_ipv4s() -> list[str]:
    """Every non-loopback IPv4 on this machine. Private LAN addresses come first.

    The route toward 8.8.8.8 is included, but it is not the only address.
    A VPN or a container bridge must not hide the address a desktop can open.
    """
    found: list[str] = []

    def add(ip: str) -> None:
        text = str(ip or "").strip()
        if not text or text.startswith("127.") or text == "0.0.0.0" or text in found:
            return
        if ":" in text:
            return
        found.append(text)

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            add(probe.getsockname()[0])
        finally:
            probe.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(None, 0, socket.AF_INET, socket.SOCK_DGRAM):
            add(info[4][0])
    except Exception:
        pass
    found.sort(key=lambda item: (not _private(item), item))
    return found


def try_open_port(port: int) -> str:
    """Allow inbound TCP when this process is allowed to change the firewall.

    Returns a short note. An empty string means nothing was changed and no
    command is required. A ``sudo ...`` string means the operator must run it.
    """
    number = int(port)
    if number < 1 or number > 65535:
        return ""
    if os.name == "nt":
        if not shutil.which("netsh"):
            return ""
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name=Kerniq {number}", "dir=in", "action=allow",
            "protocol=TCP", f"localport={number}",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        except Exception:
            return "Windows Firewall may still block this port. Allow TCP " + str(number) + "."
        if result.returncode == 0:
            return ""
        return "Windows Firewall may still block this port. Allow inbound TCP " + str(number) + "."
    if shutil.which("ufw"):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            try:
                result = subprocess.run(
                    ["ufw", "allow", f"{number}/tcp"],
                    capture_output=True, text=True, timeout=20, check=False,
                )
            except Exception:
                result = None
            if result is not None and result.returncode == 0:
                return ""
        return f"sudo ufw allow {number}/tcp"
    if shutil.which("firewall-cmd"):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            try:
                result = subprocess.run(
                    ["firewall-cmd", f"--add-port={number}/tcp"],
                    capture_output=True, text=True, timeout=20, check=False,
                )
            except Exception:
                result = None
            if result is not None and result.returncode == 0:
                return ""
        return f"sudo firewall-cmd --add-port={number}/tcp"
    return ""


def listen_lines(host: str, port: int, *, firewall_note: str = "") -> list[str]:
    number = int(port)
    bind = str(host or "127.0.0.1")
    lines = [f"Web UI listening on {bind}:{number}"]
    if bind not in ("0.0.0.0", "::"):
        lines.append(f"Web UI: http://{bind}:{number}")
        lines.append("This address is only reachable from this computer.")
        return lines
    ips = lan_ipv4s()
    if not ips:
        lines.append(f"Web UI (local): http://127.0.0.1:{number}")
    for ip in ips:
        lines.append(f"Web UI: http://{ip}:{number}")
    lines.append(f"Web UI (local): http://127.0.0.1:{number}")
    lines.append(
        "From another computer, including a Windows PC, open one of the Web UI addresses above "
        "with the port. 127.0.0.1 is this machine, not the other one."
    )
    if ips and all(_private(ip) for ip in ips):
        lines.append(
            "These addresses are private. A PC that is not on this same network cannot open them. "
            "Use the server's public address, and allow TCP "
            + str(number)
            + " in the host firewall and in the cloud security group."
        )
    if firewall_note:
        lines.append("If the page does not load, allow the port: " + firewall_note)
        lines.append("On a VPS, also allow that TCP port in the cloud security group.")
    lines.append(
        "If the browser uses a proxy, such as 127.0.0.1:10809, add this server address "
        "to the proxy bypass list. The proxy is on that computer, so the browser never "
        "reaches here. A port test can succeed while the page stays blank."
    )
    return lines


def format_lines(lines: Iterable[str]) -> str:
    return "\n".join(str(item) for item in lines)
