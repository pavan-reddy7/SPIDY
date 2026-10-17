# src/browser_session.py
"""
Browser Session Manager for SPIDY.

Provides a singleton Playwright browser instance that persists across
tool calls within a session. Uses Chromium by default with a fresh
profile for isolation.

Dependencies:
    pip install playwright
    playwright install chromium
"""

import os
import sys

# Graceful import — tools check ``PLAYWRIGHT_AVAILABLE`` at runtime.
try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Safety caps
MAX_PAGE_TEXT = 5000          # chars returned by read_page
DEFAULT_TIMEOUT_MS = 15_000   # navigation timeout
ELEMENT_TIMEOUT_MS = 5_000    # click / fill timeout


class BrowserSession:
    """
    Singleton that owns the Playwright runtime, browser, context, and page.

    Usage::

        session = BrowserSession.get()
        page = session.ensure_browser()   # lazy-start
        page.goto("https://example.com")
        ...
        session.close()                   # optional cleanup
    """

    _instance: "BrowserSession | None" = None

    # ------------------------------------------------------------------ #
    #  Singleton access                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def get(cls) -> "BrowserSession":
        """Return the singleton session (create shell if needed)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def is_active(cls) -> bool:
        """True when a browser is currently running."""
        return cls._instance is not None and cls._instance._browser is not None

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def ensure_browser(self):
        """Lazy-start the browser and return the active Page."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed.\n"
                "Install with:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        if self._page is not None and not self._page.is_closed():
            return self._page

        # Start Playwright runtime
        self._pw = sync_playwright().start()

        # Launch Chromium (visible window so user can see what SPIDY does)
        self._browser = self._pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # Fresh context = isolated profile (cookies, storage, etc.)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        self._context.set_default_timeout(DEFAULT_TIMEOUT_MS)

        self._page = self._context.new_page()
        return self._page

    # ------------------------------------------------------------------ #
    #  Convenience properties                                              #
    # ------------------------------------------------------------------ #

    @property
    def page(self):
        return self._page

    @property
    def current_url(self) -> str | None:
        if self._page and not self._page.is_closed():
            return self._page.url
        return None

    @property
    def current_title(self) -> str | None:
        if self._page and not self._page.is_closed():
            try:
                return self._page.title()
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #

    def close(self):
        """Shut down everything and reset the singleton."""
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
        except Exception:
            pass
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        BrowserSession._instance = None
