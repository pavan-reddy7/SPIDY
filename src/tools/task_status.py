# src/tools/task_status.py
"""
Tool: Task Status

Check the status of running, paused, or completed tasks.
Also provides controls: cancel a task, pause/resume, and list all tasks.

Security:
- SAFE permission (read-only status queries and control of own tasks).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tool_base import Tool, ToolResult, PERMISSION_SAFE
from task_manager import get_task_manager
from task_runner import RunStatus


class TaskStatusTool(Tool):
    """Check, cancel, pause, or resume background multi-step tasks."""

    @property
    def name(self) -> str:
        return "task_status"

    @property
    def description(self) -> str:
        return (
            "Check task status, list all tasks, or cancel/pause/resume a task. "
            "Example: task status | list tasks | cancel task abc123"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_SAFE

    @property
    def keywords(self) -> list[str]:
        return [
            "task status",
            "task status check",
            "check task",
            "list tasks",
            "show tasks",
            "all tasks",
            "cancel task",
            "stop task",
            "pause task",
            "resume task",
            "task progress",
            "task report",
            "task list",
        ]

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "").strip().lower()
        manager = get_task_manager()

        # --- list all tasks ---
        if not target or target in ("list", "all", "show", "tasks"):
            return self._list_tasks(manager)

        # --- cancel <task_id> ---
        if target.startswith("cancel "):
            task_id = target[len("cancel "):].strip()
            return self._cancel_task(manager, task_id)

        # --- pause <task_id> ---
        if target.startswith("pause "):
            task_id = target[len("pause "):].strip()
            ok = manager.pause(task_id)
            if ok:
                return ToolResult(success=True, message=f"Task '{task_id}' paused.")
            return ToolResult(success=False, message=f"Task '{task_id}' not found.")

        # --- resume <task_id> ---
        if target.startswith("resume "):
            task_id = target[len("resume "):].strip()
            ok = manager.resume(task_id)
            if ok:
                return ToolResult(success=True, message=f"Task '{task_id}' resumed.")
            return ToolResult(success=False, message=f"Task '{task_id}' not found.")

        # --- report / progress for a specific task id ---
        if target.startswith("report "):
            task_id = target[len("report "):].strip()
            return self._task_report(manager, task_id)

        # --- treat bare word as task_id lookup ---
        status = manager.status(target)
        if status:
            return self._format_status(status, manager, target)

        return ToolResult(
            success=False,
            message=(
                f"Unknown task command: '{target}'.\n"
                "Examples:\n"
                "  task status              — list all tasks\n"
                "  task status list         — list all tasks\n"
                "  task status <task_id>    — show specific task\n"
                "  cancel task <task_id>    — cancel a running task\n"
                "  pause task <task_id>     — pause a task\n"
                "  resume task <task_id>    — resume a paused task"
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _list_tasks(self, manager) -> ToolResult:
        tasks = manager.list_tasks()
        if not tasks:
            return ToolResult(
                success=True,
                message="No tasks recorded in this session.",
                data={"tasks": []},
            )

        lines = [f"Tasks ({len(tasks)}):"]
        for t in tasks:
            alive_tag = " [running]" if t["is_alive"] else ""
            lines.append(
                f"  {t['task_id']}  [{t['status']}{alive_tag}]  {t['steps_done']}/{t['steps_total']} steps"
                f"  — {t['goal'][:60]}"
            )

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"tasks": tasks},
        )

    def _cancel_task(self, manager, task_id: str) -> ToolResult:
        ok = manager.cancel(task_id)
        if ok:
            return ToolResult(
                success=True,
                message=f"Cancellation requested for task '{task_id}'.",
            )
        return ToolResult(
            success=False,
            message=f"Task '{task_id}' not found.",
        )

    def _task_report(self, manager, task_id: str) -> ToolResult:
        report = manager.report(task_id)
        if not report:
            # Try draining progress messages
            msgs = manager.drain_progress(task_id)
            if msgs:
                return ToolResult(
                    success=True,
                    message="\n".join(msgs),
                )
            return ToolResult(
                success=False,
                message=f"No report available for task '{task_id}'.",
            )

        return ToolResult(
            success=True,
            message=report.summary_message(),
            data={
                "plan_id":      report.plan_id,
                "status":       report.status.value,
                "steps_done":   report.steps_done,
                "steps_failed": report.steps_failed,
                "elapsed_s":    report.elapsed_s,
            },
        )

    def _format_status(self, status: dict, manager, task_id: str) -> ToolResult:
        lines = [
            f"Task: {task_id}",
            f"  Goal:    {status['goal']}",
            f"  Status:  {status['status']}",
            f"  Progress: {status['steps_done']}/{status['steps_total']} steps",
        ]
        # Drain any progress messages
        msgs = manager.drain_progress(task_id)
        if msgs:
            lines.append("  Recent progress:")
            for m in msgs[-5:]:
                lines.append(f"    {m}")
        return ToolResult(
            success=True,
            message="\n".join(lines),
            data=status,
        )
