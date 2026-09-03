# src/tools/system_info.py
"""
Tool: System Information

Returns OS version, hostname, CPU count, total RAM, disk usage, and uptime.
Uses only stdlib — no external dependencies.
"""

import os
import platform
import sys
import ctypes
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_SAFE


def _get_total_ram_gb() -> str:
    """Get total physical RAM in GB using Win32 API."""
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

        mem_status = MEMORYSTATUSEX()
        mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))

        total_gb = mem_status.ullTotalPhys / (1024 ** 3)
        avail_gb = mem_status.ullAvailPhys / (1024 ** 3)
        used_pct = mem_status.dwMemoryLoad
        return f"{total_gb:.1f} GB total, {avail_gb:.1f} GB available ({used_pct}% used)"
    except Exception:
        return "unknown"


def _get_uptime() -> str:
    """Get system uptime using Win32 API."""
    try:
        tick_count = ctypes.windll.kernel32.GetTickCount64()
        seconds = tick_count // 1000
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days}d {hours}h {minutes}m"
        return f"{hours}h {minutes}m"
    except Exception:
        return "unknown"


def _get_disk_usage() -> str:
    """Get disk usage for the system drive using Win32 API."""
    try:
        free_bytes = ctypes.c_ulonglong(0)
        total_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            "C:\\",
            None,
            ctypes.byref(total_bytes),
            ctypes.byref(free_bytes)
        )
        total_gb = total_bytes.value / (1024 ** 3)
        free_gb = free_bytes.value / (1024 ** 3)
        used_gb = total_gb - free_gb
        used_pct = (used_gb / total_gb) * 100 if total_gb > 0 else 0
        return f"C: {total_gb:.1f} GB total, {free_gb:.1f} GB free ({used_pct:.0f}% used)"
    except Exception:
        return "unknown"


class SystemInfoTool(Tool):
    """Returns system information: OS, hostname, CPU, RAM, disk, uptime."""

    @property
    def name(self) -> str:
        return "get_system_info"

    @property
    def description(self) -> str:
        return "Get system information including OS, hostname, CPU, RAM, disk usage, and uptime"

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "system info", "system information",
            "my computer", "computer info",
            "specs", "hardware",
            "system details", "pc info",
            "pc specs", "my pc specs",
        ]

    def execute(self, **params) -> ToolResult:
        try:
            info = {
                "os": f"{platform.system()} {platform.release()} ({platform.version()})",
                "hostname": platform.node(),
                "cpu": f"{platform.processor()} ({os.cpu_count()} cores)",
                "ram": _get_total_ram_gb(),
                "disk": _get_disk_usage(),
                "uptime": _get_uptime(),
                "python": platform.python_version(),
                "architecture": platform.machine()
            }

            lines = [
                f"  OS:           {info['os']}",
                f"  Hostname:     {info['hostname']}",
                f"  CPU:          {info['cpu']}",
                f"  RAM:          {info['ram']}",
                f"  Disk:         {info['disk']}",
                f"  Uptime:       {info['uptime']}",
                f"  Architecture: {info['architecture']}",
                f"  Python:       {info['python']}"
            ]

            return ToolResult(
                success=True,
                message="System Information:\n" + "\n".join(lines),
                data=info
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Error retrieving system info: {e}")
