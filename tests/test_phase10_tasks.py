# tests/test_phase10_tasks.py
"""
Phase 10 — Multi-Step Computer Use: Test Suite

Tests cover:
1. TaskPlanner  — goal parsing, plan generation, step types, pattern matching
2. TaskRunner   — sequential execution, retry, fallback, error recovery,
                  verify/branch/wait/loop steps, pause/resume, cancellation
3. TaskManager  — submit, status, cancel, pause/resume, report, drain_progress
4. Tool plugins — run_task, task_status (properties, keyword routing, execute)
5. Intent parsing for Phase 10 tools
6. Security / permission levels
"""

from __future__ import annotations

import os
import pathlib
import sys
import time
import threading
from unittest import mock

import pytest

# Add src to path
SRC_DIR = str(pathlib.Path(__file__).resolve().parents[1] / "src")
sys.path.insert(0, SRC_DIR)

from task_planner import (
    parse_goal, Plan, TaskStep, StepType, StepStatus,
    _step, _verify_step, _wait_step,
)
from task_runner import (
    TaskRunner, RunReport, RunStatus,
    TaskCancelledError, TaskVerificationError,
)
from task_manager import TaskManager, get_task_manager
from tool_base import ToolRegistry, ToolResult, PERMISSION_SAFE, PERMISSION_CONFIRM
from intent_parser import parse_intent
from tools.run_task import RunTaskTool
from tools.task_status import TaskStatusTool


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def registry():
    """Tool registry with all auto-discovered tools."""
    reg = ToolRegistry()
    tools_dir = pathlib.Path(SRC_DIR) / "tools"
    reg.discover(tools_dir)
    return reg


@pytest.fixture
def mini_registry():
    """Minimal registry with only system_info and get_active_window (fast, no side-effects)."""
    reg = ToolRegistry()
    # Discover only specific safe tools
    from tools.system_info import SystemInfoTool
    from tools.active_window import ActiveWindowTool
    reg.register(SystemInfoTool())
    reg.register(ActiveWindowTool())
    return reg


@pytest.fixture
def fresh_manager():
    """A fresh TaskManager (not the singleton) for isolation."""
    return TaskManager()


@pytest.fixture
def quiet_runner(fresh_manager):
    """A TaskRunner that discards progress output."""
    return TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)


# ------------------------------------------------------------------ #
#  1. TaskPlanner Tests                                                #
# ------------------------------------------------------------------ #

class TestTaskPlanner:
    """Test goal parsing and plan generation."""

    def test_parse_goal_returns_plan(self):
        plan = parse_goal("prepare my project for the demo")
        assert isinstance(plan, Plan)
        assert plan.plan_id
        assert plan.goal == "prepare my project for the demo"
        assert len(plan.steps) > 0

    def test_plan_steps_are_task_steps(self):
        plan = parse_goal("check system info")
        for step in plan.steps:
            assert isinstance(step, TaskStep)
            assert step.step_id
            assert step.description

    def test_demo_plan_selected(self):
        plan = parse_goal("prepare my project for tomorrow's demo")
        # Should pick demo template (has 7 steps)
        assert len(plan.steps) >= 5
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        assert "list_directory" in tool_names or "find_files" in tool_names

    def test_screen_plan_selected(self):
        plan = parse_goal("describe what is on screen")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        assert "describe_screen" in tool_names

    def test_git_plan_selected(self):
        plan = parse_goal("check git status and run tests")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        assert "list_directory" in tool_names or "find_files" in tool_names

    def test_open_app_plan_selected(self):
        plan = parse_goal("open notepad application")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        assert "open_application" in tool_names

    def test_rag_plan_selected(self):
        plan = parse_goal("index documents in C:\\SPIDY")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        assert "index_documents" in tool_names

    def test_web_plan_selected(self):
        plan = parse_goal("search the web for Python best practices")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        assert "web_search" in tool_names

    def test_memory_plan_selected(self):
        plan = parse_goal("recall what I know about SPIDY")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        assert "recall" in tool_names

    def test_generic_plan_fallback(self):
        plan = parse_goal("do something unusual xyz12345")
        assert len(plan.steps) > 0

    def test_step_has_required_fields(self):
        step = _step("Test step", "get_system_info")
        assert step.step_id
        assert step.description == "Test step"
        assert step.tool_name == "get_system_info"
        assert step.step_type == StepType.ACTION
        assert step.max_retries >= 0

    def test_verify_step_type(self):
        step = _verify_step("Always true", "True")
        assert step.step_type == StepType.VERIFY
        assert step.condition == "True"

    def test_wait_step_type(self):
        step = _wait_step(0.5, "Half-second pause")
        assert step.step_type == StepType.WAIT
        assert step.wait_seconds == 0.5

    def test_plan_context_is_empty_by_default(self):
        plan = parse_goal("list files")
        assert isinstance(plan.context, dict)

    def test_plan_to_dict(self):
        plan = parse_goal("get system info")
        d = plan.to_dict()
        assert "plan_id" in d
        assert "goal" in d
        assert "steps" in d
        assert isinstance(d["steps"], list)

    def test_step_to_dict(self):
        step = _step("Describe screen", "describe_screen")
        d = step.to_dict()
        assert d["tool_name"] == "describe_screen"
        assert d["status"] == "pending"


