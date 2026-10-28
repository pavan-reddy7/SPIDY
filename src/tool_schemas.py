# src/tool_schemas.py
"""
SPIDY Tool Schemas for LLM Function Calling

Converts SPIDY's 38 registered tools into standardized LLM FunctionDeclarations
for Google Gemini API and other LLM function calling providers.
"""

from typing import Any
from tool_base import ToolRegistry

try:
    from google.genai import types
    GENAI_TYPES_AVAILABLE = True
except ImportError:
    GENAI_TYPES_AVAILABLE = False


# Explicit parameter hints for core tools to improve LLM accuracy
TOOL_PARAM_HINTS = {
    "open_application": {
        "properties": {
            "target": {"type": "STRING", "description": "Application to open (e.g. notepad, chrome, vscode, calculator, spotify, terminal)"}
        },
        "required": ["target"],
    },
    "open_folder": {
        "properties": {
            "target": {"type": "STRING", "description": "Folder to open (e.g. Desktop, Downloads, Documents, Projects)"}
        },
        "required": ["target"],
    },
    "web_search": {
        "properties": {
            "query": {"type": "STRING", "description": "Search query or question to search on Google"}
        },
        "required": ["query"],
    },
    "read_file": {
        "properties": {
            "target": {"type": "STRING", "description": "Path or name of the file to read"}
        },
        "required": ["target"],
    },
    "create_file": {
        "properties": {
            "target": {"type": "STRING", "description": "Path or name of the file to create"},
            "content": {"type": "STRING", "description": "Text content to write to the file"}
        },
        "required": ["target"],
    },
    "delete_file": {
        "properties": {
            "target": {"type": "STRING", "description": "Path or name of the file to delete"}
        },
        "required": ["target"],
    },
    "list_directory": {
        "properties": {
            "target": {"type": "STRING", "description": "Directory path to list (e.g. C:\\SPIDY, Desktop, Downloads)"}
        },
        "required": [],
    },
    "find_files": {
        "properties": {
            "target": {"type": "STRING", "description": "Filename pattern to search for (e.g. *.py, report.docx)"}
        },
        "required": ["target"],
    },
    "search_contents": {
        "properties": {
            "query": {"type": "STRING", "description": "Text to search inside files"},
            "target": {"type": "STRING", "description": "Root path to search inside (optional)"}
        },
        "required": ["query"],
    },
    "screenshot": {
        "properties": {
            "target": {"type": "STRING", "description": "'full' for desktop screenshot or 'window' for active window"}
        },
        "required": [],
    },
    "read_screen": {
        "properties": {
            "target": {"type": "STRING", "description": "'full' or 'window' to extract text via OCR"}
        },
        "required": [],
    },
    "describe_screen": {
        "properties": {},
        "required": [],
    },
    "find_on_screen": {
        "properties": {
            "target": {"type": "STRING", "description": "Text or UI button to find on screen"}
        },
        "required": ["target"],
    },
    "open_browser": {
        "properties": {
            "target": {"type": "STRING", "description": "URL to navigate to (optional)"}
        },
        "required": [],
    },
    "navigate_url": {
        "properties": {
            "target": {"type": "STRING", "description": "URL to navigate to (e.g. https://google.com)"}
        },
        "required": ["target"],
    },
    "remember": {
        "properties": {
            "target": {"type": "STRING", "description": "Fact or memory to store for the user"}
        },
        "required": ["target"],
    },
    "recall": {
        "properties": {
            "query": {"type": "STRING", "description": "Topic or keyword to recall from memory"}
        },
        "required": ["query"],
    },
    "ask_documents": {
        "properties": {
            "query": {"type": "STRING", "description": "Question to answer from indexed personal documents"}
        },
        "required": ["query"],
    },
    "index_documents": {
        "properties": {
            "target": {"type": "STRING", "description": "File or folder path to index into RAG database"}
        },
        "required": ["target"],
    },
    "run_task": {
        "properties": {
            "goal": {"type": "STRING", "description": "Multi-step goal to plan and execute autonomously"}
        },
        "required": ["goal"],
    },
    "window_management": {
        "properties": {
            "action": {"type": "STRING", "description": "Action: 'minimize', 'maximize', 'restore', 'focus', 'list'"},
            "target": {"type": "STRING", "description": "Title or partial name of the target window"}
        },
        "required": ["action"],
    },
}


def build_genai_tool_declarations(registry: ToolRegistry) -> list[Any]:
    """Convert all tools in ToolRegistry to google.genai FunctionDeclarations."""
    if not GENAI_TYPES_AVAILABLE:
        return []

    declarations = []
    tools = registry.get_all_tools()

    for tool in tools:
        hint = TOOL_PARAM_HINTS.get(tool.name, {})
        props_dict = {}

        if hint and "properties" in hint:
            for p_name, p_info in hint["properties"].items():
                props_dict[p_name] = types.Schema(
                    type=types.Type.STRING,
                    description=p_info.get("description", p_name)
                )
            required_fields = hint.get("required", [])
        else:
            # Default schema for tools without specific hints
            props_dict["target"] = types.Schema(
                type=types.Type.STRING,
                description="Target argument, file path, application name, or query parameter"
            )
            required_fields = []

        schema = types.Schema(
            type=types.Type.OBJECT,
            properties=props_dict,
            required=required_fields,
        )

        # Sanitize description
        desc = tool.description.replace("\n", " ").strip()
        if len(desc) > 300:
            desc = desc[:297] + "..."

        func = types.FunctionDeclaration(
            name=tool.name,
            description=desc,
            parameters=schema,
        )
        declarations.append(func)

    return declarations


def adapt_tool_params(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM function arguments into SPIDY's expected tool parameters."""
    normalized = dict(params)

    # Some tools use 'query', 'goal', 'path', 'app_name' interchangeably with 'target'
    if "goal" in normalized and "target" not in normalized:
        normalized["target"] = normalized["goal"]
    if "query" in normalized and "target" not in normalized:
        normalized["target"] = normalized["query"]
    if "path" in normalized and "target" not in normalized:
        normalized["target"] = normalized["path"]
    if "app_name" in normalized and "target" not in normalized:
        normalized["target"] = normalized["app_name"]

    # Provide _keyword
    if "_keyword" not in normalized:
        normalized["_keyword"] = tool_name

    return normalized

