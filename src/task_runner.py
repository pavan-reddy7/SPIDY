# src/task_runner.py
"""
Task Runner for SPIDY Phase 10 — Multi-Step Computer Use.

Executes a Plan (list of TaskSteps) against the ToolRegistry with:
  - Sequential step execution
  - Conditional branches (BRANCH step type)
  - Loops with iteration count (LOOP step type)
  - Observation: captures tool output into shared context
  - Verification: evaluates Python expressions in context; raises on failure
  - Retry with configurable limit and delay
  - Fallback steps on exhausted retries
  - Error recovery: continue plan after fallback or mark step FAILED + continue
  - Progress reporting via callbacks
  - Pause / resume via threading.Event
  - Cancellation via threading.Event
  - Serialisable run log for audit

Architecture:
    TaskRunner.run(plan, registry)
        → for each step in plan.steps:
            → execute_step(step, registry, context)
                → tool.execute(**params)
                    → on success: mark DONE, store in context
                    → on failure: retry up to max_retries
                        → on exhausted: try fallback_tool
                            → on fallback failure: mark FAILED (recoverable → continue)
                        → on verify failure: raise TaskVerificationError
"""

from __future__ import annotations

import sys
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from task_planner import Plan, TaskStep, StepType, StepStatus


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TaskCancelledError(Exception):
    """Raised when the user cancels a running task."""


class TaskVerificationError(Exception):
    """Raised when a VERIFY step condition evaluates to False."""


class TaskRecoveryError(Exception):
    """Raised when a step fails and has no fallback."""


# ---------------------------------------------------------------------------
# Run result
# ---------------------------------------------------------------------------

class RunStatus(str, Enum):
    RUNNING   = "running"
    PAUSED    = "paused"
    DONE      = "done"
    CANCELLED = "cancelled"
    FAILED    = "failed"


@dataclass
class StepReport:
    """Report for a single executed step."""
    step_id:    str
    description: str
    tool_name:  str | None
    status:     StepStatus
    output:     str
    retries_used: int
    elapsed_s:  float


