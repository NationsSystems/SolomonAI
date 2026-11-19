"""Guided local first-run setup; never touches the original SolomonV3 database."""
from __future__ import annotations

import getpass
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
LOCAL = ROOT / "local_config"
CONFIG = LOCAL / "setup.json"
SCHEMA = ROOT / "schema" / "solomonai_schema.sql"
PUBLIC_DATABASE = "solomon_ai_local"
LEGACY_TEST_DATABASE = "solomon_ai_release_test"  # Existing verified pilot only.
APP_USER = "solomonai_app"
APP_HOST = "127.0.0.1"
TABLE_COUNT = 77
FOREIGN_KEYS = 102
SCHEMA_SHA256 = "f635e8581a7c7459e78b79d4f753f52ddd718e545b8b9a1f31acb5cb1cda113d"
ALLOWED_DATABASES = {PUBLIC_DATABASE, LEGACY_TEST_DATABASE}


def ask(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def read_existing_config() -> dict | None:
    if not CONFIG.exists():
        return None
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or
            set(data) != {"host", "port", "database", "user"} or
            data["database"] not in ALLOWED_DATABASES or
            not isinstance(data["host"], str) or
            not isinstance(data["user"], str) or
            not isinstance(data["port"], int) or
            not 1 <= data["port"] <= 65535):
        raise ValueError("Unrecognized local setup configuration. Refusing to overwrite it.")
    return data


