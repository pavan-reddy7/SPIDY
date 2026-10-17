# src/tools/web_search.py
"""
Tool: Web Search

Searches the web using Google via the Playwright browser.

Security:
- Requires user confirmation (PERMISSION_CONFIRM).
- Uses an isolated browser profile (managed by BrowserSession).
- No credentials stored.
"""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tool_base import Tool, ToolResult, PERMISSION_CONFIRM
from browser_session import BrowserSession, PLAYWRIGHT_AVAILABLE, MAX_PAGE_TEXT


class WebSearchTool(Tool):
    """Searches the web and returns top results."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        if not PLAYWRIGHT_AVAILABLE:
            return "Search the web (requires: pip install playwright && playwright install chromium)"
        return "Search the web using Google and display top results."

    @property
    def permission_level(self) -> str:
        return PERMISSION_CONFIRM

    @property
    def keywords(self) -> list[str]:
        return [
            "search the web", "web search", "google",
            "search online", "look up online", "bing search",
        ]

    def execute(self, **params) -> ToolResult:
        query = params.get("target", "").strip()

        if not query:
            return ToolResult(
                success=False,
                message=(
                    "Please specify what to search for.\n"
                    "Example: search the web latest Python release"
                ),
            )

        if not PLAYWRIGHT_AVAILABLE:
            return ToolResult(
                success=False,
                message=(
                    "Playwright is not installed.\n"
                    "Install with:\n"
                    "  pip install playwright\n"
                    "  playwright install chromium"
                ),
            )

        session = BrowserSession.get()

        try:
            page = session.ensure_browser()

            # Navigate to Google search
            search_url = (
                "https://www.google.com/search?q="
                + urllib.parse.quote_plus(query)
            )
            page.goto(search_url, timeout=15_000)
            page.wait_for_load_state("domcontentloaded")

            # Extract search results from Google result blocks
            results: list[str] = []
            try:
                # Google wraps each result in a div.g element
                elements = page.query_selector_all("div.g")
                for i, el in enumerate(elements[:5]):
                    text = el.inner_text().strip()
                    if text:
                        # Truncate long snippets
                        snippet = text[:300] + ("..." if len(text) > 300 else "")
                        results.append(f"{i + 1}. {snippet}")
            except Exception:
                pass

            if results:
                body = "\n\n".join(results)
                message = f"Search results for '{query}':\n\n{body}"
            else:
                # Fallback: grab raw page text
                try:
                    body_text = page.inner_text("body")[:MAX_PAGE_TEXT]
                except Exception:
                    body_text = "(could not extract page text)"
                message = f"Search results for '{query}':\n\n{body_text}"

            return ToolResult(
                success=True,
                message=message,
                data={
                    "query": query,
                    "url": page.url,
                    "results_count": len(results),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Error searching the web: {e}",
            )
