"""Server mode: one Kerniq process, many entry points.

The web plugin displays this. It does not own users, chat storage, or the
model queue.
"""

from .listen import resolve_listen
from .settings import JSON_STORAGE_WARNING, load_server_settings

__all__ = ["JSON_STORAGE_WARNING", "load_server_settings", "resolve_listen"]
