"""Web search URL encoding without urllib."""

from Kerniq.tools.web_search import _url_encode, WebSearchTool


def test_url_encode_basic():
    assert _url_encode("hello world") == "hello+world"
    assert " " not in _url_encode("a b")
    assert _url_encode("c++") == "c%2B%2B"


def test_web_search_disabled():
    import asyncio

    async def _run():
        tool = WebSearchTool(enabled=False)
        r = await tool.execute({"query": "test", "tool_call_id": "1"}, None)
        assert r.status == "error"
        assert r.error == "DISABLED"

    asyncio.run(_run())
