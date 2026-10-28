# SPIDY Version 2 — Development Plan
## Practical Personal AI Work Assistant (Jarvis-Style Experience)

---

## Overview

SPIDY Version 1 successfully established the foundational computer-use OS:
- **38 safe tools** across filesystem, window management, web browsing, screen OCR, persistent memory, and multi-step task execution.
- **Safety architecture**: Strict allowlists, path containment (`ALLOWED_ROOTS`), and permissions (`SAFE`, `CONFIRM`, `HIGH_RISK`).
- **309 passing tests** verifying deterministic execution.

**SPIDY Version 2** transforms this foundation into a **true personal Jarvis-like companion for everyday personal and professional work**. The goal is not Hollywood fiction or superhero combat, but a seamless, natural, voice-first digital partner that saves hours of daily computer tasks, understands your screen, speaks naturally, and works quietly alongside you.

---

## Architecture Evolution: V1 vs V2

```
V1 (Deterministic Tool Execution):
User Speech/Text ──> Regex Intent Parser ──> Strict Tool Match ──> Windows Action ──> pyttsx3 Robotic Speech

V2 (Conversational Assistant with Sight & Neural Voice):
User Voice ──> Wake Word ("Hey Spidy" / "Jarvis") ──> Neural Whisper / WebSpeech 
     │
     ▼
LLM Brain (Gemini / Claude / Local Ollama) + Conversational Memory + Screen Eyes
     │
     ├─ Natural Chat / Thoughtful Answers
     ├─ Vision Analysis ("Look at my screen")
     └─ Autonomous Function Calling ──> Existing 38 SPIDY Tools ──> Verified Execution
     │
     ▼
Edge-TTS Neural Voice (British 'Ryan' / Irish 'Emily') + Sci-Fi Audio Cues + Minimal Floating HUD
```

---

## Phase V2.1 — Neural Voice & Personality Synthesis

### Goal:
Eliminate the robotic `pyttsx3` speech. Give SPIDY a warm, ultra-clear, natural human voice and conversational persona with subtle audio feedback chimes.

### Tasks:
- Integrate `edge-tts` (100% free, high-speed Microsoft neural voices, no API key required).
  - Voice profiles:
    - **Jarvis style**: `en-GB-RyanNeural` (calm, articulate British assistant)
    - **Friday style**: `en-IE-EmilyNeural` (crisp, tactical Irish assistant)
    - **Custom style**: Configurable in `.env` / settings
- Add local audio cue system (lightweight WAV sound effects for wake, action confirmed, task done, error alert).
- Add natural speech formatting (cleans markdown, code snippets, and paths into concise, natural spoken sentences).
- Non-blocking asynchronous audio playback so UI/CLI never freezes while speaking.

### Deliverables:
- `src/voice_engine.py` — High-fidelity neural voice manager with fallback to offline TTS.
- `src/audio_cues.py` — Subtle sci-fi sound effect generator / player.
- `tests/test_v2_voice.py` — Automated tests for speech generation and queue management.

### Status:
COMPLETE

---

## Phase V2.2 — Conversational LLM Brain & Function Calling

### Goal:
Upgrade from rigid keyword matching (`intent_parser.py`) to an LLM-powered brain. You speak in natural, casual English, and SPIDY understands your intent, chats intelligently, and autonomously calls tools.

### Capabilities:
- Natural language understanding: Understands nuance, slang, compound instructions, and conversational context.
- Function Calling / Tool Selection: Automatically converts SPIDY's 38 tools into standardized tool schemas for the LLM.
- Multi-provider support:
  - Cloud: Google Gemini API (ultra-fast, generous free tier), Claude, or OpenAI.
  - Local/Offline: Ollama (Llama 3.2 / Mistral / Qwen) for 100% private offline work.
- Graceful Hybrid Fallback: If no internet / API key is present, automatically falls back to SPIDY's built-in V1 deterministic regex parser.
- Conversational Context: Remembers previous sentences during a work session without losing track.

### Deliverables:
- `src/llm_brain.py` — LLM interface supporting Gemini / OpenAI / Ollama with function calling.
- `src/tool_schemas.py` — Auto-generates LLM tool definitions from `ToolRegistry`.
- `tests/test_v2_llm_brain.py` — Unit tests for tool selection, prompt building, and fallback modes.

### Status:
COMPLETE

---

## Phase V2.3 — Multimodal Vision ("Look at My Screen")

### Goal:
Enable SPIDY to look at what you are working on and answer questions or perform actions based on visual context.

### Capabilities:
- "Look at this" voice command: Automatically captures the active window or full screen via `screen_capture.py` and feeds the image directly to the VLM.
- Real-life daily work use-cases:
  - *"Look at this error on my screen and tell me what's wrong."*
  - *"Summarize the open web page or document I'm reading."*
  - *"Check this design/layout and tell me if the buttons are aligned."*
  - *"Extract the text from this image and save it as a markdown note."*
