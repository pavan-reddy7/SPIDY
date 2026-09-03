# src/intent_parser.py
"""
Intent parser for SPIDY.

Parses natural-language user input and matches it to a registered tool,
extracting any parameters from the text.

Key design:
- All matching is case-insensitive.
- Longer keyword matches are preferred (more specific wins).
- Matched keyword is always passed as params['_keyword'] so tools know
  which phrase triggered them.
- "open <known-folder>" routes to open_folder, not open_application,
  because open_folder registers those keywords with longer match lengths.
"""

from tool_base import Tool, ToolRegistry


# Verbs that can precede a tool keyword
# NOTE: do NOT add close/minimize/maximize here — they are window action
# keywords in their own right, not generic verb prefixes. If they were
# ACTION_VERBS they would match app names via verb+keyword and steal
# routing from window_management.
ACTION_VERBS = [
    "open", "launch", "start", "run",
    "show", "get", "list",
    "tell me", "check", "what's", "whats",
    "what are",
]


def parse_intent(text: str, registry: ToolRegistry) -> tuple[Tool, dict] | None:
    """
    Match user text to a registered tool.

    Returns (Tool, params_dict) or None if no match.
    """
    # Normalise — collapse smart-quotes and extra whitespace
    cleaned = (
        text.strip()
        .lower()
        .replace("\u2019", "'")   # right single quote → apostrophe
        .replace("\u2018", "'")   # left single quote → apostrophe
    )
    if not cleaned:
        return None

    best_match: tuple[Tool, dict, int] | None = None  # (tool, params, keyword_length)

    for tool in registry.get_all_tools():
        for keyword in tool.keywords:
            kw = keyword.lower()
            match_result = _try_match(cleaned, kw, tool)
            if match_result is not None:
                tool_obj, params, kw_len = match_result
                # Prefer longer keyword matches (more specific wins)
                if best_match is None or kw_len > best_match[2]:
                    best_match = (tool_obj, params, kw_len)

    if best_match:
        return (best_match[0], best_match[1])
    return None


def _try_match(cleaned: str, keyword: str, tool: Tool) -> tuple[Tool, dict, int] | None:
    """
    Try to match cleaned input text against a keyword for a tool.
    Returns (tool, params, keyword_length) or None.
    """
    # Direct exact match: "system info"
    if cleaned == keyword:
        return (tool, {"_keyword": keyword}, len(keyword))

    # Verb + keyword: "get system info", "show system info"
    for verb in ACTION_VERBS:
        phrase = f"{verb} {keyword}"

        if cleaned == phrase:
            return (tool, {"_keyword": keyword}, len(keyword))

        # Verb + keyword + trailing parameter: "list files in C:\Users"
        if cleaned.startswith(phrase + " "):
            remainder = cleaned[len(phrase):].strip()
            params = _extract_params(remainder)
            params["_keyword"] = keyword
            return (tool, params, len(keyword))

    # Keyword + trailing parameter: "open folder C:\SPIDY"
    if cleaned.startswith(keyword + " "):
        remainder = cleaned[len(keyword):].strip()
        params = _extract_params(remainder)
        params["_keyword"] = keyword
        return (tool, params, len(keyword))

    # Keyword + colon + trailing parameter: "remember this: my name is Pavan"
    if cleaned.startswith(keyword + ":"):
        remainder = cleaned[len(keyword) + 1:].strip()
        params = _extract_params(remainder)
        params["_keyword"] = keyword
        return (tool, params, len(keyword))

    return None


def _extract_params(remainder: str) -> dict:
    """
    Extract parameters from the remaining text after intent matching.
    Strips common filler words at the start.
    """
    params: dict = {}
    if not remainder:
        return params

    # Strip common filler words from the front
    filler = {"in", "at", "of", "the", "my", "from", "to", "on", "folder", "directory"}
    words = remainder.split()
    while words and words[0].lower() in filler:
        words.pop(0)

    remaining = " ".join(words).strip()
    if remaining:
        params["target"] = remaining

    return params
