# src\logger.py
import datetime
import pathlib
import sys

LOG_FILE = pathlib.Path(__file__).resolve().parents[1] / "data" / "audit.log"

def log_event(command: str, result: str, tool_name: str | None = None, permission: str | None = None) -> None:
    """Append a single line to the audit log."""
    timestamp = datetime.datetime.now().isoformat(timespec='seconds')
    tool_info = f" | TOOL: {tool_name}" if tool_name else ""
    perm_info = f" | PERMISSION: {permission}" if permission else ""
    line = f"[{timestamp}] CMD: {command!r}{tool_info}{perm_info} -> RESULT: {result}\n"
    # Ensure the data folder exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)
    # Also echo to console for immediate feedback
    print(line, end="")