- Smart Privacy Filter: Never captures or sends screenshots unless explicitly triggered by the user.

### Deliverables:
- `src/vision_agent.py` — Screen analysis engine binding `screen_capture.py` to vision models.
- `src/tools/look_at_screen.py` — First-class tool plugin for screen inspection.
- `tests/test_v2_vision.py` — Unit tests for capture formatting and vision response processing.

### Status:
PENDING

---

## Phase V2.4 — Offline Wake Word Engine ("Hey Spidy" / "Jarvis")

### Goal:
True hands-free ambient operation. SPIDY sits quietly in the background using ~0% CPU until you speak its name.

### Capabilities:
- Always-on, low-power local wake word detection using `openWakeWord` or lightweight hotword engines.
- Supported wake phrases:
  - *"Hey Spidy"*
  - *"Jarvis"*
  - *"Friday"*
- Instant acoustic response: Plays a subtle wake chime when detected, opens microphone for instruction, and executes.
- Push-to-Talk alternative: Global configurable Windows hotkey (e.g. `Ctrl + Space` or `Win + Shift + J`) for silent office environments.

### Deliverables:
- `src/wake_detector.py` — Efficient background audio listener and hotword matcher.
- `tests/test_v2_wake.py` — Testing hotword trigger states and audio thread safety.

### Status:
PENDING

---

## Phase V2.5 — Minimal Floating Desktop HUD / Status Overlay

### Goal:
A sleek, unobtrusive visual indicator on your Windows desktop that lets you know SPIDY is active without cluttering your screen.

### Capabilities:
- Transparent, borderless floating widget (customizable location: bottom-right or top-center).
- Visual states:
  - **Idle**: Small, subtle glowing emblem/orb.
  - **Listening**: Audio waveform animation showing voice input levels.
  - **Thinking**: Gentle pulse while LLM / tools execute.
  - **Speaking**: Subtitle / response preview ribbon.
- Hardware Quick Telemetry (optional toggle): CPU %, RAM %, Battery %, and active task indicators.
- Built using lightweight PyQt6 or CustomTkinter (zero heavy electron bloat).

### Deliverables:
- `src/ui/hud_overlay.py` — Transparent desktop overlay with smooth status animations.
- `src/ui/assets/` — Minimal sound and visual assets.

### Status:
PENDING

---

## Phase V2.6 — Everyday Personal Workflows & Productivity Routines

### Goal:
Pre-built daily assistant workflows that handle regular personal and development routines with a single sentence.

### Built-in Routines:
1. **"Good morning / Start my workday"**:
   - Checks system health and battery status.
   - Cleans temporary clutter from Downloads/Desktop.
   - Opens your core workspace apps (VS Code, browser, notes) in your preferred layout.
   - Recalls today's notes and tasks from personal memory.
2. **"Wrap up my day"**:
   - Checks Git status across active project repositories for uncommitted changes.
   - Summarizes today's activity log.
   - Prompts to save any open notes.
3. **"Focus mode"**:
   - Closes distracting browser tabs and notifications.
   - Sets up timer and logs distraction-free working periods.
4. **"Research topic X"**:
   - Performs web searches, scrapes top 3 articles, creates a clean bulleted summary file in your workspace.

### Deliverables:
- `src/routines.py` — High-level daily productivity routine definitions.
- `src/tools/daily_routines.py` — Tool plugin exposing daily routine triggers.
- `tests/test_v2_routines.py` — Test suite for compound routine workflows.

### Status:
PENDING

---

## Phase Summary Table

| Phase | Title | Core Focus | Prerequisite |
| :--- | :--- | :--- | :--- |
| **V2.1** | **Neural Voice & Personality** | Edge-TTS human voices, natural conversational speech, audio cues | Phase 10 |
| **V2.2** | **Conversational LLM Brain** | Dynamic function calling over all 38 tools, flexible conversation | V2.1 |
| **V2.3** | **Multimodal Vision Eyes** | "Look at my screen", code debugging, visual question answering | V2.2 |
| **V2.4** | **Ambient Wake Word Engine** | Offline "Jarvis" / "Hey Spidy" activation, zero idle CPU | V2.1 |
| **V2.5** | **Lightweight Floating HUD** | Transparent glowing desktop status orb and telemetry ribbon | V2.4 |
| **V2.6** | **Everyday Work Routines** | "Morning briefing", "Research topic", "Wrap up day" workflows | V2.3 |

---

## Guiding Principles for Version 2

1. **Practical utility over sci-fi gimmickry**: Every feature must solve a real daily PC friction point.
2. **Zero bloat**: Keep RAM and CPU footprint minimal so SPIDY can run in the background all day.
3. **Privacy first**: Screen capture, microphone listening, and document indexing only operate under explicit user control. Local models (Ollama) supported out-of-the-box.
4. **Resilient hybrid architecture**: If LLM or internet fails, the entire deterministic V1 core continues working without interruption.
5. **Preserve existing tests**: All 309 existing V1 tests must remain green at every phase milestone.