@dataclass
class RunReport:
    """Complete run report for a plan."""
    plan_id:    str
    goal:       str
    status:     RunStatus
    steps:      list[StepReport] = field(default_factory=list)
    context:    dict[str, Any]   = field(default_factory=dict)
    error:      str              = ""
    elapsed_s:  float            = 0.0

    # Summary helpers
    @property
    def steps_done(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.DONE)

    @property
    def steps_failed(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)

    @property
    def steps_skipped(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.SKIPPED)

    def summary_message(self) -> str:
        total = len(self.steps)
        lines = [
            f"Task '{self.goal[:60]}' — {self.status.value.upper()}",
            f"  Steps: {self.steps_done}/{total} done"
            + (f", {self.steps_failed} failed" if self.steps_failed else "")
            + (f", {self.steps_skipped} skipped" if self.steps_skipped else ""),
            f"  Time: {self.elapsed_s:.1f}s",
        ]
        if self.error:
            lines.append(f"  Error: {self.error}")
        for s in self.steps:
            icon = {"done": "✓", "failed": "✗", "skipped": "—",
                    "retrying": "↺", "running": "►", "pending": "○"}.get(s.status.value, "?")
            retry_note = f" (retried {s.retries_used}x)" if s.retries_used else ""
            lines.append(f"    {icon} [{s.step_id}] {s.description}{retry_note}")
            if s.output:
                # Show first line of output
                first = s.output.split("\n")[0][:120]
                lines.append(f"        → {first}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Registry shim (lazy import so circular imports are avoided)
# ---------------------------------------------------------------------------

def _get_tool(registry, tool_name: str):
    """Get a tool from registry; returns None if not found."""
    return registry.get(tool_name)


# ---------------------------------------------------------------------------
# Task Runner
# ---------------------------------------------------------------------------

class TaskRunner:
    """
    Executes a Plan against a ToolRegistry.

    Thread-safe pause/resume and cancellation via threading Events.
    Progress reported via an optional callback.
    """

    def __init__(
        self,
        progress_callback: Callable[[str], None] | None = None,
        retry_delay_s: float = 0.5,
    ):
        self._progress_callback = progress_callback or (lambda msg: None)
        self._default_retry_delay = retry_delay_s
        self._pause_event  = threading.Event()
        self._cancel_event = threading.Event()
        self._pause_event.set()   # not paused initially

    # ------------------------------------------------------------------
    # Control API
    # ------------------------------------------------------------------

    def pause(self) -> None:
        """Pause execution between steps."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume paused execution."""
        self._pause_event.set()

    def cancel(self) -> None:
        """Request cancellation. Current step finishes, then stops."""
        self._cancel_event.set()
        self._pause_event.set()  # unblock any waiting pause

    def reset(self) -> None:
        """Reset control events for reuse."""
        self._cancel_event.clear()
        self._pause_event.set()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, plan: Plan, registry) -> RunReport:
        """
        Execute the plan and return a RunReport.

        Safe to call from any thread.
        """
        self.reset()
        report = RunReport(
            plan_id=plan.plan_id,
            goal=plan.goal,
            status=RunStatus.RUNNING,
            context=dict(plan.context),
        )
        t0 = time.monotonic()

        self._progress(f"\u25b6 Starting task: {plan.goal}")
        self._progress(f"  Plan {plan.plan_id}: {len(plan.steps)} step(s)")

        try:
            step_index = 0
            while step_index < len(plan.steps):
                # Check for pause
                self._pause_event.wait()

                # Check for cancellation
                if self._cancel_event.is_set():
                    report.status = RunStatus.CANCELLED
                    self._progress("\u2298 Task cancelled by user.")
                    break

                step = plan.steps[step_index]
                self._progress(f"  [{step_index + 1}/{len(plan.steps)}] {step.description} \u2026")

                next_index = self._execute_step(step, registry, report)

                step_index = next_index if next_index is not None else (step_index + 1)

            else:
                # Loop completed normally
                if report.status == RunStatus.RUNNING:
                    report.status = RunStatus.DONE

        except TaskCancelledError:
            report.status = RunStatus.CANCELLED
            self._progress("\u2298 Task cancelled by user.")

        report.elapsed_s = time.monotonic() - t0

        if report.status == RunStatus.RUNNING:
            report.status = RunStatus.DONE

        self._progress(f"\n{report.summary_message()}")
        return report

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _execute_step(
        self,
        step: TaskStep,
        registry,
        report: RunReport,
    ) -> int | None:
        """
        Execute one step.

        Returns:
            None      — advance to next step normally
            int index — jump to this step index (for BRANCH)
        """
        t0 = time.monotonic()
        step.status = StepStatus.RUNNING

        try:
            if step.step_type == StepType.WAIT:
                return self._exec_wait(step, report, t0)

            elif step.step_type == StepType.VERIFY:
                return self._exec_verify(step, report, t0)

            elif step.step_type == StepType.BRANCH:
                return self._exec_branch(step, report, t0)

            elif step.step_type == StepType.OBSERVE:
                return self._exec_observe(step, registry, report, t0)

            elif step.step_type == StepType.LOOP:
                return self._exec_loop(step, registry, report, t0)

            else:  # ACTION (default)
                return self._exec_action(step, registry, report, t0)

        except TaskCancelledError:
            step.status = StepStatus.FAILED
            step.output = "Cancelled"
            report.steps.append(_make_step_report(step, time.monotonic() - t0))
            raise

        except TaskVerificationError as e:
            step.status = StepStatus.FAILED
            step.output = str(e)
            report.steps.append(_make_step_report(step, time.monotonic() - t0))
            report.status = RunStatus.FAILED
            report.error = str(e)
            return len(report.steps) + 1000  # jump past all steps

        except Exception as e:
            step.status = StepStatus.FAILED
            step.output = f"Unexpected error: {e}"
            report.steps.append(_make_step_report(step, time.monotonic() - t0))
            self._progress(f"    ⚠ Step error: {e}")
            return None  # continue with next step (recovery by continuing)

    # ------------------------------------------------------------------
    # Step type implementations
    # ------------------------------------------------------------------

    def _exec_wait(self, step: TaskStep, report: RunReport, t0: float) -> None:
        self._progress(f"    \u23f3 Waiting {step.wait_seconds}s \u2026")
        deadline = time.monotonic() + step.wait_seconds
        while time.monotonic() < deadline:
            if self._cancel_event.is_set():
                step.status = StepStatus.SKIPPED
                step.output = "Wait cancelled"
                report.steps.append(_make_step_report(step, time.monotonic() - t0))
                raise TaskCancelledError()
            time.sleep(min(0.1, deadline - time.monotonic()))
        step.status = StepStatus.DONE
        step.output = f"Waited {step.wait_seconds}s"
        report.steps.append(_make_step_report(step, time.monotonic() - t0))
        return None

    def _exec_verify(self, step: TaskStep, report: RunReport, t0: float) -> None:
        condition = step.condition or "True"
        try:
            result = bool(eval(condition, {"__builtins__": {}}, report.context))  # noqa: S307
        except Exception as e:
            result = False

        if result:
            step.status = StepStatus.DONE
            step.output = f"Verified: {condition}"
            self._progress(f"    ✓ Verified: {condition}")
        else:
            step.status = StepStatus.FAILED
            step.output = f"Verification failed: {condition}"
            self._progress(f"    ✗ Verification failed: {condition}")
            report.steps.append(_make_step_report(step, time.monotonic() - t0))
            raise TaskVerificationError(f"Verification failed: {condition!r}")

        report.steps.append(_make_step_report(step, time.monotonic() - t0))
        return None

    def _exec_branch(self, step: TaskStep, report: RunReport, t0: float) -> int | None:
        condition = step.condition or "True"
        try:
            result = bool(eval(condition, {"__builtins__": {}}, report.context))  # noqa: S307
        except Exception:
            result = False

        next_idx = step.on_true if result else step.on_false
        step.status = StepStatus.DONE
        step.output = f"Branch {'True' if result else 'False'} → step {next_idx}"
        self._progress(f"    ↦ Branch {'True' if result else 'False'} → step {next_idx}")
        report.steps.append(_make_step_report(step, time.monotonic() - t0))
        return next_idx

    def _exec_observe(self, step: TaskStep, registry, report: RunReport, t0: float) -> None:
        # OBSERVE is like ACTION but always stores result in context
        return self._exec_action(step, registry, report, t0)

    def _exec_loop(self, step: TaskStep, registry, report: RunReport, t0: float) -> None:
        for i in range(step.loop_count):
            if self._cancel_event.is_set():
                raise TaskCancelledError()
            self._progress(f"    ↻ Loop iteration {i + 1}/{step.loop_count}")
            for inner in step.loop_steps:
                self._execute_step(inner, registry, report)
        step.status = StepStatus.DONE
        step.output = f"Loop completed ({step.loop_count} iterations)"
        report.steps.append(_make_step_report(step, time.monotonic() - t0))
        return None

    def _exec_action(self, step: TaskStep, registry, report: RunReport, t0: float) -> None:
        """Execute an ACTION step with retry + fallback logic."""
        if not step.tool_name:
            step.status = StepStatus.SKIPPED
            step.output = "No tool specified"
            report.steps.append(_make_step_report(step, time.monotonic() - t0))
            return None

        tool = _get_tool(registry, step.tool_name)
        if tool is None:
            step.status = StepStatus.SKIPPED
            step.output = f"Tool '{step.tool_name}' not found in registry"
            self._progress(f"    — Skipping: tool '{step.tool_name}' not registered")
            report.steps.append(_make_step_report(step, time.monotonic() - t0))
            return None

        # --- Retry loop ---
        last_error: str = ""
        for attempt in range(step.max_retries + 1):
            if self._cancel_event.is_set():
                raise TaskCancelledError()

            if attempt > 0:
                step.status = StepStatus.RETRYING
                step.retries_used = attempt
                delay = step.retry_delay_s or self._default_retry_delay
                self._progress(f"    ↺ Retry {attempt}/{step.max_retries} after {delay}s …")
                time.sleep(delay)

            try:
                result = tool.execute(**step.params)
                if result.success:
                    step.status = StepStatus.DONE
                    step.output = result.message
                    # Store in context if requested
                    if step.result_key and result.data:
                        report.context[step.result_key] = result.data
                    elif step.result_key:
                        report.context[step.result_key] = result.message
                    self._progress(f"    ✓ {result.message[:120]}")
                    report.steps.append(_make_step_report(step, time.monotonic() - t0))
                    return None
                else:
                    last_error = result.message
                    self._progress(f"    ✗ Tool error: {result.message[:80]}")
            except Exception as exc:
                last_error = str(exc)
                self._progress(f"    ✗ Exception: {exc}")

        # --- All retries exhausted: try fallback ---
        if step.fallback_tool:
            fallback_tool = _get_tool(registry, step.fallback_tool)
            if fallback_tool:
                self._progress(f"    ⟳ Fallback: {step.fallback_tool}")
                try:
                    fb_result = fallback_tool.execute(**step.fallback_params)
                    if fb_result.success:
                        step.status = StepStatus.DONE
                        step.output = f"[fallback] {fb_result.message}"
                        report.steps.append(_make_step_report(step, time.monotonic() - t0))
                        return None
                    else:
                        last_error = f"Fallback also failed: {fb_result.message}"
                except Exception as exc:
                    last_error = f"Fallback exception: {exc}"

        # --- Step failed; mark but continue plan (error recovery by proceeding) ---
        step.status = StepStatus.FAILED
        step.output = last_error
        self._progress(f"    ✗ Step failed (continuing): {last_error[:80]}")
        report.steps.append(_make_step_report(step, time.monotonic() - t0))
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _progress(self, msg: str) -> None:
        self._progress_callback(msg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step_report(step: TaskStep, elapsed: float) -> StepReport:
    return StepReport(
        step_id=step.step_id,
        description=step.description,
        tool_name=step.tool_name,
        status=step.status,
        output=step.output,
        retries_used=step.retries_used,
        elapsed_s=round(elapsed, 3),
    )
