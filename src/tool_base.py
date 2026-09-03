# src/tool_base.py
"""
Base tool infrastructure for SPIDY.

Provides:
- ToolResult: standardized result container
- Tool: abstract base class for all tools
- ToolRegistry: auto-discovers and manages tools
"""

import importlib
import importlib.util
import inspect
import os
import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# Permission levels (enforced by application code, NOT by the LLM)
PERMISSION_SAFE = "SAFE"           # No confirmation needed
PERMISSION_CONFIRM = "CONFIRM"     # Requires user confirmation
PERMISSION_HIGH_RISK = "HIGH_RISK" # Requires explicit high-risk confirmation
PERMISSION_BLOCKED = "BLOCKED"     # Never allowed


@dataclass
class ToolResult:
    """Standardized result from a tool execution."""
    success: bool
    message: str
    data: dict | None = field(default=None)

    def __str__(self) -> str:
        return self.message


class Tool(ABC):
    """
    Abstract base class for all SPIDY tools.

    Every tool must declare:
    - name: unique identifier (e.g. "open_application")
    - description: human-readable description
    - permission_level: one of SAFE, CONFIRM, HIGH_RISK, BLOCKED
    - keywords: list of phrases that trigger this tool
    - execute(**params) -> ToolResult
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...

    @property
    @abstractmethod
    def permission_level(self) -> str:
        """Permission level: SAFE, CONFIRM, HIGH_RISK, BLOCKED."""
        ...

    @property
    @abstractmethod
    def keywords(self) -> list[str]:
        """
        List of keyword phrases that map to this tool.
        The intent parser uses these for matching.
        """
        ...

    @abstractmethod
    def execute(self, **params) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...

    def __repr__(self) -> str:
        return f"<Tool: {self.name} [{self.permission_level}]>"


class ToolRegistry:
    """
    Registry that discovers, stores, and looks up tools.

    Tools are auto-discovered from a 'tools/' directory:
    any Python file in that directory that contains a class
    inheriting from Tool will be registered automatically.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        """Get all registered tool names."""
        return list(self._tools.keys())

    def discover(self, tools_dir: str | pathlib.Path) -> int:
        """
        Auto-discover and register tools from a directory.

        Scans all .py files in the directory for classes that
        inherit from Tool and instantiates them.

        Returns the number of tools discovered.
        """
        tools_dir = pathlib.Path(tools_dir)
        if not tools_dir.is_dir():
            return 0

        count = 0
        for py_file in sorted(tools_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception:
                continue

            # Find all Tool subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (inspect.isclass(attr)
                        and issubclass(attr, Tool)
                        and attr is not Tool
                        and not inspect.isabstract(attr)):
                    try:
                        tool_instance = attr()
                        self.register(tool_instance)
                        count += 1
                    except Exception:
                        continue

        return count
