# src/tools/run_task.py
"""
Tool: Run Task

Execute a multi-step goal as an autonomous task sequence.
Parses the user's high-level goal into a Plan, then runs all steps
sequentially with automatic retry, error recovery, and progress reporting.

The task runs synchronously and streams progress output to the console.
The final report summarises every step's outcome.

Security:
- CONFIRM permission — user-visible multi-step action sequence.
- All individual tool calls respect their own permission levels.
- No additional privilege is granted beyond the tools' own rules.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from task_planner import parse_goal
from task_manager import get_task_manager


class RunTaskTool(Tool):
    """Execute a multi-step goal autonomously with retry and error recovery."""

    @property
    def name(self) -> str:
        return "run_task"

    @property
    def description(self) -> str:
        return (
            "Execute a multi-step task autonomously. "
            "Plans, executes, retries, and reports results. "
            "Example: run task prepare my project for tomorrow's demo"
        )

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "run task",
            "execute task",
            "do task",
            "perform task",
            "run plan",
            "execute plan",
            "do multi step",
            "multi step task",
            "autonomous task",
            "run steps",
            "task run",
        ]

    def execute(self, **params) -> ToolResult:
        goal = params.get("target", "").strip()

        if not goal:
            return ToolResult(
                success=False,
                message=(
                    "Please specify a goal for the task.\n"
                    "Examples:\n"
                    "  run task prepare my project for the demo\n"
                    "  run task find and read all test files\n"
                    "  run task describe what is on screen\n"
                    "  run task search the web for Python best practices"
                ),
            )

        try:
            # Parse the goal into a plan
            plan = parse_goal(goal)

            print(f"\n▶ Task Goal: {goal}")
            print(f"  Plan {plan.plan_id}: {len(plan.steps)} steps planned")
            print()

            # Get the registry from the module-level context if available
            registry = params.get("_registry")
            if registry is None:
                # Try to build one on the fly
                import pathlib
                import importlib.util
                from tool_base import ToolRegistry
                registry = ToolRegistry()
                tools_dir = pathlib.Path(__file__).resolve().parents[1] / "tools"
                registry.discover(tools_dir)

            # Run inline (blocks until done)
            manager = get_task_manager()
            report = manager.run_inline(plan, registry)

            return ToolResult(
                success=(report.steps_done > 0),
                message=report.summary_message(),
                data={
                    "plan_id":      report.plan_id,
                    "status":       report.status.value,
                    "steps_done":   report.steps_done,
                    "steps_failed": report.steps_failed,
                    "elapsed_s":    report.elapsed_s,
                    "goal":         goal,
                },
            )

        except Exception as e:
            return ToolResult(success=False, message=f"Task execution error: {e}")
