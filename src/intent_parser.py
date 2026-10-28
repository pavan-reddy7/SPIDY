# src/intent_parser.py
"""
Intent parser for SPIDY.

Parses natural-language user input and matches it to a registered tool,
extracting any parameters from the text.

Key design:
- All matching is case-insensitive (small, CAPITAL, Title Case).
- Supports commands with underscores (speech_to_text, open_browser),
  with spaces (speech to text, open browser), or hyphens.
- Automatically incorporates canonical tool names, space/underscore variants,
  and stripped 'get_' names so every command works seamlessly.
- Longer keyword matches are preferred (more specific wins).
- Matched keyword is always passed as params['_keyword'] so tools know
  which phrase triggered them.
- "open <known-folder>" routes to open_folder, not open_application,
  because open_folder registers those keywords with longer match lengths.
"""

import re
from tool_base import Tool, ToolRegistry


def _replace_smart_quotes(s: str) -> str:
    """Replace smart quotes with plain ASCII quotes."""
    return s.replace("\u2019", "'").replace("\u2018", "'")


# Verbs that can precede a tool keyword
ACTION_VERBS = [
    "open", "launch", "start", "run",
    "show", "get", "list",
    "tell me", "check", "what's", "whats",
    "what are",
]


def _normalize_tokens(s: str) -> list[str]:
    """Extract individual words/tokens, splitting on whitespace, underscores, hyphens."""
    return [part for part in re.split(r'[\s_\-]+', s) if part]


def _get_registry_index(registry: ToolRegistry) -> dict:
    """Build or retrieve cached intent matching index for the tool registry."""
    tools = registry.get_all_tools()
    cached = getattr(registry, "_intent_index", None)
    if cached is not None and cached.get("tool_count") == len(tools):
        return cached

    direct_map: dict[tuple[str, ...], list[tuple[Tool, str, int]]] = {}
    for tool in tools:
        phrases: set[str] = set()
        for kw in tool.keywords:
            kw_clean = kw.strip()
            if kw_clean:
                phrases.add(kw_clean)
                phrases.add(kw_clean.replace('_', ' '))
                phrases.add(kw_clean.replace(' ', '_'))

        name = tool.name
        phrases.add(name)
        phrases.add(name.replace('_', ' '))
        phrases.add(name.replace(' ', '_'))

        if name.startswith('get_'):
            stripped = name[4:]
            phrases.add(stripped)
            phrases.add(stripped.replace('_', ' '))
            phrases.add(stripped.replace(' ', '_'))

        for p in phrases:
            toks = tuple(t.lower() for t in _normalize_tokens(p))
            if not toks:
                continue
            if toks not in direct_map:
                direct_map[toks] = []
            direct_map[toks].append((tool, p, len(p)))

    for toks in direct_map:
        direct_map[toks].sort(key=lambda item: item[2], reverse=True)

    verb_tokens = [tuple(t.lower() for t in _normalize_tokens(v)) for v in ACTION_VERBS]
    verb_tokens.sort(key=lambda v: len(v), reverse=True)

    index = {
        "tool_count": len(tools),
        "direct_map": direct_map,
        "verb_tokens": verb_tokens,
    }
    registry._intent_index = index
    return index


def parse_intent(text: str, registry: ToolRegistry) -> tuple[Tool, dict] | None:
    """
    Match user text to a registered tool.
    Accepts uppercase, lowercase, mixed case, underscores, spaces, or hyphens.
    Returns (Tool, params_dict) or None if no match.
    """
    orig = text.strip()
    orig_no_smart = _replace_smart_quotes(orig)
    if not orig_no_smart:
        return None

    # Find token spans in orig_no_smart
    matches = list(re.finditer(r'[^\s_:\-]+', orig_no_smart))
    if not matches:
        return None

    tokens = [m.group(0).lower() for m in matches]
    total_tokens = len(tokens)

    index = _get_registry_index(registry)
    direct_map = index["direct_map"]
    verb_tokens = index["verb_tokens"]

    best_match: tuple[Tool, dict, tuple[int, int]] | None = None  # (tool, params, score)

    # 1. Direct match (e.g. "speech_to_text", "speech to text", "open_browser")
    for n in range(total_tokens, 0, -1):
        sub_toks = tuple(tokens[:n])
        if sub_toks in direct_map:
            tool, orig_kw, _ = direct_map[sub_toks][0]
            end_pos = matches[n - 1].end()
            rest = orig_no_smart[end_pos:].lstrip(' :_\t-')
            params = _extract_params(rest)
            params['_keyword'] = orig_kw
            score = (n, end_pos)
            if best_match is None or score > best_match[2]:
                best_match = (tool, params, score)
            break

    # 2. Verb + keyword match (e.g. "open notepad", "get system info", "launch chrome")
    for vtoks in verb_tokens:
        vlen = len(vtoks)
        if total_tokens > vlen and tuple(tokens[:vlen]) == vtoks:
            sub_input_toks = tokens[vlen:]
            sub_matches = matches[vlen:]
            sub_count = len(sub_input_toks)
            for n in range(sub_count, 0, -1):
                sub_toks = tuple(sub_input_toks[:n])
                if sub_toks in direct_map:
                    tool, orig_kw, _ = direct_map[sub_toks][0]
                    end_pos = sub_matches[n - 1].end()
                    rest = orig_no_smart[end_pos:].lstrip(' :_\t-')
                    params = _extract_params(rest)
                    params['_keyword'] = orig_kw
                    score = (vlen + n, end_pos)
                    if best_match is None or score > best_match[2]:
                        best_match = (tool, params, score)
                    break

    if best_match:
        return (best_match[0], best_match[1])
    return None


def _extract_params(remainder: str) -> dict:
    """
    Extract parameters from the remaining text after intent matching.
    Strips common filler words at the start.
    """
    params: dict = {}
    if not remainder:
        return params

    filler = {"in", "at", "of", "the", "my", "from", "to", "on", "folder", "directory"}
    words = remainder.split()
    while words and words[0].lower() in filler:
        words.pop(0)

    remaining = " ".join(words).strip()
    if remaining:
        params["target"] = remaining

    return params
