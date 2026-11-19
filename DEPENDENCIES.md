# SolomonAI Release 1.0 — Dependencies and verification

This is a developer-oriented, as-is Windows source release. The guided installation workflow was verified on a single reference Windows x64 machine on November 19, 2026. It is not a guarantee of compatibility across other hardware or operating systems.

## Tested reference environment

- Windows x64, Python 3.11 (`py -3.11`), local MySQL/MariaDB server, NVIDIA RTX 3060 (12 GB VRAM).
- `setup.bat` created a new Python virtual environment and installed the application dependencies in `requirements.txt`.
- The installer installed CUDA PyTorch 2.12.0+cu126, Transformers 5.9.0, Accelerate 1.13.0 and the dependencies in `requirements-ai.txt`.
- `pip check` reported no broken requirements.
- The guided setup created the `solomon_ai_local` database with 77 empty tables from `schema/solomonai_schema.sql`, created a dedicated `solomonai_app` database account, and generated non-secret installation settings.
- `configure_local_ai.bat` independently downloaded and configured Qwen3-1.7B. No model weights are shipped in this repository.
- `start.bat` authenticated to that database, loaded Qwen3-1.7B onto CUDA, and performed successful text generation (approximately 22 tokens/sec during the tested warmup).
- In a fresh browser session, the WebUI displayed a generated chat answer and accepted a file upload. This verifies the baseline workflow, not all optional features.
- Waitress is the normal local server; the session-signing secret is generated privately and reused across restarts. Do not expose the reference setup to the public Internet without additional hardening.

## Requirements manifests

- `requirements.txt`: pinned application dependencies.
- `requirements-ai.txt`: pinned local model dependencies; the setup script separately installs the verified CUDA PyTorch wheel for NVIDIA GPUs.
- `requirements-lock.txt` was a historical pre-release environment snapshot containing outdated versions. It is intentionally excluded from GitHub and must not be treated as the current dependency contract.
- The original private SolomonV3 environment used older Pydantic/SQLAlchemy releases; do not copy those versions into this release.

## Optional components

- **Standalone SIS:** Not required for the tested local chat workflow. The WebUI starts an in-process intelligence/spool worker; optional standalone/remote SIS transport is not part of the tested deployment.
- **Embeddings and document workers:** An embedding model or separate configuration may be necessary. Not all processing jobs have been qualified.
- **BEI and LoRA model assets:** Not shipped; specialized functions may require separate model configuration.
- **Redis and other external integrations:** May be used by optional code paths, but are not established as necessary for the verified local chat workflow.

## Installation sequence

1. Install Python 3.11 and a local MySQL/MariaDB server; make administrator credentials available for one-time setup.
2. Run `setup.bat` in a fresh source directory; create the new dedicated database and account when prompted. The installer will not replace an existing database/account.
3. Run `configure_local_ai.bat` to download or select compatible model weights.
4. Run `start.bat`, enter the dedicated database account password, and open `http://127.0.0.1:8080`.

Keep `local_config/` private. Do not commit actual credentials, model weights, database data, logs, or caches. The original private `solomon_ai` database is not part of this distribution.
