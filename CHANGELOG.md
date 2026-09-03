# SPIDY Changelog

All notable changes to the SPIDY project will be documented in this file.

## [Phase 3 - Read-Only Filesystem] - 2026-09-02

### Added
- **4 new tool plugins** for inspecting the filesystem safely:
  - `find_files` — Search for files by name or glob pattern within allowed directories.
  - `file_metadata` — Get metadata (size, type, created/modified dates, path) about a file.
  - `read_file` — Read text file contents with safety limits (500 lines, 50 KB, binary blocking).
  - `search_contents` — Perform grep-like text search inside files with line limits and match caps.
- **Security**: All Phase 3 tools inherit strict security, ensuring read-only operations, traversal blocking, and limitation to `ALLOWED_ROOTS`.
- **Test suite**: Added `tests/test_phase3_tools.py` covering all new tools, intent routing, and security.

### Fixed
- **Filesystem containment**: Normalized allowed-root checks now use path-aware containment and preserve Windows case-insensitive behavior.
- **Symlink safety**: File discovery and content searching exclude file symlinks whose targets resolve outside an allowed root.
- **Search limits**: Text searches now enforce the documented 1,000-match maximum, including when a single file contains many matches, and skip extensionless binary content.

## [Phase 2 - Multiple Safe Tools] - 2026-09-01

### Added
- **Plugin-based tool architecture**: `tool_base.py` with `Tool` ABC, `ToolResult` dataclass, and `ToolRegistry` with auto-discovery from `tools/` directory.
- **Intent parser**: `intent_parser.py` with verb stripping, keyword matching, parameter extraction, and synonym support.
- **6 tool plugins** auto-discovered from `src/tools/`:
  - `open_application` — Launch allowlisted Windows applications (Notepad, VS Code, Calculator, File Explorer, Terminal)
  - `get_system_info` — OS, hostname, CPU, RAM, disk usage, uptime via ctypes Win32 API
  - `get_active_window` — Foreground window title and process name via Win32 API
  - `list_directory` — List files/folders with security-enforced allowed roots and path traversal blocking
  - `open_folder` — Open a folder in File Explorer with same security restrictions
  - `window_management` — Minimize, maximize, close, restore windows by title via Win32 API
- **Security**: Allowed-roots enforcement for filesystem tools, path traversal blocking, permission levels (SAFE/CONFIRM)
- **Test suite**: `tests/test_tool_base.py`, `tests/test_intent_parser.py`, `tests/test_tools.py`

### Changed
- Refactored `src/main.py` to be a pure agent loop with zero tool-specific code
- Extracted open_application logic from main.py into `src/tools/open_application.py`

## [Phase 1 - MVP Agent Core] - 2026-09-01

### Added
- Dynamic Windows application path resolution supporting `calc.exe` for Calculator, `code.cmd` / `%LOCALAPPDATA%` for VS Code, `powershell.exe` / `wt.exe` for Terminal, `explorer.exe` for File Explorer, and `notepad.exe` for Notepad.
- Flexible natural language intent parsing with support for aliases (`calc`, `code`, `powershell`, `vs code`, `vscode`, `explorer`) and action verbs (`open`, `launch`, `start`, `run`).
- Structured tool registry with tool permissions (`CONFIRM` level requirement for application launching).
- Application-enforced security allowlist preventing execution of unauthorized binaries (e.g. `chrome`, `malware.exe`).
- Structured audit logging formatting `[TIMESTAMP] CMD: 'command' | TOOL: tool_name | PERMISSION: status -> RESULT: result` appended to `data/audit.log`.
- Unit tests (`src/test_main.py`), function tests (`test_functions.py`), and interactive subprocess tests (`test_interaction.py`) with 100% pass rate.

### Fixed
- Resolved `FileNotFoundError` issues for Calculator, VS Code, and Terminal launching on Windows.
