# SPIDY Changelog

All notable changes to the SPIDY project will be documented in this file.

## [Phase V2.2 - Conversational LLM Brain & Function Calling] - 2026-10-28

### Added
- **Conversational LLM Brain** (`src/llm_brain.py`):
  - Integrates Google Gemini (`gemini-3.5-flash-lite`, sub-1.5s latency) for intelligent conversational reasoning.
  - Multi-persona system prompts (J.A.R.V.I.S., F.R.I.D.A.Y., E.D.I.T.H.) addressing user respectfully ("Sir", "Boss").
  - Autonomous Function Calling: Gemini dynamically evaluates intent and chooses the right computer tool from all 38 registered tools.
  - Conversational context with natural spoken summary feedback.
  - Security Enforcement: Every LLM tool call validates SPIDY permission policies (`SAFE`, `CONFIRM`, `HIGH_RISK`, `BLOCKED`).
  - Graceful Hybrid Fallback: Seamlessly falls back to deterministic regex parser (`parse_intent`) if offline or unconfigured.
- **Dynamic Tool Schema Generator** (`src/tool_schemas.py`):
  - Auto-converts SPIDY tools from `ToolRegistry` into `google.genai` `FunctionDeclaration` schemas with parameter hints.
  - Adapts flexible parameter naming (`app_name`, `path`, `query`, `goal` -> canonical `target`).
- **Core Loop Upgrades**:
  - `src/voice_loop.py` and `src/main.py` upgraded to use `LLMBrain` for hands-free natural voice and CLI interactions.
- **Test Suite**:
  - `tests/test_v2_llm_brain.py`: 7 comprehensive unit tests covering tool schema building, parameter adaptation, persona prompts, mocked function calling execution, permission enforcement, and deterministic fallback. 100% passing.


## [Phase V2.1 - Neural Voice Engine & Personality Synthesis] - 2026-10-28

### Added
- **Neural Voice Engine** (`src/voice_engine.py`):
  - High-fidelity streaming speech synthesis powered by `edge-tts` (zero API key needed).
  - Personality profiles with tailored voices and honorifics:
    - **JARVIS**: `en-GB-RyanNeural` (calm, British conversational assistant, "Sir").
    - **FRIDAY**: `en-IE-EmilyNeural` (crisp, tactical Irish assistant, "Boss").
    - **EDITH**: `en-US-AriaNeural` (tactical system assistant).
    - **SPIDY**: `en-US-GuyNeural` (friendly modern assistant).
  - Seamless in-memory MP3 decoding via `miniaudio` and playback via `sounddevice`.
  - Automatic fallback to offline `pyttsx3` when disconnected or during network delays.
  - Disk caching (`data/audio_cache/`) with MD5 hashing for instant zero-latency speech repetition.
  - Speech sanitizer that strips markdown, resolves paths to friendly names, and condenses verbosity for natural conversation.
  - Dynamic runtime personality switching (e.g., "switch to friday", "switch to jarvis").
- **Futuristic Audio Cues** (`src/audio_cues.py`):
  - Pure harmonic synthesis of sci-fi sound effects:
    - `wake`: Ascending dual-tone Stark chime (587Hz -> 880Hz).
    - `confirm`: Crisp tactical blip (1046Hz -> 1318Hz).
    - `done`: Harmonic success chord (C-E-G triad).
    - `error`: Subdued low warning tone.
    - `listening`: Soft prompt ping.
  - Thread-safe, non-blocking asynchronous playback with zero external asset dependencies.
- **Voice Loop Integration** (`src/voice_loop.py`):
  - Upgraded voice loop to use `voice_engine` and `audio_cues`.
  - Audio cue triggers on wake, confirmation prompts, tool execution success, and errors.
- **Test Suite**:
  - `tests/test_v2_voice.py`: 10 comprehensive unit tests covering cue synthesis, WAV integrity, personality profiles, text sanitization, cache indexing, and voice confirmation. 100% passing.


## [Hands-Free Voice Mode & Universal Command Matching] - 2026-10-25

### Added
- **100% Hands-Free Voice Assistant Mode**:
  - `src/voice_loop.py` — continuous voice loop with microphone listening, Google Web Speech API recognition, dynamic noise threshold calibration, and pyttsx3 spoken feedback.
  - Hands-free voice confirmation for protected tools (`PERMISSION_CONFIRM` and `PERMISSION_HIGH_RISK`): prompts the user aloud and listens for spoken "yes/no/cancel".
  - Dedicated entrypoint `src/voice_main.py` to start SPIDY completely by voice commands with zero keyboard typing.
  - Voice flag `--voice` and `-v` added to `src/main.py`, as well as `voice` command in console.
