"""Web search tool using DuckDuckGo HTML (httpx only, no urllib)."""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any, Dict, List, Optional

# Absolute ban on urllib — implement minimal query encoding ourselves.
from ....interfaces.tools import Tool, ToolResult
from ....interfaces.settings_schema import SettingsSchema, SettingField, SettingType

logger = logging.getLogger(__name__)


def _url_encode(s: str) -> str:
    """Minimal URL query encoding without urllib."""
    out = []
    for ch in s:
        o = ord(ch)
        if (
            (48 <= o <= 57)
            or (65 <= o <= 90)
            or (97 <= o <= 122)
            or ch in "-_.~"
        ):
            out.append(ch)
        elif ch == " ":
            out.append("+")
        else:
            out.append(f"%{o:02X}")
    return "".join(out)


class WebSearchTool(Tool):
    def __init__(self):
        self.cfg_collapsible = True

    @property
    def category(self) -> str:
        return "web"

    @property
    def pack_id(self) -> str:
        return "web"

    @property
    def ui_icon(self) -> str:
        return "🔍"

    @property
    def collapsible(self) -> bool:
        return bool(getattr(self, "cfg_collapsible", True))

    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        return f"{count} поисков"

    def settings_schema(self):
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(key="max_results", label="Default max results", type=SettingType.INT, default=5, minimum=1, maximum=20),
                SettingField(key="timeout", label="Timeout (sec)", type=SettingType.FLOAT, default=15.0, minimum=1, maximum=120),
            ],
        )

    def apply_settings(self, values):
        if not values:
            return
        if "max_results" in values:
            self.max_results = int(values["max_results"])
        if "timeout" in values:
            self.timeout = float(values["timeout"])

    """Search the web via DuckDuckGo HTML endpoint and optional page fetch."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_results: int = 5,
        timeout: float = 20.0,
        user_agent: str = "AgentPlatform/0.1 (web_search)",
    ):
        self.enabled = enabled
        self.max_results = max_results
        self.timeout = timeout
        self.user_agent = user_agent

    @property
    def tool_id(self) -> str:
        return "web_search"

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the internet for information. Returns titles, URLs and snippets. "
            "Use when you need up-to-date facts, docs, or external knowledge."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        if not self.enabled:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                output=None,
                human_readable="Web search is disabled in tool settings.",
                error="DISABLED",
            )

        query = (arguments.get("query") or "").strip()
        if not query:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                output=None,
                human_readable="Empty search query",
                error="VALIDATION",
            )

        max_results = int(arguments.get("max_results") or self.max_results)
        max_results = max(1, min(max_results, 10))

        try:
            import httpx
        except ImportError:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                output=None,
                human_readable="httpx is required for web search",
                error="DEPENDENCY",
            )

        url = f"https://html.duckduckgo.com/html/?q={_url_encode(query)}"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            logger.warning("Web search failed: %s", e)
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                output=None,
                human_readable=f"Web search request failed: {e}",
                error="NETWORK",
            )

        results = self._parse_ddg_html(html, max_results)
        if not results:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"query": query, "results": []},
                human_readable=f"No results found for: {query}",
            )

        lines = [f"Search results for '{query}':"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   URL: {r['url']}")
            if r.get("snippet"):
                lines.append(f"   {r['snippet']}")
        return ToolResult(
            tool_call_id=call_id,
            tool_id=self.tool_id,
            status="success",
            output={"query": query, "results": results},
            human_readable="\n".join(lines),
        )

    def _parse_ddg_html(self, html: str, limit: int) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        # DuckDuckGo HTML result blocks
        pattern = re.compile(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
            re.DOTALL | re.IGNORECASE,
        )
        for m in pattern.finditer(html):
            href = unescape(m.group(1))
            title = re.sub(r"<[^>]+>", "", unescape(m.group(2))).strip()
            snippet = re.sub(r"<[^>]+>", "", unescape(m.group(3))).strip()
            # DDG sometimes wraps redirects
            if "uddg=" in href:
                # extract uddg= parameter value
                um = re.search(r"uddg=([^&]+)", href)
                if um:
                    href = self._pct_decode(um.group(1))
            if not title:
                continue
            results.append({"title": title, "url": href, "snippet": snippet})
            if len(results) >= limit:
                break

        if results:
            return results

        # Fallback simpler pattern
        simple = re.compile(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        for m in simple.finditer(html):
            href = unescape(m.group(1))
            title = re.sub(r"<[^>]+>", "", unescape(m.group(2))).strip()
            if "uddg=" in href:
                um = re.search(r"uddg=([^&]+)", href)
                if um:
                    href = self._pct_decode(um.group(1))
            if title:
                results.append({"title": title, "url": href, "snippet": ""})
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _pct_decode(s: str) -> str:
        """Percent-decode without urllib."""
        out = []
        i = 0
        while i < len(s):
            if s[i] == "%" and i + 2 < len(s):
                try:
                    out.append(chr(int(s[i + 1 : i + 3], 16)))
                    i += 3
                    continue
                except ValueError:
                    pass
            elif s[i] == "+":
                out.append(" ")
                i += 1
                continue
            out.append(s[i])
            i += 1
        return "".join(out)


class FetchUrlTool(Tool):
    def __init__(self):
        self.cfg_collapsible = True

    @property
    def category(self) -> str:
        return "web"

    @property
    def pack_id(self) -> str:
        return "web"

    @property
    def ui_icon(self) -> str:
        return "🔗"

    @property
    def collapsible(self) -> bool:
        return bool(getattr(self, "cfg_collapsible", True))

    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        return f"{count} ссылок"

    def settings_schema(self):
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(key="timeout", label="Timeout (sec)", type=SettingType.FLOAT, default=20.0, minimum=1, maximum=120),
                SettingField(key="max_bytes", label="Max download bytes", type=SettingType.INT, default=500000, minimum=1000, maximum=10_000_000),
            ],
        )

    def apply_settings(self, values):
        if not values:
            return
        if "timeout" in values:
            self.timeout = float(values["timeout"])
        if "max_bytes" in values:
            self.max_bytes = int(values["max_bytes"])

    """Fetch text content from a public URL (http/https)."""

    def __init__(self, *, enabled: bool = True, timeout: float = 20.0, max_bytes: int = 100_000):
        self.enabled = enabled
        self.timeout = timeout
        self.max_bytes = max_bytes

    @property
    def tool_id(self) -> str:
        return "fetch_url"

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return "Fetches text/HTML content from an http(s) URL for reading documentation or pages."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_bytes": {"type": "integer", "default": 100000},
            },
            "required": ["url"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        if not self.enabled:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                output=None,
                human_readable="fetch_url is disabled in tool settings.",
                error="DISABLED",
            )
        url = (arguments.get("url") or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                output=None,
                human_readable="Only http(s) URLs are allowed",
                error="VALIDATION",
            )
        max_bytes = int(arguments.get("max_bytes") or self.max_bytes)
        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True
            ) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "AgentPlatform/0.1 (fetch_url)"},
                )
                resp.raise_for_status()
                raw = resp.content[:max_bytes]
                text = raw.decode(resp.encoding or "utf-8", errors="replace")
                # Strip scripts/styles roughly
                text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
                text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
                text = re.sub(r"(?is)<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > max_bytes:
                    text = text[:max_bytes] + "..."
                return ToolResult(
                    tool_call_id=call_id,
                    tool_id=self.tool_id,
                    status="success",
                    output={"url": url, "status": resp.status_code, "text": text[:5000]},
                    human_readable=f"Fetched {url} ({resp.status_code}):\n{text[:4000]}",
                )
        except Exception as e:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                output=None,
                human_readable=f"Failed to fetch {url}: {e}",
                error="NETWORK",
            )
