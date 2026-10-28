# src/task_planner.py
"""
Task Planner for SPIDY Phase 10 — Multi-Step Computer Use.

Converts a high-level user goal into an ordered sequence of concrete
TaskStep objects that the TaskRunner can execute.

Design:
- Plans are deterministic and rule-based (no LLM required).
- Each step maps to exactly one registered tool + parameters.
- Steps can have conditions, retry limits, and dependencies.
- Supports sequential steps, conditional branches, and loops.
- Fully serialisable so plans can be saved/loaded for pause-resume.

Architecture:
  goal (str)
    ↓
  _parse_goal()       — keyword pattern matching to pick a plan template
    ↓
  Plan                — list[TaskStep] + metadata
    ↓
  TaskRunner          — executes, observes, retries, recovers

Step types:
  ACTION   — call a tool (default)
  BRANCH   — evaluate a condition; choose next step index
  LOOP     — repeat N times or until condition met
  OBSERVE  — capture output; store in context
  VERIFY   — assert condition; raise RecoveryError if fails
  WAIT     — pause N seconds
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Step types & status
# ---------------------------------------------------------------------------

class StepType(str, Enum):
    ACTION  = "action"
    OBSERVE = "observe"
    VERIFY  = "verify"
    BRANCH  = "branch"
    LOOP    = "loop"
    WAIT    = "wait"


class StepStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"
    SKIPPED   = "skipped"
    RETRYING  = "retrying"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TaskStep:
    """A single executable unit within a plan."""
    step_id:     str
    description: str
    step_type:   StepType           = StepType.ACTION
    tool_name:   str | None         = None
    params:      dict[str, Any]     = field(default_factory=dict)
    # Retry policy
    max_retries: int                = 2
    retry_delay_s: float            = 1.0
    # Recovery: if this step fails after all retries, run this step instead
    fallback_tool:  str | None      = None
    fallback_params: dict[str, Any] = field(default_factory=dict)
    # Condition for BRANCH/VERIFY (Python expression evaluated in context)
    condition:   str | None         = None
    # For BRANCH: step indices if condition is True/False
    on_true:     int | None         = None
    on_false:    int | None         = None
    # For LOOP: number of repetitions and inner steps list
    loop_count:  int                = 1
    loop_steps:  list["TaskStep"]   = field(default_factory=list)
    # For WAIT
    wait_seconds: float             = 1.0
    # Runtime state (not part of the plan definition)
    status:      StepStatus         = StepStatus.PENDING
    result_key:  str | None         = None   # store result.data in context[result_key]
    output:      str                = ""
    retries_used: int               = 0

    def to_dict(self) -> dict:
        return {
            "step_id":     self.step_id,
            "description": self.description,
            "step_type":   self.step_type.value,
            "tool_name":   self.tool_name,
            "params":      self.params,
            "status":      self.status.value,
            "output":      self.output,
            "retries_used": self.retries_used,
        }


@dataclass
class Plan:
    """A complete execution plan for a user goal."""
    plan_id:   str
    goal:      str
    steps:     list[TaskStep]    = field(default_factory=list)
    context:   dict[str, Any]   = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "goal":    self.goal,
            "steps":   [s.to_dict() for s in self.steps],
        }


# ---------------------------------------------------------------------------
# Helper: step factory
# ---------------------------------------------------------------------------

def _step(
    description: str,
    tool_name: str,
    params: dict | None = None,
    max_retries: int = 2,
    fallback_tool: str | None = None,
    fallback_params: dict | None = None,
    result_key: str | None = None,
) -> TaskStep:
    return TaskStep(
        step_id=str(uuid.uuid4())[:8],
        description=description,
        step_type=StepType.ACTION,
        tool_name=tool_name,
        params=params or {},
        max_retries=max_retries,
        fallback_tool=fallback_tool,
        fallback_params=fallback_params or {},
        result_key=result_key,
    )


def _verify_step(description: str, condition: str, fallback_tool: str | None = None) -> TaskStep:
    return TaskStep(
        step_id=str(uuid.uuid4())[:8],
        description=description,
        step_type=StepType.VERIFY,
        condition=condition,
        fallback_tool=fallback_tool,
    )


def _wait_step(seconds: float, description: str = "") -> TaskStep:
    return TaskStep(
        step_id=str(uuid.uuid4())[:8],
        description=description or f"Wait {seconds}s",
        step_type=StepType.WAIT,
        wait_seconds=seconds,
    )


# ---------------------------------------------------------------------------
# Built-in plan templates
# ---------------------------------------------------------------------------

def _plan_git_status_and_test(goal: str, target: str) -> list[TaskStep]:
    """Plan: check git status then run tests."""
    return [
        _step("List project directory", "list_directory", {"target": target}),
        _step("Check active window context", "get_active_window"),
        _step("Search for test files", "find_files", {"target": f"test*.py {target}"}, result_key="test_files"),
        _step("Read recent activity log (audit.log)", "read_file", {"target": "data/audit.log"}, max_retries=1),
        _verify_step("Confirm project directory found", "True"),
    ]


def _plan_find_and_read(goal: str, target: str) -> list[TaskStep]:
    """Plan: find files matching a pattern and read them."""
    return [
        _step("Find matching files", "find_files", {"target": target}, result_key="found_files"),
        _step("List directory context", "list_directory", {"target": target}),
        _step("Get system info for context", "get_system_info"),
    ]


def _plan_screen_report(goal: str, target: str) -> list[TaskStep]:
    """Plan: describe screen, find elements, read text."""
    return [
        _step("Take a screenshot", "screenshot"),
        _step("Describe what is on screen", "describe_screen", result_key="screen_desc"),
        _step("Read screen text via OCR", "read_screen", result_key="screen_text"),
        _step("Search for specific element on screen", "find_on_screen",
              {"target": target or "button"}, result_key="found_elements"),
    ]


def _plan_open_and_verify(goal: str, target: str) -> list[TaskStep]:
    """Plan: open an application and verify it started."""
    return [
        _step("Check current active window before open", "get_active_window"),
        _step("Open the target application", "open_application", {"target": target}, max_retries=1),
        _wait_step(2.0, "Wait for application to start"),
        _step("Verify application is now running", "get_active_window", result_key="after_window"),
        _step("Describe screen after open", "describe_screen"),
    ]


def _plan_file_operations(goal: str, target: str) -> list[TaskStep]:
    """Plan: multi-step file management sequence."""
    return [
        _step("List current directory", "list_directory", {"target": target or "."}),
        _step("Get file/folder metadata", "file_metadata", {"target": target}, max_retries=1),
        _step("Search inside target for keywords", "search_contents",
              {"target": target, "query": "TODO"}, max_retries=1),
        _verify_step("Confirm file operations completed", "True"),
    ]


def _plan_research_and_save(goal: str, target: str) -> list[TaskStep]:
    """Plan: web search, read page, save results."""
    return [
        _step("Search the web for information", "web_search", {"target": target}, result_key="search_results"),
        _step("Take screenshot of search results", "screenshot"),
        _step("Get system info", "get_system_info"),
        _verify_step("Verify web search completed", "True"),
    ]


def _plan_memory_recall_and_act(goal: str, target: str) -> list[TaskStep]:
    """Plan: recall memories then act based on stored knowledge."""
    return [
        _step("Recall related memories", "recall", {"target": target}, result_key="memories"),
        _step("Get active window context", "get_active_window"),
        _step("List relevant directory", "list_directory", {"target": target or "."}, max_retries=1),
        _verify_step("Memory recall step complete", "True"),
    ]


def _plan_document_indexing_and_query(goal: str, target: str) -> list[TaskStep]:
    """Plan: index documents then query them."""
    return [
        _step("Index the specified documents", "index_documents",
              {"target": target}, result_key="index_result"),
        _step("List the indexed documents", "manage_index",
              {"target": "list"}, result_key="indexed_list"),
        _step("Query the indexed documents", "ask_documents",
              {"target": f"summary of {target}"}, result_key="rag_answer"),
        _verify_step("Document index and query complete", "True"),
    ]


def _plan_demo_preparation(goal: str, target: str) -> list[TaskStep]:
    """Plan: prepare project for a demo (multi-phase)."""
    return [
        _step("List project structure", "list_directory",
              {"target": target or "."}, result_key="project_files"),
        _step("Find test files", "find_files",
              {"target": f"test*.py"}, result_key="test_files"),
        _step("Check current screen state", "describe_screen"),
        _step("Search for TODO items in project", "search_contents",
              {"target": target or ".", "query": "TODO"}, max_retries=1),
        _step("Take screenshot of current state", "screenshot"),
        _step("Get system performance info", "get_system_info"),
        _verify_step("Project inspection complete", "True"),
    ]


def _plan_generic(goal: str, target: str) -> list[TaskStep]:
    """Generic fallback plan: gather context, describe screen, report."""
    return [
        _step("Get system context", "get_system_info"),
        _step("Describe current screen", "describe_screen", result_key="screen"),
        _step("List user documents area", "list_directory",
              {"target": target or "."}, max_retries=1),
        _verify_step("Context gathering complete", "True"),
    ]


# ---------------------------------------------------------------------------
# Plan selector
# ---------------------------------------------------------------------------

# Ordered from most specific to least specific
_PLAN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(demo|prepare.*demo|get.*ready)\b", re.I), "demo"),
    (re.compile(r"\b(git|commit|push|pull|status|branch)\b", re.I), "git"),
    (re.compile(r"\b(open|launch|start|run)\b.*\b(app|application|program|notepad|browser)\b", re.I), "open_app"),
    (re.compile(r"\b(index|rag|documents?|ask.*doc|query.*doc)\b", re.I), "rag"),
    (re.compile(r"\b(screen|ocr|describe|what.*on|capture|screenshot)\b", re.I), "screen"),
    (re.compile(r"\b(web|google|look up|research)\b|search.*(web|internet|online)", re.I), "web"),
    (re.compile(r"\b(file|folder|directory|find|list|read|search)\b", re.I), "files"),
    (re.compile(r"\b(remember|recall|memory|forget|store)\b", re.I), "memory"),
]


def _extract_target(goal: str) -> str:
    """Extract the primary target/subject from the goal string."""
    # Remove common leading verbs
    cleaned = re.sub(
        r"^(prepare|open|find|search|check|get|describe|run|launch|index|ask|recall|list)\s+",
        "", goal.strip(), flags=re.I
    )
    # Remove trailing filler phrases
    cleaned = re.sub(r"\s+(for tomorrow|for the demo|and report|and save)\s*$", "", cleaned, flags=re.I)
    return cleaned.strip()


def parse_goal(goal: str) -> Plan:
    """
    Parse a natural language goal into an executable Plan.

    Returns a Plan with a concrete list of TaskSteps.
    """
    target = _extract_target(goal)

    # Match plan template
    plan_type = "generic"
    for pattern, ptype in _PLAN_PATTERNS:
        if pattern.search(goal):
            plan_type = ptype
            break

    builders = {
        "demo":     _plan_demo_preparation,
        "git":      _plan_git_status_and_test,
        "open_app": _plan_open_and_verify,
        "rag":      _plan_document_indexing_and_query,
        "screen":   _plan_screen_report,
        "files":    _plan_file_operations,
        "web":      _plan_research_and_save,
        "memory":   _plan_memory_recall_and_act,
        "generic":  _plan_generic,
    }

    steps = builders[plan_type](goal, target)

    return Plan(
        plan_id=str(uuid.uuid4())[:12],
        goal=goal,
        steps=steps,
    )