- **Universal Flexible Command Matching**:
  - `src/intent_parser.py` upgraded with token-based indexing:
    - Any case: lowercase, UPPERCASE, Title Case, or mixed case (`OPEN BROWSER`, `open browser`, `Open Browser`).
    - With or without underscores, spaces, or hyphens (`speech_to_text`, `speech to text`, `speech-to-text`).
    - Automatic inclusion of canonical tool names and stripped `get_` names.
    - Parameter paths and filenames with underscores (e.g. `read_file C:\path\my_file.py`) preserved intact.
- **Test Suite**: `tests/test_flexible_and_voice.py` — comprehensive unit tests for all variations and voice helpers. All 309 tests passing.

## [Phase 10 - Multi-Step Computer Use] - 2026-10-25

### Added
- **Task Planner**: `src/task_planner.py` — parses natural-language goals into ordered `Plan` / `TaskStep` lists. 9 goal templates (demo, git, screen, files, web, memory, RAG, open-app, generic). Each step supports retry policy, fallback tool, result key for context storage, and condition expressions.
- **Task Runner**: `src/task_runner.py` — executes plans against the ToolRegistry with:
  - **Sequential execution** with per-step progress callbacks
  - **5 step types**: ACTION, VERIFY, BRANCH, LOOP, WAIT
  - **Retry** with configurable `max_retries` and `retry_delay_s` per step
  - **Fallback tool** invoked when all retries are exhausted
  - **Error recovery**: failed steps log and continue (plan does not abort)
  - **VERIFY** steps evaluate Python expressions in shared context; stop plan on failure
  - **BRANCH** steps evaluate conditions and jump to arbitrary step indices
  - **LOOP** steps repeat inner step lists N times
  - **Pause / resume** via `threading.Event` (thread-safe)
  - **Cancellation** via `threading.Event` — graceful mid-wait interrupt
  - **RunReport**: structured result with per-step status, output, retry count, elapsed time
- **Task Manager**: `src/task_manager.py` — module-level singleton managing background task threads:
  - `submit(plan, registry)` — run plan in daemon thread; returns task_id
  - `run_inline(plan, registry)` — synchronous execution for REPL / tests
  - `cancel / pause / resume` — thread-safe task control
  - `status / report / drain_progress` — inspect running and completed tasks
  - `cleanup_done()` — remove finished tasks from memory
- **2 new tool plugins**:
  - `run_task` (CONFIRM) — accepts a natural-language goal, plans it, and executes it autonomously with live progress output. Keywords: `run task`, `execute task`, `multi step task`, etc.
  - `task_status` (SAFE) — list all tasks, show per-task report, cancel / pause / resume by task_id. Keywords: `task status`, `list tasks`, `cancel task`, etc.
- **Test suite**: `tests/test_phase10_tasks.py` — 78 tests across 7 test classes covering planner, runner, manager, tool plugins, intent routing, tool discovery, and end-to-end integration.

### Design Decisions
- **No LLM required for planning**: Rule-based keyword-pattern matching selects deterministic plan templates, keeping planning fast, offline, and predictable.
- **Continue-on-failure recovery**: Failed ACTION steps log and continue rather than aborting the whole plan, maximising the number of steps completed in partial-success scenarios.
- **Shared context dict**: Steps store `result.data` or `result.message` in a per-run context dict keyed by `result_key`; VERIFY and BRANCH steps evaluate expressions against this context.
- **Thread-safe background tasks**: Daemon threads with `threading.Event` primitives avoid blocking the REPL while long-running task sequences execute.
- **38 total tools**: `run_task` + `task_status` added to existing 36.

## [Phase 9 - Screen Understanding] - 2026-10-22


