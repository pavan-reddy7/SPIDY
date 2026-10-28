# src/task_manager.py
"""
Task Manager for SPIDY Phase 10 — Multi-Step Computer Use.

Singleton that manages the lifecycle of background tasks.
Supports running a task in a background thread so the REPL stays responsive,
reporting progress back via the progress queue, and retrieving run reports.

API:
    task_manager.submit(plan, registry)  → task_id (str)
    task_manager.status(task_id)        → TaskStatus dict
    task_manager.cancel(task_id)        → bool
    task_manager.pause(task_id)         → bool
    task_manager.resume(task_id)        → bool
    task_manager.report(task_id)        → RunReport | None
    task_manager.list_tasks()           → list[dict]
    task_manager.drain_progress(task_id) → list[str]
"""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from task_planner import Plan
from task_runner import TaskRunner, RunReport, RunStatus


@dataclass
class _TaskRecord:
    task_id:   str
    plan:      Plan
    runner:    TaskRunner
    thread:    threading.Thread
    progress:  queue.Queue          = field(default_factory=queue.Queue)
    report:    RunReport | None     = None
    started:   float                = 0.0

    def status_dict(self) -> dict:
        is_alive = self.thread.is_alive()
        run_status = self.report.status.value if self.report else ("running" if is_alive else "unknown")
        return {
            "task_id":   self.task_id,
            "goal":      self.plan.goal,
            "plan_id":   self.plan.plan_id,
            "status":    run_status,
            "is_alive":  is_alive,
            "steps_total": len(self.plan.steps),
            "steps_done":  self.report.steps_done if self.report else 0,
        }


class TaskManager:
    """Thread-safe singleton task manager."""

    def __init__(self):
        self._tasks: dict[str, _TaskRecord] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, plan: Plan, registry) -> str:
        """
        Submit a plan for background execution.

        Returns a task_id string.
        """
        import time
        task_id = str(uuid.uuid4())[:12]
        prog_queue: queue.Queue = queue.Queue()

        def callback(msg: str) -> None:
            prog_queue.put(msg)

        runner = TaskRunner(progress_callback=callback)

        def _run():
            try:
                report = runner.run(plan, registry)
            except Exception as exc:
                from task_runner import RunReport, RunStatus
                report = RunReport(
                    plan_id=plan.plan_id,
                    goal=plan.goal,
                    status=RunStatus.FAILED,
                    error=str(exc),
                )
            with self._lock:
                self._tasks[task_id].report = report
            prog_queue.put(f"__DONE__:{report.status.value}")

        thread = threading.Thread(target=_run, daemon=True, name=f"spidy-task-{task_id}")
        record = _TaskRecord(
            task_id=task_id,
            plan=plan,
            runner=runner,
            thread=thread,
            progress=prog_queue,
            started=time.monotonic(),
        )

        with self._lock:
            self._tasks[task_id] = record

        thread.start()
        return task_id

    def run_inline(self, plan: Plan, registry) -> RunReport:
        """
        Run a plan synchronously in the current thread.

        Used when the caller wants to block until completion (e.g. tests, REPL direct mode).
        """
        messages: list[str] = []
        runner = TaskRunner(progress_callback=lambda m: messages.append(m))
        report = runner.run(plan, registry)
        return report

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
        if record:
            record.runner.cancel()
            return True
        return False

    def pause(self, task_id: str) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
        if record:
            record.runner.pause()
            return True
        return False

    def resume(self, task_id: str) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
        if record:
            record.runner.resume()
            return True
        return False

    def status(self, task_id: str) -> dict | None:
        with self._lock:
            record = self._tasks.get(task_id)
        return record.status_dict() if record else None

    def report(self, task_id: str) -> RunReport | None:
        with self._lock:
            record = self._tasks.get(task_id)
        return record.report if record else None

    def drain_progress(self, task_id: str) -> list[str]:
        """Drain all queued progress messages for a task."""
        with self._lock:
            record = self._tasks.get(task_id)
        if not record:
            return []
        messages = []
        while True:
            try:
                messages.append(record.progress.get_nowait())
            except queue.Empty:
                break
        return messages

    def list_tasks(self) -> list[dict]:
        with self._lock:
            records = list(self._tasks.values())
        return [r.status_dict() for r in records]

    def cleanup_done(self) -> int:
        """Remove completed tasks from memory. Returns count removed."""
        with self._lock:
            done_ids = [
                tid for tid, rec in self._tasks.items()
                if not rec.thread.is_alive() and rec.report is not None
            ]
            for tid in done_ids:
                del self._tasks[tid]
        return len(done_ids)


# Module-level singleton
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
