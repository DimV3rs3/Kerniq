"""Create a MySQL database and the URL Kerniq stores. No urllib."""

from __future__ import annotations

import importlib.util
import shutil
from typing import Any


_NAME_OK = __import__("re").compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def database_name_ok(name: str) -> bool:
    return bool(_NAME_OK.match(str(name or "")))


def _pct(text: str) -> str:
    out: list[str] = []
    for byte in str(text or "").encode("utf-8"):
        ch = chr(byte)
        if ch.isalnum() or ch in "-._~":
            out.append(ch)
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def build_mysql_url(host: str, port: int, user: str, password: str, name: str) -> str:
    if not database_name_ok(name):
        raise ValueError("Database name must be letters, digits, and underscores.")
    host_text = str(host or "").strip()
    if not host_text or any(ch in host_text for ch in " /@\\"):
        raise ValueError("Database host is not valid.")
    number = int(port)
    if number < 1 or number > 65535:
        raise ValueError("Database port is not valid.")
    return f"mysql://{_pct(user)}:{_pct(password)}@{host_text}:{number}/{name}"


def scan_engines() -> list[dict[str, Any]]:
    """Databases visible on this machine. Unsupported ones are marked, not offered."""
    found: list[dict[str, Any]] = []
    mysql_client = bool(shutil.which("mysql") or shutil.which("mariadb"))
    driver = importlib.util.find_spec("pymysql") is not None
    if mysql_client or driver:
        found.append({
            "id": "mysql",
            "label": "MySQL / MariaDB",
            "supported": True,
            "client": mysql_client,
            "driver": driver,
        })
    if shutil.which("psql"):
        found.append({
            "id": "postgres",
            "label": "PostgreSQL",
            "supported": False,
            "reason": "Kerniq does not use PostgreSQL.",
        })
    return found


def provision_mysql(*, host: str, port: int, user: str, password: str, name: str) -> dict[str, Any]:
    """Connect without a database, create it if missing, and return the URL.

    The password is not included in ``error``. Kerniq creates the database.
    The operator does not have to create it first.
    """
    if not database_name_ok(name):
        return {
            "ok": False,
            "error": "Database name must be letters, digits, and underscores.",
        }
    try:
        import pymysql
    except ImportError:
        return {
            "ok": False,
            "error": "MySQL support is not installed. Run: pip install pymysql",
        }
    try:
        conn = pymysql.connect(
            host=str(host or "127.0.0.1"),
            port=int(port),
            user=str(user or ""),
            password=str(password or ""),
            connect_timeout=8,
            autocommit=True,
        )
    except Exception:
        return {
            "ok": False,
            "error": "Could not connect to MySQL. Check the host, user, and password.",
        }
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4"
            )
    except Exception:
        return {
            "ok": False,
            "error": (
                "Connected, but the database could not be created. "
                "The account needs permission to create databases."
            ),
        }
    finally:
        conn.close()
    try:
        url = build_mysql_url(host, int(port), user, password, name)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "url": url, "database": name}


def init_server_database(state_dir) -> int:
    """Ask for storage, the UI port, user folders, and an optional Linux account."""
    import sys

    if not sys.stdin.isatty():
        print("Server setup needs a terminal. Run: kerniq server init")
        return 0
    code = _ask_database(state_dir)
    layout = ask_server_layout(state_dir)
    return code or layout