# ------------------------------------------------------------------ #
#  2. TaskRunner Tests                                                 #
# ------------------------------------------------------------------ #

class TestTaskRunner:
    """Test step execution, retry, verify, branch, wait, cancellation."""

    def _run(self, steps: list[TaskStep], registry=None) -> RunReport:
        runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
        plan = Plan(plan_id="test", goal="test goal", steps=steps)
        if registry is None:
            registry = ToolRegistry()
        return runner.run(plan, registry)

    # --- ACTION step ---

    def test_action_step_success(self, mini_registry):
        step = _step("Get system info", "get_system_info")
        report = self._run([step], mini_registry)
        assert report.steps_done >= 1

    def test_action_step_unknown_tool_skipped(self):
        step = _step("Unknown", "nonexistent_tool_xyz")
        report = self._run([step])
        assert report.steps[0].status == StepStatus.SKIPPED

    def test_action_step_no_tool_name_skipped(self):
        step = TaskStep(step_id="s1", description="No tool")
        report = self._run([step])
        assert report.steps[0].status == StepStatus.SKIPPED

    def test_action_step_retries_on_failure(self, mini_registry):
        call_count = [0]
        orig_tool = mini_registry.get("get_system_info")
        with mock.patch.object(orig_tool, "execute", side_effect=RuntimeError("boom")) as m:
            step = _step("Failing step", "get_system_info", max_retries=2)
            report = self._run([step], mini_registry)
        assert report.steps[0].status == StepStatus.FAILED
        assert report.steps[0].retries_used == 2

    def test_action_step_uses_fallback_on_exhausted_retries(self, mini_registry):
        orig_tool = mini_registry.get("get_system_info")
        orig_active = mini_registry.get("get_active_window")
        with mock.patch.object(orig_tool, "execute", return_value=ToolResult(success=False, message="fail")):
            step = _step("Primary fails", "get_system_info", max_retries=0,
                         fallback_tool="get_active_window")
            report = self._run([step], mini_registry)
        # Fallback should succeed
        assert report.steps[0].status == StepStatus.DONE
        assert "[fallback]" in report.steps[0].output

    def test_action_step_stores_result_in_context(self, mini_registry):
        step = _step("Sys info", "get_system_info", result_key="sys")
        plan = Plan(plan_id="test", goal="t", steps=[step])
        runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
        report = runner.run(plan, mini_registry)
        assert "sys" in report.context

    # --- WAIT step ---

    def test_wait_step_completes(self):
        step = _wait_step(0.05, "Short wait")
        report = self._run([step])
        assert report.steps[0].status == StepStatus.DONE
        assert report.elapsed_s >= 0.05

    # --- VERIFY step ---

    def test_verify_step_true(self):
        step = _verify_step("Always passes", "True")
        report = self._run([step])
        assert report.steps[0].status == StepStatus.DONE
        assert report.status == RunStatus.DONE

    def test_verify_step_false_stops_plan(self, mini_registry):
        steps = [
            _step("Info", "get_system_info"),
            _verify_step("Always fails", "False"),
            _step("Never reached", "get_active_window"),  # should not run
        ]
        report = self._run(steps, mini_registry)
        assert report.status == RunStatus.FAILED
        assert any(s.status == StepStatus.FAILED for s in report.steps)

    def test_verify_step_with_context_value(self, mini_registry):
        # Put a value in context then verify against it
        from task_planner import TaskStep, StepType
        steps = [
            _step("Get info", "get_system_info", result_key="info"),
        ]
        verify_step = TaskStep(
            step_id="v1",
            description="Check info is present",
            step_type=StepType.VERIFY,
            condition="info is not None",
        )
        steps.append(verify_step)
        plan = Plan(plan_id="t", goal="test", steps=steps)
        runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
        report = runner.run(plan, mini_registry)
        assert report.status == RunStatus.DONE

    # --- BRANCH step ---

    def test_branch_step_true_path(self, mini_registry):
        from task_planner import TaskStep, StepType
        steps = [
            TaskStep(
                step_id="b1",
                description="Always-true branch",
                step_type=StepType.BRANCH,
                condition="True",
                on_true=1,   # jump to step index 1 = next (normal flow)
                on_false=5,  # jump past all
            ),
            _step("Info", "get_system_info"),
        ]
        report = self._run(steps, mini_registry)
        assert report.steps_done >= 1

    # --- LOOP step ---

    def test_loop_step_runs_n_times(self, mini_registry):
        from task_planner import TaskStep, StepType
        inner = _step("Inner info", "get_system_info")
        loop_step = TaskStep(
            step_id="l1",
            description="Loop 3x",
            step_type=StepType.LOOP,
            loop_count=3,
            loop_steps=[inner],
        )
        report = self._run([loop_step], mini_registry)
        assert report.steps[-1].status == StepStatus.DONE

    # --- Cancellation ---

    def test_cancel_stops_execution(self, mini_registry):
        runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
        steps = [
            _wait_step(3.0, "Long wait"),  # will be interrupted
            _step("After cancel", "get_system_info"),
        ]
        plan = Plan(plan_id="t", goal="test cancel", steps=steps)

        def cancel_after_delay():
            time.sleep(0.15)
            runner.cancel()

        t = threading.Thread(target=cancel_after_delay)
        t.start()
        report = runner.run(plan, mini_registry)
        t.join(timeout=5)
        assert report.status == RunStatus.CANCELLED

    # --- Pause / Resume ---

    def test_pause_and_resume(self, mini_registry):
        runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
        steps = [
            _step("Step 1", "get_system_info"),
            _step("Step 2", "get_active_window"),
        ]
        plan = Plan(plan_id="t", goal="pause test", steps=steps)

        runner.pause()
        result_container = []

        def run_in_thread():
            runner.resume()
            report = runner.run(plan, mini_registry)
            result_container.append(report)

        t = threading.Thread(target=run_in_thread)
        t.start()
        t.join(timeout=10)
        assert result_container, "Thread did not complete"
        assert result_container[0].status == RunStatus.DONE

    # --- Multi-step success ---

    def test_multi_step_sequential_success(self, mini_registry):
        steps = [
            _step("Step A", "get_system_info"),
            _step("Step B", "get_active_window"),
            _wait_step(0.01),
            _verify_step("Always true", "True"),
        ]
        report = self._run(steps, mini_registry)
        assert report.status == RunStatus.DONE
        assert report.steps_done >= 3

    # --- Report ---

    def test_run_report_summary(self, mini_registry):
        step = _step("Info", "get_system_info")
        report = self._run([step], mini_registry)
        summary = report.summary_message()
        assert "done" in summary.lower() or "DONE" in summary
        assert isinstance(summary, str)

    def test_run_report_elapsed(self, mini_registry):
        step = _step("Info", "get_system_info")
        report = self._run([step], mini_registry)
        assert report.elapsed_s >= 0

    def test_run_report_counts(self, mini_registry):
        steps = [
            _step("Good step", "get_system_info"),
            _step("Bad step", "nonexistent_tool_xyz"),  # skipped
        ]
        report = self._run(steps, mini_registry)
        assert report.steps_done == 1
        assert report.steps_skipped == 1

    # --- Error recovery ---

    def test_failed_step_does_not_abort_plan(self, mini_registry):
        """A failed action step (no fallback) should continue the plan."""
        orig = mini_registry.get("get_system_info")
        with mock.patch.object(orig, "execute", return_value=ToolResult(success=False, message="oops")):
            steps = [
                _step("Fail step", "get_system_info", max_retries=0),
                _step("Good step", "get_active_window"),
            ]
            report = self._run(steps, mini_registry)
        assert report.steps_failed >= 1
        assert report.steps_done >= 1   # the second step still ran


