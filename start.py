"""Guarded local WebUI launcher; only release-owned databases permitted."""
from __future__ import annotations
import getpass
import json
import os
import pathlib
import secrets
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
CONFIG = ROOT / "local_config" / "setup.json"
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
TEST_DATABASE = "solomon_ai_release_test"  # Preserve existing accepted pilot.
PUBLIC_DATABASE = "solomon_ai_local"
ALLOWED_DATABASES = {TEST_DATABASE, PUBLIC_DATABASE}
EXPECTED_TABLES = 77
SECRET_FILE = ROOT / "local_config" / "session_secret"
AI_CONFIG = ROOT / "local_config" / "ai.json"



def load_local_ai_selection() -> tuple[pathlib.Path, str] | None:
    """Read a non-secret local model selection; never load model weights here."""
    if not AI_CONFIG.is_file():
        return None
    try:
        data = json.loads(AI_CONFIG.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Unrecognized AI setup format")
        raw_path = data.get("model_path")
        name = data.get("model_name")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("Model path missing")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Model name missing or invalid")
        model_path = pathlib.Path(raw_path).expanduser().resolve(strict=True)
        if not model_path.is_dir():
            raise ValueError("Model path is not a directory")
        if not (model_path / "config.json").is_file():
            raise ValueError("Missing model config.json")
        if not ((model_path / "tokenizer.json").is_file() or
                (model_path / "tokenizer_config.json").is_file()):
            raise ValueError("Missing tokenizer files")
        if not (any(model_path.glob("*.safetensors")) or
                any(model_path.glob("*.bin"))):
            raise ValueError("Missing local model weight files")
        return model_path, name.strip()
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"Local AI selection invalid ({exc}); run configure_local_ai.bat") from exc

def get_or_create_session_secret() -> str:
    """Persist a private installation-specific secret; do not commit it."""
    if SECRET_FILE.exists():
        secret = SECRET_FILE.read_text(encoding="utf-8").strip()
        if len(secret) < 40:
            raise ValueError("Local session-secret file is invalid; inspect it before starting")
        return secret
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(48)
    # Exclusive creation: never overwrite a key created by a different session.
    with SECRET_FILE.open("x", encoding="utf-8") as f:
        f.write(secret + "\n")
    return secret


def launch(password: str | None = None, config: dict | None = None):
    if config is None:
        if not CONFIG.is_file():
            print("No configuration found. Run setup.bat first.")
            return 1
        try:
            config = json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print("Local setup file is invalid. Run setup.bat again.")
            return 1
    database = config.get("database")
    if database not in ALLOWED_DATABASES:
        print("ABORT: This release cannot connect to that database.")
        return 1
    if not VENV_PY.is_file() or pathlib.Path(sys.executable).resolve() != VENV_PY.resolve():
        print("ABORT: Use the isolated release Python through start.bat.")
        return 1
    try:
        import pymysql
        from sqlalchemy.engine import URL
    except ImportError as exc:
        print("Missing dependency:", exc.name)
        return 1
    if password is None:
        print("This is a separate launch session. We do not store database passwords.")
        password = getpass.getpass("MySQL account password (hidden): ")
    if not password:
        print("Password required.")
        return 1
    try:
        conn = pymysql.connect(host=config["host"], port=int(config["port"]),
                               user=config["user"], password=password,
                               database=database, connect_timeout=5,
                               read_timeout=10, autocommit=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DATABASE()")
                active = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM information_schema.tables "
                               "WHERE table_schema=%s AND table_type='BASE TABLE'", (database,))
                count = cursor.fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:
        print("Database connection failed:", type(exc).__name__)
        print("Run setup.bat to review server and account settings.")
        return 1
    if active != database or count != EXPECTED_TABLES:
        print("ABORT: Unexpected database or table count.")
        return 1
    url = URL.create("mysql+pymysql", username=config["user"], password=password,
                     host=config["host"], port=int(config["port"]),
                     database=database, query={"charset":"utf8mb4"}).render_as_string(hide_password=False)
    env = os.environ.copy()
    env.update({
        "SOLOMON_SQLALCHEMY_DATABASE_URL": url,
        "SOLOMON_INVESTIGATOR_SQLALCHEMY_DATABASE_URL": url,
        "SOLOMON_DB_HOST": config["host"],
        "SOLOMON_DB_PORT": str(config["port"]),
        "SOLOMON_DB_NAME": database,
        "SOLOMON_DB_USER": config["user"],
        "SOLOMON_DB_PASS": password,
        "SOLOMON_INVESTIGATOR_DB_USER": config["user"],
        "SOLOMON_INVESTIGATOR_DB_PASS": password,
        "SOLOMON_APP_SECRET_KEY": get_or_create_session_secret(),
        "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
    })
    try:
        selected_ai = load_local_ai_selection()
    except ValueError as exc:
        print("ABORT:", exc)
        return 1
    if selected_ai is not None:
        model_dir, model_name = selected_ai
        env["SOLOMONAI_LOCAL_MODEL_DIR"] = str(model_dir)
        env["SOLOMONAI_LOCAL_MODEL_NAME"] = model_name
        print("Local AI model selected:", model_name)
        print("Model directory:", model_dir)
    else:
        print("Local AI model not configured; model warmup may fail.")
        print("Run configure_local_ai.bat when ready to enable local generation.")

    print(f"\nPREFLIGHT PASS: Running with isolated release database {database!r}.")
    print("Starting the release WebUI. Ctrl+C stops the foreground process.")
    print("Local session-signing secret is private and persistent across restarts.")
    try:
        return subprocess.call([str(VENV_PY), str(ROOT / "webui" / "app.py")], cwd=str(ROOT), env=env)
    finally:
        del url
        del password


def main():
    try:
        return launch()
    except KeyboardInterrupt:
        print("\nLauncher stopped by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