def _ask_database(state_dir) -> int:
    """Ask which supported database to use."""
    import getpass

    from .settings import JSON_STORAGE_WARNING, save_server_settings

    engines = scan_engines()
    supported = [row for row in engines if row.get("supported")]
    dropped = [row for row in engines if not row.get("supported")]
    print("Kerniq creates the database. You do not create it first.")
    if dropped:
        print("Ignored (not supported): " + ", ".join(str(row["label"]) for row in dropped))
    if not supported:
        print("No supported database was found on this machine. Chats stay in JSON.")
        print(JSON_STORAGE_WARNING)
        return 0
    for index, row in enumerate(supported, 1):
        note = ""
        if row.get("id") == "mysql" and not row.get("driver"):
            note = " — pymysql is not installed yet"
        print(f"  {index}. {row['label']}{note}")
    print("  0. JSON files")
    choice = input("Choose [0]: ").strip() or "0"
    if choice == "0":
        print(JSON_STORAGE_WARNING)
        return 0
    try:
        picked = supported[int(choice) - 1]
    except (ValueError, IndexError):
        print("Unknown choice.")
        return 1
    if picked.get("id") != "mysql":
        print("That database is not supported.")
        return 1
    if not picked.get("driver"):
        print("Install the driver first: pip install pymysql")
        return 1
    host = input("Host [127.0.0.1]: ").strip() or "127.0.0.1"
    port_text = input("Port [3306]: ").strip() or "3306"
    user = input("User: ").strip()
    password = getpass.getpass("Password: ")
    name = input("Database name [kerniq]: ").strip() or "kerniq"
    try:
        port = int(port_text)
    except ValueError:
        print("Port must be a number.")
        return 1
    result = provision_mysql(host=host, port=port, user=user, password=password, name=name)
    if not result.get("ok"):
        print(result.get("error") or "Database was not created.")
        return 1
    save_server_settings(state_dir, {"database_url": result["url"], "enabled": True})
    print(f"Database {name} is ready.")
    return 0


def _yes(prompt: str, default_yes: bool) -> bool:
    hint = "Y/n" if default_yes else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default_yes
    return answer in {"y", "yes", "1", "true"}


def ask_server_layout(state_dir) -> int:
    """Port, user-folder roots, and the optional service account."""
    from pathlib import Path

    from .account import offer_service_user
    from .homes import assert_users_root
    from .settings import load_server_settings, save_server_settings
    from Kerniq.settings.component_store import ComponentSettingsStore

    current = load_server_settings(state_dir)
    default_port = int(current.get("port") or 8765)
    port_text = input(f"UI port [{default_port}]: ").strip() or str(default_port)
    try:
        port = int(port_text)
    except ValueError:
        print("Port must be a number.")
        return 1
    if not 1 <= port <= 65535:
        print("Port must be from 1 to 65535.")
        return 1
    suggested = str(current.get("users_root") or "")
    hint = suggested or str(Path("workspace").resolve())
    print("User folders hold one directory per browser. Each has workspace/ and attachments/.")
    primary_text = input(f"Folder for user workspaces [{hint}]: ").strip() or hint
    try:
        primary = assert_users_root(primary_text)
    except ValueError as exc:
        print(str(exc))
        return 1
    extras: list[str] = []
    print("Extra disks for the same folders. Empty line finishes. An existing user stays on the disk that already has them.")
    while True:
        extra = input("Another disk folder (empty to stop): ").strip()
        if not extra:
            break
        try:
            folder = assert_users_root(extra)
        except ValueError as exc:
            print(str(exc))
            continue
        if folder == primary or str(folder) in extras:
            print("That folder is already in the list.")
            continue
        extras.append(str(folder))
    save_server_settings(
        state_dir,
        {
            "enabled": True,
            "host": "0.0.0.0",
            "port": port,
            "lan_access": True,
            "users_root": str(primary),
            "users_roots": extras,
        },
    )
    store = ComponentSettingsStore(state_dir)
    plugin = store.load("plugin", "plugin_web_ui")
    plugin["port"] = port
    plugin["host"] = "0.0.0.0"
    plugin["server_mode"] = True
    plugin["lan_access"] = True
    store.save("plugin", "plugin_web_ui", plugin)
    print(f"UI port {port}. User folders: {primary}")
    if extras:
        print("Also: " + ", ".join(extras))
    create_user = _yes("Create a Linux user named kerniq", True)
    superuser = False
    if create_user:
        superuser = _yes("Give that user superuser rights", False)
    offer_service_user(create=create_user, superuser=superuser)
    print("Restart the Web UI so these answers apply.")
    return 0
