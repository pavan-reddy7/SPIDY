# SPIDY Development Plan

## Phase 0 — Planning & Foundation

Goal:

Establish the architecture before building advanced capabilities.

Tasks:

- Define product vision
- Define security model
- Define tool architecture
- Define project structure
- Configure Python environment
- Configure Git
- Create documentation
- Establish development workflow

Deliverables:

- PRODUCT_VISION.md
- DEVELOPMENT_PLAN.md
- CLAUDE.md
- README.md
- Git repository
- Python virtual environment

Status:
COMPLETE


---

# Phase 1 — MVP Agent Core

Goal:

Build the smallest real SPIDY.

SPIDY should accept a natural-language text request and execute ONE safe computer action.

Example:

"Open Notepad."

Architecture:

User
↓
SPIDY
↓
LLM
↓
Tool selection
↓
Permission check
↓
Tool execution
↓
Result
↓
SPIDY response

First tool:

open_application

Initial allowlist:

- Notepad
- VS Code
- Calculator
- File Explorer
- Terminal

Requirements:

- Structured tool interface
- Tool registry
- Agent loop
- Permission policy
- Structured logging
- Error handling
- Unit tests

Do NOT implement yet:

- Voice
- RAG
- Browser automation
- Screen understanding
- Long-term memory
- Autonomous multi-step workflows

Success example:

User:
"Open VS Code."

SPIDY:
"VS Code is open."

Status:
COMPLETE


---

# Phase 2 — Multiple Safe Tools

Goal:

Prove that the tool architecture is extensible.

Add tools such as:

- Open application
- Get system information
- Get current active window
- List allowed directories
- Open folder
- Basic window management

Requirements:

- Tool registry
- Consistent schemas
- Consistent permissions
- Tool execution results
- Logging
- Tests

Success:

Adding a new tool should not require rewriting the agent core.

Status:
COMPLETE

---

# Phase 3 — Read-Only Filesystem

Goal:

Allow SPIDY to inspect the user's filesystem safely.

Capabilities:

- List directories
- Find files
- Search filenames
- Get file metadata
- Read text files
- Search text contents

Security:

- Restrict filesystem roots
- Prevent path traversal
- Do not modify/delete anything
- Handle permissions errors

Example:

"Find my Python files in C:\Projects."

Status:
COMPLETE


---

# Phase 4 — Memory & Context

Goal:

Give SPIDY continuity.

Implement:

### Short-term memory

- Conversation history
- Recent tool results
- Current task context

### Persistent memory

- Explicit user memories
- Project locations
- Preferences
- Named entities

Requirements:

- Local storage
- Search
- Delete memory
- Inspect memory
- Do not silently store sensitive information

Example:

"Remember that SPIDY's source code is in C:\SPIDY."

Status:
COMPLETE


---

# Phase 5 — Voice

Goal:

Add natural voice interaction.

Components:

Speech
↓
Speech-to-text
↓
SPIDY
↓
Tool execution
↓
Text response
↓
Text-to-speech

Features:

- Push-to-talk
- Speech-to-text
- Text-to-speech
- Interrupt/cancel
- Text fallback

Wake word can be added later.

Voice should NOT change the underlying tool/security architecture.

Status:
COMPLETE


---

# Phase 6 — Write Operations & Permission Escalation

Goal:

Allow controlled modifications.

Add:

- Create file
- Edit file
- Rename file
- Move file
- Create directory
- Delete file

Permission levels:

SAFE
CONFIRM
HIGH RISK
BLOCKED

Examples:

Creating a file:
→ confirmation depending on policy

Deleting a file:
→ mandatory confirmation

System modifications:
→ high-risk confirmation or blocked

Every action must be logged.

Status:
COMPLETE

---

# Phase 7 — Browser Automation

Goal:

Allow SPIDY to interact with the web.

Capabilities:

- Open browser
- Navigate
- Search
- Read pages
- Click
- Fill forms
- Download files

Security:

- Isolated browser profile where practical
- Network restrictions where practical
- Explicit confirmation for sensitive external actions
- Never expose credentials unnecessarily

Example:

"Search for the latest Python release."
Status:
COMPLETE