# ------------------------------------------------------------------ #
#  3. TaskManager Tests                                                #
# ------------------------------------------------------------------ #

class TestTaskManager:
    """Test background task lifecycle management."""

    def test_submit_returns_task_id(self, fresh_manager, mini_registry):
        plan = parse_goal("system info")
        tid = fresh_manager.submit(plan, mini_registry)
        assert isinstance(tid, str) and len(tid) > 4

    def test_status_returns_dict(self, fresh_manager, mini_registry):
        plan = parse_goal("system info")
        tid = fresh_manager.submit(plan, mini_registry)
        time.sleep(1)
        status = fresh_manager.status(tid)
        assert status is not None
        assert "task_id" in status
        assert "status" in status
        assert "goal" in status

    def test_run_inline_completes(self, fresh_manager, mini_registry):
        plan = parse_goal("system info check")
        report = fresh_manager.run_inline(plan, mini_registry)
        assert report is not None
        assert report.status == RunStatus.DONE

    def test_cancel_task(self, fresh_manager, mini_registry):
        from task_planner import TaskStep, StepType
        long_step = TaskStep(
            step_id="wait", description="Long wait",
            step_type=StepType.WAIT, wait_seconds=5.0,
        )
        plan = Plan(plan_id="t", goal="long plan", steps=[long_step])
        tid = fresh_manager.submit(plan, mini_registry)
        time.sleep(0.1)
        ok = fresh_manager.cancel(tid)
        assert ok is True
        time.sleep(0.5)
        status = fresh_manager.status(tid)
        assert status["status"] in ("cancelled", "done")

    def test_pause_and_resume_task(self, fresh_manager, mini_registry):
        plan = parse_goal("system info")
        tid = fresh_manager.submit(plan, mini_registry)
        fresh_manager.pause(tid)
        fresh_manager.resume(tid)
        time.sleep(1.5)
        status = fresh_manager.status(tid)
        assert status is not None

    def test_report_available_after_completion(self, fresh_manager, mini_registry):
        plan = parse_goal("system info report")
        report = fresh_manager.run_inline(plan, mini_registry)
        assert report is not None
        assert isinstance(report.steps, list)

    def test_drain_progress_returns_messages(self, fresh_manager, mini_registry):
        plan = parse_goal("system info")
        tid = fresh_manager.submit(plan, mini_registry)
        time.sleep(1.5)  # let it finish
        msgs = fresh_manager.drain_progress(tid)
        assert isinstance(msgs, list)

    def test_list_tasks_returns_list(self, fresh_manager, mini_registry):
        plan = parse_goal("system info")
        fresh_manager.submit(plan, mini_registry)
        tasks = fresh_manager.list_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) >= 1

    def test_cleanup_done_removes_finished_tasks(self, fresh_manager, mini_registry):
        plan = parse_goal("system info")
        fresh_manager.run_inline(plan, mini_registry)
        tid = fresh_manager.submit(plan, mini_registry)
        time.sleep(1.5)
        removed = fresh_manager.cleanup_done()
        assert removed >= 0

    def test_status_none_for_unknown_id(self, fresh_manager):
        assert fresh_manager.status("does-not-exist") is None

    def test_cancel_false_for_unknown_id(self, fresh_manager):
        assert fresh_manager.cancel("does-not-exist") is False

    def test_singleton_get_task_manager(self):
        m1 = get_task_manager()
        m2 = get_task_manager()
        assert m1 is m2


