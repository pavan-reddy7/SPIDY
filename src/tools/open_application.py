# src/tools/open_application.py
"""
Tool: Open Application

Opens an application from the security allowlist.

Supports:
- Hardcoded known applications (Notepad, VS Code, Calculator, File Explorer, Terminal)
- Dynamic discovery of installed applications (Chrome, Edge, Spotify, Discord, Steam, etc.)
- Natural language aliases (Google Chrome, Visual Studio Code, etc.)

Security model:
- Only executable files at known install locations are ever launched.
- The LLM / user cannot cause an arbitrary shell command to execute.
- Discovered apps are resolved from specific known paths only — not from PATH search alone.
"""

import glob
import os
import shutil
import subprocess
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM


# ------------------------------------------------------------------ #
#  Alias map: normalises natural-language names to canonical app keys  #
# ------------------------------------------------------------------ #
ALIAS_MAP: dict[str, str] = {
    # Notepad
    "notepad": "notepad",
    # VS Code
    "vs code": "vscode",
    "vscode": "vscode",
    "code": "vscode",
    "visual studio code": "vscode",
    # Calculator
    "calculator": "calculator",
    "calc": "calculator",
    # File Explorer
    "file explorer": "file_explorer",
    "explorer": "file_explorer",
    "windows explorer": "file_explorer",
    # Terminal
    "terminal": "terminal",
    "powershell": "terminal",
    "cmd": "terminal",
    "command prompt": "terminal",
    # Chrome
    "chrome": "chrome",
    "google chrome": "chrome",
    # Edge
    "edge": "edge",
    "microsoft edge": "edge",
    # Spotify
    "spotify": "spotify",
    # Discord
    "discord": "discord",
    # Steam
    "steam": "steam",
    # WhatsApp
    "whatsapp": "whatsapp",
    "whats app": "whatsapp",
}

# ------------------------------------------------------------------ #
#  Per-app candidate search lists                                      #
#  SECURITY: only specific, well-known install paths are searched.    #
#  Arbitrary user-supplied paths are never executed.                  #
# ------------------------------------------------------------------ #
def _build_candidates() -> dict[str, list[str]]:
    lad = os.path.expandvars("%LOCALAPPDATA%")
    app = os.path.expandvars("%APPDATA%")
    pf  = os.path.expandvars("%PROGRAMFILES%")
    pf86 = os.path.expandvars("%PROGRAMFILES(X86)%")

    return {
        "notepad": ["notepad.exe"],
        "vscode": [
            "code.cmd", "code",
            os.path.join(lad,  r"Programs\Microsoft VS Code\Code.exe"),
            os.path.join(pf,   r"Microsoft VS Code\Code.exe"),
        ],
        "calculator": ["calc.exe"],
        "file_explorer": ["explorer.exe"],
        "terminal": ["powershell.exe", "wt.exe", "cmd.exe"],
        "chrome": [
            os.path.join(pf,   r"Google\Chrome\Application\chrome.exe"),
            os.path.join(pf86, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(lad,  r"Google\Chrome\Application\chrome.exe"),
        ],
        "edge": [
            os.path.join(pf86, r"Microsoft\Edge\Application\msedge.exe"),
            os.path.join(pf,   r"Microsoft\Edge\Application\msedge.exe"),
        ],
        "spotify": [
            os.path.join(app,  r"Spotify\Spotify.exe"),
            os.path.join(lad,  r"Microsoft\WindowsApps\Spotify.exe"),
        ],
        "discord": [
            # Discord installs with a versioned directory; use glob
            *glob.glob(os.path.join(lad, r"Discord\app-*\Discord.exe")),
            os.path.join(lad,  r"Discord\Update.exe"),
        ],
        "steam": [
            os.path.join(pf86, r"Steam\steam.exe"),
            os.path.join(pf,   r"Steam\steam.exe"),
        ],
        "whatsapp": [
            os.path.join(lad,  r"WhatsApp\WhatsApp.exe"),
            os.path.join(app,  r"WhatsApp\WhatsApp.exe"),
            os.path.join(lad,  r"Microsoft\WindowsApps\WhatsApp.exe"),
        ],
    }


# Display names for canonical keys
DISPLAY_NAMES: dict[str, str] = {
    "notepad": "Notepad",
    "vscode": "VS Code",
    "calculator": "Calculator",
    "file_explorer": "File Explorer",
    "terminal": "Terminal",
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "spotify": "Spotify",
    "discord": "Discord",
    "steam": "Steam",
    "whatsapp": "WhatsApp",
}


def _resolve_path(canonical_key: str) -> str | None:
    """
    Resolve the executable path for a canonical app key.
    Tries specific candidate paths only — never arbitrary shell lookup.
    Returns absolute path or None.
    """
    candidates = _build_candidates()
    app_candidates = candidates.get(canonical_key, [])

    for candidate in app_candidates:
        if not candidate:
            continue
        # Absolute path that exists
        if os.path.isabs(candidate) and os.path.isfile(candidate):
            return candidate
        # Relative name - look via shutil.which (safe: returns full path)
        found = shutil.which(candidate)
        if found and os.path.isfile(found):
            return found

    return None


class OpenApplicationTool(Tool):
    """Opens an application by resolving it from known safe install locations."""

    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        return (
            "Open an installed application "
            "(Notepad, VS Code, Calculator, File Explorer, Terminal, "
            "Chrome, Edge, Spotify, Discord, Steam, WhatsApp)"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        # Every alias key is a valid keyword for intent matching
        return sorted(ALIAS_MAP.keys())

    def execute(self, **params) -> ToolResult:
        # Determine what app was requested
        raw = params.get("target", "") or params.get("_keyword", "")
        raw_lower = raw.lower().strip()

        if not raw_lower:
            return ToolResult(
                success=False,
                message="No application specified. Try: open notepad, open chrome, open vs code, etc."
            )

        # Normalise to canonical key
        canonical = ALIAS_MAP.get(raw_lower)
        if canonical is None:
            return ToolResult(
                success=False,
                message=(
                    f"'{raw}' is not in the allowed application list.\n"
                    f"Allowed: {', '.join(sorted(set(DISPLAY_NAMES.values())))}"
                )
            )

        display = DISPLAY_NAMES.get(canonical, canonical.title())

        # Resolve path from known safe locations
        exe_path = _resolve_path(canonical)
        if not exe_path:
            return ToolResult(
                success=False,
                message=f"{display} does not appear to be installed on this system."
            )

        try:
            is_cmd_script = exe_path.lower().endswith((".cmd", ".bat"))
            subprocess.Popen([exe_path], shell=is_cmd_script)
            return ToolResult(
                success=True,
                message=f"{display} is now open.",
                data={"app": display, "exe_path": exe_path}
            )
        except FileNotFoundError:
            return ToolResult(success=False, message=f"Executable not found: {exe_path}")
        except Exception as e:
            return ToolResult(success=False, message=f"Error launching {display}: {e}")