def verify_database(config: dict, password: str) -> bool:
    import pymysql
    database = config["database"]
    if database not in ALLOWED_DATABASES:
        raise ValueError("Refusing connection to a non-release database")
    conn = pymysql.connect(
        host=config["host"], port=config["port"], user=config["user"],
        password=password, database=database, connect_timeout=5,
        read_timeout=15, autocommit=True, charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            active = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema=%s AND table_type='BASE TABLE'", (database,))
            count = cur.fetchone()[0]
    finally:
        conn.close()
    if active != database or count != TABLE_COUNT:
        print(f"ABORT: Expected {TABLE_COUNT} tables in {database!r}; found {count}.")
        return False
    return True


def schema_statements() -> list[str]:
    """Strictly accept our schema-only DDL, never generic SQL scripts."""
    if not SCHEMA.is_file():
        raise ValueError("Missing schema/solomonai_schema.sql")
    content = SCHEMA.read_text(encoding="utf-8")
    if hashlib.sha256(content.encode("utf-8")).hexdigest() != SCHEMA_SHA256:
        raise ValueError("Public schema file differs from approved 77-table distribution")
    statements = [s.strip() for s in "\n".join(
        line for line in content.splitlines()
        if not line.lstrip().startswith("--")
    ).split(";") if s.strip()]
    ddl = [s for s in statements if s.startswith("CREATE TABLE `")]
    if (len(ddl) != TABLE_COUNT or len(statements) != TABLE_COUNT + 3 or
            content.count("FOREIGN KEY (") != FOREIGN_KEYS or
            not statements[0].upper().startswith("SET NAMES UTF8MB4") or
            statements[1].upper() != "SET FOREIGN_KEY_CHECKS=0" or
            statements[-1].upper() != "SET FOREIGN_KEY_CHECKS=1"):
        raise ValueError("Schema is incomplete or not the approved 77-table definition set")
    for stmt in statements[2:-1]:
        if not re.match(r"\ACREATE TABLE `[a-z][a-z0-9_]*` \(\n", stmt):
            raise ValueError("Unexpected statement in public schema; no changes made")
    return statements


def save_config(config: dict):
    if CONFIG.exists():
        raise RuntimeError("Existing setup configuration must not be overwritten")
    LOCAL.mkdir(parents=True, exist_ok=True)
    ignore = LOCAL / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n!.gitignore\n", encoding="utf-8")
    CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def configure_existing(config: dict) -> int:
    print(f"Existing release installation: {config['database']} at {config['host']}:{config['port']}")
    print("The existing database and settings will not be modified.")
    password = getpass.getpass("Database account password (not saved): ")
    if not verify_database(config, password):
        return 1
    print(f"PASS: Existing configuration verified ({TABLE_COUNT} tables).")
    print("Run configure_local_ai.bat to select a model, then start.bat.")
    return 0


def setup_new() -> int:
    import pymysql
    print("\nNew isolated local installation (Windows / MySQL)")
    print(f"Database to CREATE: {PUBLIC_DATABASE} (never solomon_ai or solomon_ai_release_test)")
    print(f"Dedicated database user to CREATE: {APP_USER}@{APP_HOST}")
    print("A local MySQL administrator is needed once; no credentials are saved.")
    print("If either database or account already exists, setup stops without changing it.")
    if input("Create this isolated database and account? [y/N]: ").strip().lower() != "y":
        print("Cancelled. Nothing changed.")
        return 0
    host = APP_HOST
    port = int(ask("MySQL port", "3306"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid MySQL port")
    admin = ask("MySQL administrator username", "root")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", admin):
        raise ValueError("Invalid administrator account name")
    admin_password = getpass.getpass("MySQL administrator password (hidden): ")
    app_password = getpass.getpass("Choose NEW SolomonAI database account password: ")
    if len(app_password) < 12:
        raise ValueError("Use at least 12 characters for the new application account password")
    if app_password != getpass.getpass("Repeat new application password: "):
        raise ValueError("Application account passwords do not match")
    statements = schema_statements()  # Validate before connecting or writing.
    conn = pymysql.connect(host=host, port=port, user=admin, password=admin_password,
                           connect_timeout=5, read_timeout=30, autocommit=True,
                           charset="utf8mb4")
    created = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT SCHEMA_NAME FROM information_schema.schemata WHERE SCHEMA_NAME=%s",
                        (PUBLIC_DATABASE,))
            if cur.fetchone():
                raise RuntimeError("Database already exists; refusing to overwrite it")
            # A name collision is a failure, not permission to replace the account.
            cur.execute("SELECT COUNT(*) FROM mysql.user WHERE user=%s AND host=%s",
                        (APP_USER, APP_HOST))
            if cur.fetchone()[0] != 0:
                raise RuntimeError("Dedicated MySQL account already exists; refusing to alter it")
            cur.execute("CREATE USER 'solomonai_app'@'127.0.0.1' IDENTIFIED BY %s", (app_password,))
            cur.execute("CREATE DATABASE `solomon_ai_local` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            created = True
            cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES "
                        "ON `solomon_ai_local`.* TO 'solomonai_app'@'127.0.0.1'")
            cur.execute("USE `solomon_ai_local`")
            try:
                for stmt in statements:
                    cur.execute(stmt)
            finally:
                cur.execute("SET FOREIGN_KEY_CHECKS=1")
    finally:
        conn.close()
        del admin_password
    if not created:
        raise RuntimeError("Database provisioning did not complete")
    config = {"host": host, "port": port, "database": PUBLIC_DATABASE, "user": APP_USER}
    if not verify_database(config, app_password):
        raise RuntimeError("Schema verification failed; review isolated installation")
    save_config(config)
    print("\nPASS: 77 empty tables created in the new local database.")
    print("PASS: Dedicated application account and non-secret local setup saved.")
    print("REMEMBER your application database password; start.bat will ask for it.")
    print("Next: configure_local_ai.bat (choose/download model), then start.bat.")
    return 0


def main() -> int:
    print("=" * 64)
    print("SOLOMONAI 1.0 | GUIDED LOCAL SETUP")
    print("=" * 64)
    print("Original SolomonV3 database and files are prohibited.")
    try:
        import pymysql  # noqa: F401
    except ImportError:
        print("PyMySQL is missing. Run setup.bat to install dependencies first.")
        return 1
    existing = read_existing_config()
    if existing is not None:
        return configure_existing(existing)
    return setup_new()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled by user. No existing databases were modified.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"SETUP STOPPED ({type(exc).__name__}): {exc}")
        print("No existing database was overwritten. If a new database was partially")
        print("created, inspect solomon_ai_local manually before attempting setup again.")
        raise SystemExit(1)
