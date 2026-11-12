"""A tool may hide the chat cards of work it runs itself."""

from __future__ import annotations

import contextvars

suppress_tool_cards = contextvars.ContextVar("suppress_tool_cards", default=False)
# Older plugins set this name. It is the same flag.
agent_tools_silent = suppress_tool_cards

