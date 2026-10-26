"""Chat lists and replies. MySQL when it is reachable, otherwise JSON.

The JSON fallback is a real store, not a placeholder. Every caller that
serves a person includes ``warning`` while that fallback is in use.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .settings import JSON_STORAGE_WARNING

_SAFE = __import__("re").compile(r"[^a-zA-Z0-9_-]+")


def _pct_decode(text: str) -> str:
    raw = bytearray()
    i = 0
    s = text or ""
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            try:
                raw.append(int(s[i + 1 : i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        raw.extend(s[i].encode("utf-8"))
        i += 1
    return raw.decode("utf-8", errors="replace")


def parse_mysql_url(url: str) -> dict[str, Any]:
    """Parse ``mysql://user:pass@host:3306/db`` without urllib."""
    text = (url or "").strip()
    if "://" not in text:
        raise ValueError("database url must start with mysql://")
    scheme, rest = text.split("://", 1)
    if scheme not in {"mysql", "mariadb"}:
        raise ValueError("only mysql is supported")
    user = password = ""
    hostpart = rest
    if "@" in rest:
        auth, hostpart = rest.rsplit("@", 1)
        if ":" in auth:
            user, password = auth.split(":", 1)
        else:
            user = auth
    database = ""
    if "/" in hostpart:
        hostport, database = hostpart.split("/", 1)
        database = database.split("?", 1)[0]
    else:
        hostport = hostpart
    host = hostport
    port = 3306
    if hostport.startswith("["):
        end = hostport.find("]")
        if end < 0:
            raise ValueError("bad database host")
        host = hostport[1:end]
        tail = hostport[end + 1 :]
        if tail.startswith(":"):
            port = int(tail[1:] or "3306")
    elif ":" in hostport:
        host, port_text = hostport.rsplit(":", 1)
        port = int(port_text)
    if not host or not database:
        raise ValueError("database url needs a host and a database name")
    return {
        "user": _pct_decode(user),
        "password": _pct_decode(password),
        "host": host,
        "port": port,
        "database": database,
    }


def _safe_user(user_id: str) -> str:
    cleaned = _SAFE.sub("_", user_id or "local").strip("_")
    return (cleaned or "local")[:80]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HistoryStore:
    def __init__(self, state_dir: Path | str, database_url: str = ""):
        from ..devtools.paths import anchored_dir

        self.root = anchored_dir(state_dir) / "server"
        self.warning = ""
        self.backend = "json"
        self._lock = threading.RLock()
        self._db = None
        url = (database_url or "").strip()
        if not url:
            self.warning = JSON_STORAGE_WARNING
            return
        try:
            if url.startswith("sqlite://"):
                self._db = _Sqlite(url)
                self.backend = "sqlite"
            else:
                self._db = _Mysql(url)
                self.backend = "mysql"
        except Exception as exc:
            self.warning = JSON_STORAGE_WARNING
            self.backend = "json"
            self._db = None
            # The URL can contain a password. Keep it out of the warning.
            self.failure = exc.__class__.__name__

    def list_chats(self, user_id: str) -> list:
        if self._db is not None:
            return self._db.list_chats(user_id)
        return list(self._read(user_id).get("chats") or [])

    def save_chats(self, user_id: str, chats: list) -> None:
        kept = list(chats)[-40:]
        if self._db is not None:
            self._db.save_chats(user_id, kept)
            return
        with self._lock:
            data = self._read(user_id)
            data["chats"] = kept
            self._write(user_id, data)

    def save_replies(self, user_id: str, chat_id: str, rows: list) -> None:
        clean = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "")
            content = str(row.get("content") or "")
            if role not in {"user", "assistant"} or not content.strip():
                continue
            clean.append({"role": role, "content": content})
        if not clean:
            return
        if self._db is not None:
            self._db.save_replies(user_id, chat_id, clean)
            return
        with self._lock:
            data = self._read(user_id)
            bucket = data.setdefault("replies", {})
            if not isinstance(bucket, dict):
                bucket = {}
                data["replies"] = bucket
            current = bucket.get(chat_id)
            if not isinstance(current, list):
                current = []
            current.extend(clean)
            bucket[chat_id] = current[-200:]
            self._write(user_id, data)

    def replies(self, user_id: str, chat_id: str) -> list:
        if self._db is not None:
            return self._db.replies(user_id, chat_id)
        bucket = self._read(user_id).get("replies") or {}
        rows = bucket.get(chat_id) if isinstance(bucket, dict) else None
        return list(rows) if isinstance(rows, list) else []

    def _file(self, user_id: str) -> Path:
        return self.root / "users" / f"{_safe_user(user_id)}.json"

    def _read(self, user_id: str) -> dict[str, Any]:
        path = self._file(user_id)
        if not path.is_file():
            return {"chats": [], "replies": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"chats": [], "replies": {}}
        return data if isinstance(data, dict) else {"chats": [], "replies": {}}

    def _write(self, user_id: str, data: dict[str, Any]) -> None:
        path = self._file(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


class _Mysql:
    def __init__(self, url: str):
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("mysql driver is not installed") from exc
        cfg = parse_mysql_url(url)
        self._pymysql = pymysql
        self._cfg = cfg
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kerniq_chat (
                        user_id VARCHAR(80) NOT NULL,
                        document LONGTEXT NOT NULL,
                        updated_at VARCHAR(40) NOT NULL,
                        PRIMARY KEY (user_id)
                    ) CHARACTER SET utf8mb4
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kerniq_reply (
                        reply_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(80) NOT NULL,
                        chat_id VARCHAR(80) NOT NULL,
                        role VARCHAR(16) NOT NULL,
                        content LONGTEXT NOT NULL,
                        created_at VARCHAR(40) NOT NULL,
                        PRIMARY KEY (reply_id),
                        KEY kerniq_reply_user (user_id, chat_id)
                    ) CHARACTER SET utf8mb4
                    """
                )
        finally:
            conn.close()

    def _connect(self):
        return self._pymysql.connect(
            host=self._cfg["host"],
            user=self._cfg["user"],
            password=self._cfg["password"],
            database=self._cfg["database"],
            port=int(self._cfg["port"]),
            connect_timeout=3,
            charset="utf8mb4",
            autocommit=True,
        )

    def list_chats(self, user_id: str) -> list:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT document FROM kerniq_chat WHERE user_id=%s",
                    (_safe_user(user_id),),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return []
        try:
            data = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def save_chats(self, user_id: str, chats: list) -> None:
        payload = json.dumps(chats, ensure_ascii=False)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kerniq_chat (user_id, document, updated_at)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE document=VALUES(document), updated_at=VALUES(updated_at)
                    """,
                    (_safe_user(user_id), payload, _now()),
                )
        finally:
            conn.close()

    def save_replies(self, user_id: str, chat_id: str, rows: list) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO kerniq_reply
                            (reply_id, user_id, chat_id, role, content, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            uuid4().hex,
                            _safe_user(user_id),
                            str(chat_id)[:80],
                            row["role"],
                            row["content"],
                            _now(),
                        ),
                    )
        finally:
            conn.close()

    def replies(self, user_id: str, chat_id: str) -> list:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content, created_at FROM kerniq_reply
                    WHERE user_id=%s AND chat_id=%s
                    ORDER BY created_at ASC
                    """,
                    (_safe_user(user_id), str(chat_id)[:80]),
                )
                found = cur.fetchall()
        finally:
            conn.close()
        return [{"role": role, "content": content, "created_at": at} for role, content, at in found]


def open_history(state_dir: Path | str, database_url: str = "") -> HistoryStore:
    return HistoryStore(state_dir, database_url)
