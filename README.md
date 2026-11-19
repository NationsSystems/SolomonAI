# SolomonAI

**SolomonAI Release 1.0 — open-source community release**  
Developed by **Bryan Nations** and published under the **Nations Systems** name.

SolomonAI is an existing, locally runnable AI application combining a browser workspace, user accounts, document/file workflows, and local language-model inference. This repository is intended for technically capable developers who want to study, adapt, or contribute to the application.

> **Current status:** The isolated Windows development copy successfully launched, authenticated users, handled files, and completed a browser chat exchange with local Qwen3-1.7B inference on an NVIDIA RTX 3060 (November 2026). **A fresh guided installation was acceptance-tested in an isolated Windows source copy on November 19, 2026.** This is not a hosted service or a turnkey installer.

## What is included

- Existing Python application, browser UI, and local AI integration.
- Windows setup/start scripts (`setup.bat`, `start.bat`) and the local model configurator (`configure_local_ai.bat`).
- Python requirements, local setup guidance, and tested-environment notes in [DEPENDENCIES.md](DEPENDENCIES.md).
- DDL-only MySQL schema in `schema/solomonai_schema.sql` (no user rows).
- [Third-party notices](THIRD_PARTY_NOTICES.md) for bundled frontend assets.
- [Branding and trademark policy](BRANDING.md): SolomonAI and Nations Systems branding remains proprietary, separate from the open-source code license.

**Not included:** Model weights, trained adapters/LoRAs, user data, credentials, environment folders, caches, logs, and the developer's MySQL database or database export. Model-related examples may be documented separately where licensing permits.

## The Solomon Constitution

The [Solomon Constitution, Version 1.1](docs/SOLOMON_CONSTITUTION.md) records the project’s architecture and governance model. The [active Constitutional Amendment I](docs/SOLOMON_CONSTITUTION_AMENDMENT_I.md) integrates a Knowledge Layer in the Investigator stage and is intended to be read alongside Version 1.1. Publication-ready Word editions are provided for the [Constitution](docs/Solomon_Constitution_v1.1.docx) and [Amendment I](docs/Solomon_Constitution_Amendment_I.docx), with source text and formatting retained and document metadata cleaned.

These documents express design intent and contribution guidance; **they are not additional software licenses and do not restrict rights under Apache 2.0**. They are historical architectural references and do not certify that every part of the current code implements each described rule.

## Architecture and optional components

SolomonAI has a working **local inference mode**. The reference setup does **not** require a separately installed or running Solomon Intelligence Service (SIS) server for browser chat. These components have different requirements:

| Component | Required for the verified local chat workflow? | Current release status |
| --- | --- | --- |
| WebUI and application backend | Yes | Validated locally with the existing **Waitress** server (localhost by default). |
| MySQL | Yes | The pilot used an independently provisioned 77-table schema. The new guided installer can create a separate `solomon_ai_local` database from the bundled schema; the fresh-install path was acceptance-tested on the reference Windows machine. |
| Python environment and application packages | Yes | `setup.bat` creates a Python 3.11 virtual environment and installs the candidate dependencies when needed; fresh bootstrap passed on the reference Windows machine. |
| Direct Transformers LLM and its model files | Yes, for local AI chat | Qwen3-1.7B on CUDA was verified. Model files are selected/downloaded separately and excluded from source control. |
| In-process intelligence/spool worker | Starts with the application | Started successfully in the local pilot; not every queued document or embedding job has been functionally tested. No separate SIS server is implied by a `[SIS][SPOOL_WORKER_STARTED]` log. |
| Standalone/remote Solomon Intelligence Service (SIS) | **No** | Optional alternate transport/compute integration in the source. The release pilot ran with SIS disabled; its separate deployment, endpoint, credentials, and health checks were **not validated**. |
| Embedding model | Not needed for the verified basic chat test | Some document/semantic workflows may need a separately configured embedding model; full acceptance testing is pending. |
| Specialized BEI model or LoRA assets | No | Not included. Specialized behavior that depends on them is not part of the verified baseline. |
| Redis and other optional external integrations | Not established as required for tested chat | Dependency references alone do not prove an external service is required. Optional features and their service requirements have not been exhaustively qualified. |

**SIS configuration:** Keep external SIS disabled for the documented local inference route. A configured endpoint such as `http://127.0.0.1:8091` appearing in a startup log does not by itself mean an external server is running or required. Enabling SIS selects a distinct service-backed path and requires separately validating that service. Do not enable it merely to fix a local chat readiness warning.

