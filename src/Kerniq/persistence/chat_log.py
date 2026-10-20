"""On-disk chat log. Survives a browser refresh while the agent is still running.

The UI plugin reads this. The agent core does not import the UI.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .transcript import project_events


def _safe_id(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in (value or "chat"))[:80]


class ChatLog:
    def __init__(self, state_dir: Path | str):
        self.root = Path(state_dir) / "chats"
        self._lock = threading.Lock()
        self._mem: dict[str, dict] = {}
        self._last_flush = 0.0

    def _path(self, chat_id: str) -> Path:
        return self.root / f"{_safe_id(chat_id)}.json"

    def _run_path(self, run_id: str) -> Path:
        return self.root / f"run-{_safe_id(run_id)}.json"

    def begin(
        self,
        chat_id: str,
        run_id: str,
        user_text: str,
        attachments: Optional[list] = None,
    ) -> None:
        prior: list = []
        model_prior: list = []
        old = None
        with self._lock:
            old = self._mem.get(str(chat_id))
            if old is None:
                path = self._path(str(chat_id))
                if path.exists():
                    try:
                        old = json.loads(path.read_text(encoding="utf-8"))
                    except Exception:
                        old = None
        if old:
            if old.get("messages_model"):
                model_prior = list(old["messages_model"])
            else:
                model_prior = []
            if old.get("messages_full"):
                prior = list(old["messages_full"])
            elif old.get("done"):
                prior = project_events(
                    old.get("user_text") or "",
                    old.get("events") or [],
                    done=True,
                    attachments=old.get("attachments") or [],
                )
                prior = list(old.get("prior_messages") or []) + prior
            elif old.get("prior_messages"):
                prior = list(old["prior_messages"])
        else:
            model_prior = []
        rec = {
            "chat_id": str(chat_id),
            "run_id": str(run_id),
            "user_text": user_text or "",
            "attachments": list(attachments or []),
            "prior_messages": prior,
            "messages_model": model_prior,
            "messages_full": [],
            "events": [],
            "done": False,
            "error": None,
            "updated_at": time.time(),
        }
        with self._lock:
            self._mem[str(chat_id)] = rec
            self._mem["run:" + str(run_id)] = rec
            self._write(rec)

    def save_model_messages(self, chat_id: str, rows: list) -> None:
        """Transcript the next model call must continue. Survives a restart."""
        with self._lock:
            rec = self._mem.get(str(chat_id))
            if rec is None:
                path = self._path(str(chat_id))
                if path.exists():
                    try:
                        rec = json.loads(path.read_text(encoding="utf-8"))
                    except Exception:
                        rec = None
            if rec is None:
                rec = {
                    "chat_id": str(chat_id),
                    "run_id": "",
                    "user_text": "",
                    "attachments": [],
                    "prior_messages": [],
                    "messages_full": [],
                    "events": [],
                    "done": True,
                    "error": None,
                }
            rec["messages_model"] = [dict(row) for row in rows if isinstance(row, dict)]
            rec["updated_at"] = time.time()
            self._mem[str(chat_id)] = rec
            if rec.get("run_id"):
                self._mem["run:" + str(rec["run_id"])] = rec
            self._write(rec)

    def model_messages(self, chat_id: str) -> list:
        with self._lock:
            rec = self._mem.get(str(chat_id))
            if rec is None:
                path = self._path(str(chat_id))
                if path.exists():
                    try:
                        rec = json.loads(path.read_text(encoding="utf-8"))
                    except Exception:
                        rec = None
        if not rec:
            return []
        rows = rec.get("messages_model")
        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, dict)]

    def append(self, run_id: str, event: dict) -> None:
        with self._lock:
            rec = self._mem.get("run:" + str(run_id))
            if rec is None:
                rec = self._read_run(str(run_id))
                if rec is None:
                    return
                self._mem["run:" + str(run_id)] = rec
                self._mem[rec["chat_id"]] = rec
            rec["events"].append(dict(event))
            rec["updated_at"] = time.time()
            now = time.monotonic()
            important = event.get("type") in {
                "tool",
                "assistant",
                "think_done",
                "approval",
                "file_op",
                "status",
            }
            if important or now - self._last_flush > 0.4:
                self._write(rec)
                self._last_flush = now

    def finish(self, run_id: str, *, done: bool = True, error: Optional[str] = None) -> None:
        with self._lock:
            rec = self._mem.get("run:" + str(run_id))
            if rec is None:
                return
            rec["done"] = done
            rec["error"] = error
            rec["updated_at"] = time.time()
            current = project_events(
                rec.get("user_text") or "",
                rec.get("events") or [],
                done=True,
                attachments=rec.get("attachments") or [],
            )
            rec["messages_full"] = list(rec.get("prior_messages") or []) + current
            self._write(rec)

    def events_since(self, run_id: str, cursor: int) -> dict:
        with self._lock:
            rec = self._mem.get("run:" + str(run_id)) or self._read_run(str(run_id))
        if rec is None:
            return {"error": "unknown run", "events": [], "done": True, "cursor": cursor}
        events = rec.get("events") or []
        try:
            idx = max(0, int(cursor))
        except (TypeError, ValueError):
            idx = 0
        chunk = events[idx:]
        return {
            "events": chunk,
            "done": bool(rec.get("done")),
            "error": rec.get("error"),
            "cursor": idx + len(chunk),
        }

    def snapshot(self, chat_id: str) -> dict:
        with self._lock:
            rec = self._mem.get(str(chat_id))
            if rec is None:
                path = self._path(str(chat_id))
                if path.exists():
                    try:
                        rec = json.loads(path.read_text(encoding="utf-8"))
                    except Exception:
                        rec = None
        if not rec:
            return {"chat_id": chat_id, "messages": [], "active": False, "cursor": 0}
        events = rec.get("events") or []
        if rec.get("done") and rec.get("messages_full"):
            messages = list(rec["messages_full"])
        else:
            current = project_events(
                rec.get("user_text") or "",
                events,
                done=bool(rec.get("done")),
                attachments=rec.get("attachments") or [],
            )
            messages = list(rec.get("prior_messages") or []) + current
        active = bool(rec.get("run_id")) and not rec.get("done")
        return {
            "chat_id": rec.get("chat_id") or chat_id,
            "run_id": rec.get("run_id"),
            "messages": messages,
            "active": active,
            "done": bool(rec.get("done")),
            "cursor": len(events),
            "error": rec.get("error"),
        }

    def _read_run(self, run_id: str) -> Optional[dict]:
        path = self._run_path(run_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write(self, rec: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(rec, ensure_ascii=False)
        paths = [self._path(rec["chat_id"])]
        run_id = str(rec.get("run_id") or "")
        if run_id:
            paths.append(self._run_path(run_id))
        for path in paths:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(blob, encoding="utf-8")
            tmp.replace(path)