### Added
- **Screen capture engine**: `src/screen_capture.py` — captures full desktop, active window, and arbitrary bounding box regions via Win32 GDI BitBlt and Pillow ImageGrab fallback. Automatic filename generation with microsecond timestamps and auto-cleanup retaining the most recent 50 screenshots in `data/screenshots/`.
- **OCR engine**: `src/ocr_engine.py` — fully local optical character recognition powered by Windows built-in WinRT OCR (`Windows.Media.Ocr` via `winocr`). Provides structured line-level text extraction with bounding boxes, case-insensitive substring search, and text summaries.
- **UI inspector**: `src/ui_inspector.py` — detects and enumerates visible top-level windows (process name, HWND, geometry, z-order) and child UI controls (buttons, text fields, labels, list views, etc.) using ctypes Win32 API. Provides full screen structure representation.
- **4 new tool plugins**:
  - `screenshot` — Capture full desktop or active window and list saved screenshots (`take a screenshot`, `capture screen`, `screenshot window`).
  - `read_screen` — Extract all visible text from the desktop or active window via OCR (`read screen`, `read my screen`, `ocr screen`).
  - `describe_screen` — Overview of open windows, active window, resolution, and visible UI controls (`what is on my screen`, `describe screen`).
  - `find_on_screen` — Locate specific text, buttons, or controls using combined UI inspection and OCR (`find on screen Submit`, `find button OK`).
- **Dependencies**: `Pillow`, `winocr`
- **Test suite**: `tests/test_phase9_screen.py` — 43 tests covering screen capture, OCR engine, UI inspector, tool plugins, intent routing, and security permissions. All 225 test suite tests passing.

### Design Decisions
- **Rock-solid capture**: Win32 GDI BitBlt as primary capture method avoids failures in background and locked sessions.
- **Non-blocking OCR**: ThreadPool execution prevents event-loop collisions with async WinRT operations.
- **Safe permissions**: All 4 screen understanding tools are marked `PERMISSION_SAFE` (read-only desktop inspection).
- **Data privacy**: Screenshots are saved locally only (`data/screenshots/` excluded in `.gitignore`), no network calls.

## [Phase 8 - Personal RAG] - 2026-10-17

### Added
- **Document parsers**: `src/rag_parsers.py` — extracts plain text from TXT, Markdown, PDF (via pypdf), DOCX (via python-docx), and XLSX (via openpyxl). Enforces 10 MB file-size limit.
- **RAG document store**: `src/rag_store.py` — JSON-backed index (`data/rag_index.json`) with document metadata, content-hash deduplication, and chunk storage (`data/rag_chunks/`). Capped at 1,000 documents.
- **RAG engine**: `src/rag_engine.py` — sentence-aware text chunking (2,000 chars, 250 overlap), TF-IDF vectorization via scikit-learn, cosine-similarity search, and incremental indexing pipeline.
- **3 new tool plugins**:
  - `index_documents` — Index files or folders for RAG search (e.g. `index documents C:\SPIDY`)
  - `ask_documents` — Query indexed documents with natural language (e.g. `ask documents what are permissions`)
  - `manage_index` — List, delete, re-index, or clear indexed documents (e.g. `list indexed`, `clear index`)
- **New dependencies**: pypdf, python-docx, openpyxl, scikit-learn (+ numpy, scipy, joblib, lxml)
- **Test suite**: `tests/test_phase8_rag.py` — 41 tests covering parsers, chunking, store CRUD, engine pipeline, tool plugins, integration, and intent routing. 100% pass rate.

### Design Decisions
- **Fully local**: TF-IDF embeddings via scikit-learn — no API keys or network calls needed.
- **Incremental indexing**: Content-hash based — unchanged files are skipped on re-index.
- **Source references**: Every search result cites the source filename and chunk number.
- **Security**: Only files within `ALLOWED_ROOTS` can be indexed. Path traversal blocked. CONFIRM permission for index/delete operations.

## [Phase 4 - Memory & Context] - 2026-09-03

### Added
- **Persistent memory store**: `src/memory_store.py` — JSON-backed local storage (`data/memory.json`) with save, search, list, delete, and clear operations. Auto-categorises memories as `general`, `project`, `preference`, or `entity`. Capped at 500 memories.
- **3 new tool plugins**:
  - `remember` — Store explicit user memories (e.g. `remember that SPIDY is in C:\SPIDY`)
  - `recall` — Search, list, or filter memories by category (e.g. `my memories`, `recall SPIDY`)
  - `forget` — Delete by ID, by text search, or clear all (e.g. `forget everything`)
- **Short-term session memory**: Last 10 interactions tracked in-memory. Type `history` to view.
- **Intent parser enhancement**: Colon-separator support (e.g. `remember this: my name is Pavan`)
- **Test suite**: `tests/test_phase4_memory.py` — 18 tests covering memory store, tools, intents, permissions, and session history.

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