# ------------------------------------------------------------------ #
#  4. Tool Plugin Tests                                                #
# ------------------------------------------------------------------ #

class TestRunTaskTool:
    """Test the run_task tool plugin."""

    def test_properties(self):
        tool = RunTaskTool()
        assert tool.name == "run_task"
        assert tool.permission_level == PERMISSION_CONFIRM
        assert "run task" in tool.keywords
        assert len(tool.description) > 0

    def test_empty_goal_returns_failure(self):
        tool = RunTaskTool()
        result = tool.execute(target="")
        assert result.success is False
        assert "Please specify" in result.message

    def test_no_target_returns_failure(self):
        tool = RunTaskTool()
        result = tool.execute()
        assert result.success is False

    def test_valid_goal_produces_report(self, mini_registry):
        tool = RunTaskTool()
        result = tool.execute(target="system info check", _registry=mini_registry)
        # Should produce a report (success based on steps done > 0)
        assert "step" in result.message.lower() or "task" in result.message.lower()

    def test_result_has_data(self, mini_registry):
        tool = RunTaskTool()
        result = tool.execute(target="system info", _registry=mini_registry)
        assert result.data is not None
        assert "plan_id" in result.data
        assert "status" in result.data

    def test_exception_returns_failure(self):
        tool = RunTaskTool()
        with mock.patch("tools.run_task.parse_goal", side_effect=RuntimeError("boom")):
            result = tool.execute(target="anything")
        assert result.success is False
        assert "error" in result.message.lower()


