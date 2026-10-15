"""Task and chat persistence.

Lives under this name on purpose. A project-root data directory is also called
sessions/, and a gitignore rule of that name must not be able to hide the code.
"""

from .chat_log import ChatLog
from .manager import SessionManager
from .transcript import fold_transcript

__all__ = ["ChatLog", "SessionManager", "fold_transcript"]