---

# Phase 8 — Personal RAG

Goal:

Allow SPIDY to answer questions using personal documents.

Pipeline:

Documents
↓
Parser
↓
Text extraction
↓
Chunking
↓
Embeddings
↓
Vector database
↓
Retrieval
↓
LLM
↓
Grounded answer

Support initially:

- PDF
- Markdown
- TXT
- DOCX
- XLSX

Features:

- Document indexing
- Incremental updates
- Search
- Source references
- Delete/re-index documents

Example:

"What does my SPIDY documentation say about permissions?"

Status:
COMPLETE

---

# Phase 9 — Screen Understanding

Goal:

Allow SPIDY to understand the visible Windows desktop.

Capabilities:

- Screenshot capture
- OCR
- Screen description
- UI element detection
- Active-window identification
- Basic visual grounding

Example:

"What is on my screen?"

Later:

"Find the Submit button."

Status:
COMPLETE


---

# Phase 10 — Multi-Step Computer Use

Goal:

Turn SPIDY into a reliable computer-use agent.

Architecture:

User goal
↓
Planner (task_planner.py)
↓
Task graph (Plan + TaskStep list)
↓
Tool execution (task_runner.py)
↓
Observation (result_key → context)
↓
Verification (VERIFY step type)
↓
Next step / BRANCH
↓
Retry + Fallback Recovery
↓
Progress reporting (callback)
↓
Completion (RunReport)

Capabilities:

- Multi-step planning (9 goal templates + generic fallback)
- Sequential actions (ordered TaskStep list)
- Conditional branches (BRANCH step type)
- Loops (LOOP step type with inner steps)
- Retry (configurable max_retries per step)
- Error recovery (fallback tool + continue-on-failure)
- Progress reporting (progress_callback → console / queue)
- Pause/resume (threading.Event)
- Cancellation (threading.Event, graceful mid-wait cancel)
- Background tasks (TaskManager.submit → daemon thread)
- Task lifecycle management (status / report / drain_progress / cleanup)

New files:

- src/task_planner.py  — goal → Plan + TaskStep list (9 templates)
- src/task_runner.py   — executes plans; retry, verify, branch, loop, wait
- src/task_manager.py  — singleton; background threads, pause/cancel/status
- src/tools/run_task.py    — tool plugin (CONFIRM): multi-step autonomous task
- src/tools/task_status.py — tool plugin (SAFE): task lifecycle management

New tools (38 total):

- run_task    — Execute a multi-step goal autonomously
- task_status — Check, cancel, pause, or resume background tasks

Tests:

- tests/test_phase10_tasks.py — 78 tests; all passing

Example:

"Prepare my project for tomorrow's demo."

SPIDY:

1. List project structure
2. Find test files
3. Describe current screen
4. Search for TODO items
5. Take screenshot
6. Get system info
7. Verify all steps complete

Status:
COMPLETE


---

# Phase 11 — Reliability, Security & Production Polish

Goal:

Make SPIDY dependable rather than just impressive in demos.

Tasks:

- Comprehensive testing
- Security testing
- Permission testing
- Failure injection
- Tool timeout handling
- Cancellation
- Recovery
- Audit log integrity
- Performance monitoring
- UI polish
- Packaging
- Installation process
- Configuration management
- Documentation
- Demo scenarios

Final target:

SPIDY should be able to complete useful tasks reliably while keeping the user informed and in control.


---

# Development Rules

1. Never skip phases without a clear reason.
2. Never implement advanced features prematurely.
3. Never trust the LLM as a security boundary.
4. Validate all tool inputs.
5. Restrict filesystem access.
6. Use allowlists wherever possible.
7. Require confirmation for risky actions.
8. Log meaningful actions.
9. Write tests for important functionality.
10. Prefer APIs and structured automation over screen-coordinate automation.
11. Never store secrets in Git.
12. Never commit `.env`.
13. Keep dependencies minimal.
14. Update this document after completing each phase.
15. Update CHANGELOG.md after significant changes.
16. Make Git commits at stable milestones.
17. Do not rewrite working architecture without justification.
18. Preserve backward compatibility where practical.