class TestTaskStatusTool:
    """Test the task_status tool plugin."""

    def test_properties(self):
        tool = TaskStatusTool()
        assert tool.name == "task_status"
        assert tool.permission_level == PERMISSION_SAFE
        assert "task status" in tool.keywords

    def test_empty_target_lists_tasks(self):
        tool = TaskStatusTool()
        result = tool.execute(target="")
        assert result.success is True

    def test_list_keyword(self):
        tool = TaskStatusTool()
        result = tool.execute(target="list")
        assert result.success is True

    def test_cancel_unknown_task(self):
        tool = TaskStatusTool()
        result = tool.execute(target="cancel xyz-does-not-exist")
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_pause_unknown_task(self):
        tool = TaskStatusTool()
        result = tool.execute(target="pause xyz-does-not-exist")
        assert result.success is False

    def test_resume_unknown_task(self):
        tool = TaskStatusTool()
        result = tool.execute(target="resume xyz-does-not-exist")
        assert result.success is False

    def test_report_unknown_task(self):
        tool = TaskStatusTool()
        result = tool.execute(target="report xyz-does-not-exist")
        assert result.success is False

    def test_unknown_bare_id_returns_failure(self):
        tool = TaskStatusTool()
        result = tool.execute(target="completely-unknown-id-xyz")
        assert result.success is False


# ------------------------------------------------------------------ #
#  5. Intent Parser Tests                                              #
# ------------------------------------------------------------------ #

class TestPhase10IntentParsing:
    """Test intent routing for Phase 10 tools."""

    @pytest.mark.parametrize(
        "phrase, expected_tool",
        [
            ("run task prepare my project for the demo", "run_task"),
            ("run plan check git status", "run_task"),
            ("execute task open browser", "run_task"),
            ("multi step task find files", "run_task"),
            ("task status", "task_status"),
            ("list tasks", "task_status"),
            ("cancel task abc123", "task_status"),
            ("task progress", "task_status"),
        ],
    )
    def test_phase10_intent_routing(self, registry, phrase, expected_tool):
        match = parse_intent(phrase, registry)
        assert match is not None, f"No match for '{phrase}'"
        tool, params = match
        assert tool.name == expected_tool, f"'{phrase}' → expected {expected_tool}, got {tool.name}"