**Scope of verification:** Successful local GPU generation, browser chat, and the local spool worker's startup do not certify all optional features, remote execution, or a clean installation on another computer.

## Environment and requirements

The validated pilot was on **Windows x64, Python 3.11, MySQL, and an NVIDIA RTX 3060 with 12 GB VRAM**. Other operating systems, CPU-only inference, GPU models, and Python versions have not been qualified.

The pinned Python manifests passed the guided fresh-install test on the reference Windows machine; they are not a cross-platform compatibility guarantee. The AI model requires separately installed dependencies and model files; see [requirements-ai.txt](requirements-ai.txt) and [DEPENDENCIES.md](DEPENDENCIES.md).

## Guided Windows local installation

**Prerequisites:** Windows x64, Python 3.11 (including the `py` launcher), a running local MySQL/MariaDB server with an administrator login, and suitable hardware for a local LLM. The tested dependency baseline targets an NVIDIA GPU and CUDA 12.6. Other GPU/CPU configurations may require manual changes. Internet access is needed to install Python packages and download the model if not already available.

1. Download/extract the source, then run **`setup.bat`**. On a fresh copy, it creates `.venv`, installs the candidate Python/AI dependencies and CUDA PyTorch reference build, then guides you through MySQL setup. This installer was tested on the reference Windows environment, not across other machines or operating systems.
2. Confirm creation of the **new** database `solomon_ai_local` and application account `solomonai_app` using your local MySQL administrator credentials. The included `schema/solomonai_schema.sql` contains 77 empty table definitions. The installer refuses to overwrite an existing database or account. Record the new application database password yourself; it is not written to disk.
3. Run **`configure_local_ai.bat`** to download the Apache-2.0 Qwen3-1.7B reference model, or select an existing Transformers-compatible local model.
4. Run **`start.bat`**, enter your application database account password, and open `http://127.0.0.1:8080/ai` to register or sign in.

Existing accepted pilots with `local_config/setup.json` pointing to `solomon_ai_release_test` remain supported; rerunning setup for those installations only verifies their existing database. The installer never touches the original private `solomon_ai` database. Never copy personal `local_config/` settings or database contents into the public repository.

**Installation verification status (November 19, 2026):** An isolated source-only copy created a new Python environment, installed Python and CUDA dependencies, provisioned a clean 77-table MySQL database, downloaded Qwen3-1.7B, started SolomonAI, and successfully completed browser chat and a file upload. This qualifies the documented reference Windows workflow, not other machines or every feature.

**Security:** The accepted pilot ran using the **Waitress** server on localhost, with Flask debug mode disabled by default. The launcher now creates a persistent, random per-installation session-signing secret under excluded `local_config/`. Keep that directory private; this is not a security-reviewed deployment for public network access. Keep the installation private to localhost unless independently hardened. The published source is supplied as-is and has not undergone a comprehensive security penetration test.

## Project layout

- `solomon_core/` — backend intelligence, orchestration, routes, and inference integration
- `solomon_workspace/` — workspace capabilities and document-related state
- `webui/` — browser frontend and Flask application
- `setup.py`, `start.py`, `configure_local_ai.py` — local supervised tooling

## License and support

**Copyright © 2026 Bryan Nations** for the original SolomonAI software and documentation he owns. Bryan Nations publishes the project under the **Nations Systems** name. Nations Systems is a publishing/brand name here; no separate LLC or other registered entity is claimed.

The SolomonAI **software source code** covered by this release is distributed under the [Apache License, Version 2.0](LICENSE). **The official SolomonAI name, Nations Systems identity, logo, and favicon remain proprietary**, with the two bundled brand image assets expressly excluded from the Apache-2.0 copyright grant. See [BRANDING.md](BRANDING.md) for exact files, the limited permission for unchanged official distributions, and rebranding guidance for forks. This branding policy does not restrict the Apache-2.0-licensed source code.

Third-party components, models, libraries, and assets remain subject to their respective licenses. See [third-party notices](THIRD_PARTY_NOTICES.md) and the bundled attribution/license texts in `third_party_licenses/`. Python dependencies are installed from their upstream distributions rather than bundled.

Provided **as-is**, without warranties, response-time commitments, guaranteed compatibility, or individual installation support. Community discussion and contributions may be considered as resources permit. Nations Systems' primary product-development priorities remain separate from this community release.
