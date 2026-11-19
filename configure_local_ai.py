"""Interactive local model selection for SolomonAI Release 1.0 (Windows pilot).

This script never modifies SolomonV3 or downloads without explicit consent.
Only a non-secret local model path and display name are saved.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
LOCAL = ROOT / "local_config"
TARGET = LOCAL / "ai.json"
MODEL_DEST = ROOT / "models" / "generation" / "qwen3-1.7b"
REPO_ID = "Qwen/Qwen3-1.7B"


def ask(question: str, default: str = "") -> str:
    value = input(question).strip()
    return value or default


def check_model(path: pathlib.Path) -> pathlib.Path:
    directory = path.expanduser().resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("The selected path is not a directory")
    if not (directory / "config.json").is_file():
        raise ValueError("The directory is missing config.json")
    if not ((directory / "tokenizer.json").is_file() or
            (directory / "tokenizer_config.json").is_file()):
        raise ValueError("The directory is missing tokenizer files")
    if not (any(directory.glob("*.safetensors")) or
            any(directory.glob("*.bin"))):
        raise ValueError("The directory is missing Transformers model weights")
    return directory


def save_model(path: pathlib.Path, name: str) -> None:
    directory = check_model(path)
    if TARGET.exists():
        response = ask("A local model is already selected. Replace that selection? [y/N]: ")
        if response.lower() != "y":
            print("No settings changed.")
            return
    LOCAL.mkdir(parents=True, exist_ok=True)
    ignore = LOCAL / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n!.gitignore\n", encoding="utf-8")
    data = {"schema_version": 1, "model_path": str(directory), "model_name": name}
    temporary = LOCAL / "ai.json.tmp"
    try:
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, TARGET)
    finally:
        if temporary.exists():
            temporary.unlink()
    print("Model configured:", name)
    print("Stored only the local path and model name in local_config/ai.json.")
    print("No model weights or credentials were copied into this settings file.")
    print("Launch with start.bat to test SolomonAI's existing model loader.")


def main() -> int:
    print("=" * 66)
    print(" SOLOMONAI RELEASE 1.0 | LOCAL GENERATION MODEL")
    print("=" * 66)
    print("This is a supervised model configuration pilot, not a public installer.")
    print("The WebUI and database already work independently of local generation.")
    print("Local generation needs an actual Transformers model folder.")
    print("Models are not included in the public SolomonAI source package.\n")
    print(" 1 - Download the Qwen3-1.7B reference model (recommended)")
    print(" 2 - Select an existing compatible local model folder")
    print(" 0 - Cancel")
    choice = ask("Choice [0]: ", "0")
    if choice == "0":
        print("Cancelled; nothing changed.")
        return 0
    if choice == "1":
        print("Model:", REPO_ID)
        print("Source: https://huggingface.co/" + REPO_ID)
        print("License: Apache-2.0 (see upstream model repository)")
        print("Destination:", MODEL_DEST)
        print("This downloads several GB of model files from Hugging Face.")
        if ask("Download these weights now? [y/N]: ").lower() != "y":
            print("Cancelled; no download started.")
            return 0
        if shutil.disk_usage(ROOT).free < 8 * 1024**3:
            print("ABORT: Less than 8 GiB free space. Free space and retry.")
            return 1
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print("Missing huggingface_hub. Install requirements-ai.txt first.")
            return 1
        print("Downloading the official model; a partial download may be resumed.")
        snapshot_download(repo_id=REPO_ID, local_dir=str(MODEL_DEST))
        path = check_model(MODEL_DEST)
        save_model(path, "Qwen3-1.7B")
        return 0
    if choice == "2":
        path_text = ask("Absolute path to your Transformers model directory: ")
        if not path_text:
            print("No path entered. Nothing changed.")
            return 0
        name = ask("Model display name [folder name]: ", pathlib.Path(path_text).name)
        if not name or len(name) > 120:
            print("Model name must contain 1-120 characters.")
            return 1
        save_model(pathlib.Path(path_text), name)
        return 0
    print("Unknown option. No settings changed.")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print("Configuration failed:", type(exc).__name__, str(exc))
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        raise SystemExit(130)