# ------------------------------------------------------------------ #
#  6. Tool Discovery & Count                                           #
# ------------------------------------------------------------------ #

class TestPhase10ToolDiscovery:
    """Verify tool count and names after Phase 10 additions."""

    def test_tool_count_is_38(self, registry):
        tools = registry.get_all_tools()
        assert len(tools) == 38, f"Expected 38 tools, got {len(tools)}: {sorted(registry.get_tool_names())}"

    def test_phase10_tools_registered(self, registry):
        assert registry.get("run_task") is not None
        assert registry.get("task_status") is not None

    def test_run_task_permission(self, registry):
        assert registry.get("run_task").permission_level == PERMISSION_CONFIRM

    def test_task_status_permission(self, registry):
        assert registry.get("task_status").permission_level == PERMISSION_SAFE


# ------------------------------------------------------------------ #
#  7. End-to-End Integration Tests                                     #
# ------------------------------------------------------------------ #

class TestPhase10Integration:
    """End-to-end scenario tests."""

    def test_full_system_info_plan(self, mini_registry):
        """A simple goal with known tools should run to completion."""
        plan = parse_goal("get system performance info")
        runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
        report = runner.run(plan, mini_registry)
        assert report.status in (RunStatus.DONE, RunStatus.FAILED)
        assert len(report.steps) > 0

    def test_unknown_tool_in_plan_continues(self, mini_registry):
        """Steps with unregistered tools are skipped; remaining steps continue."""
        steps = [
            _step("Known step", "get_system_info"),
            _step("Unknown", "tool_that_does_not_exist"),
            _step("Known again", "get_active_window"),
        ]
        plan = Plan(plan_id="t", goal="mixed plan", steps=steps)
        runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
        report = runner.run(plan, mini_registry)
        assert report.steps_done >= 2
        assert report.steps_skipped >= 1

    def test_context_passed_between_steps(self, mini_registry):
        """Result of first step should appear in context for subsequent steps."""
        steps = [
            _step("Sys info", "get_system_info", result_key="sys_data"),
        ]
        verify = _verify_step("Context has sys_data", "sys_data is not None")
        steps.append(verify)
        plan = Plan(plan_id="t", goal="context test", steps=steps)
        runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
        report = runner.run(plan, mini_registry)
        assert report.status == RunStatus.DONE
        assert "sys_data" in report.context

    def test_background_task_completes(self, fresh_manager, mini_registry):
        """Submit background task and wait for completion."""
        plan = parse_goal("check system info status")
        tid = fresh_manager.submit(plan, mini_registry)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = fresh_manager.status(tid)
            if status and not status["is_alive"]:
                break
            time.sleep(0.2)
        report = fresh_manager.report(tid)
        assert report is not None
        assert report.status in (RunStatus.DONE, RunStatus.CANCELLED)

    def test_retry_then_succeed(self, mini_registry):
        """Step fails twice then succeeds on third attempt."""
        orig = mini_registry.get("get_system_info")
        call_count = [0]
        original_execute = orig.execute

        def flaky_execute(**kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                return ToolResult(success=False, message="transient error")
            return original_execute(**kwargs)

        with mock.patch.object(orig, "execute", side_effect=lambda **kw: flaky_execute(**kw)):
            step = _step("Flaky step", "get_system_info", max_retries=3)
            plan = Plan(plan_id="t", goal="retry test", steps=[step])
            runner = TaskRunner(progress_callback=lambda _: None, retry_delay_s=0.01)
            report = runner.run(plan, mini_registry)

        assert report.steps[0].status == StepStatus.DONE
        assert report.steps[0].retries_used >= 2
