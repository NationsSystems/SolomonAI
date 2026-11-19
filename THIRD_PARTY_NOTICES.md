# Bundled third-party components

The root `LICENSE` is the Apache License 2.0 for Nations Systems-controlled SolomonAI source. It does **not** override licenses for third-party components or assets. The files below are distributed under their respective upstream terms. Keep attribution/license files when redistributing these assets.

| Asset | Distributed file(s) | License and attribution |
| --- | --- | --- |
| Bootstrap 5.3.3 | `webui/static/vendor/bootstrap/js/bootstrap.bundle.min.js`, `webui/static/vendor/bootstrap/css/bootstrap.min.css` | MIT; Copyright 2011–2024 The Bootstrap Authors. [Full text](third_party_licenses/Bootstrap_MIT.txt); [upstream](https://github.com/twbs/bootstrap). |
| Marked 4.3.0 | `webui/static/vendor/marked/marked.min.js` | MIT; Copyright 2011–2023 Christopher Jeffrey (as indicated in the bundled file). [Full text](third_party_licenses/Marked_MIT.txt); [upstream](https://github.com/markedjs/marked). |
| Orbitron | `webui/static/fonts/Orbitron.woff2` | SIL Open Font License 1.1; Copyright 2018 The Orbitron Project Authors; Reserved Font Name “Orbitron”. [Full text](third_party_licenses/Orbitron_OFL.txt); [upstream](https://github.com/google/fonts/tree/main/ofl/orbitron). |
| Material Symbols Outlined | `webui/static/fonts/material-symbols-outlined-v309-latin-regular.woff2` | Apache License 2.0; Copyright 2025 Google LLC in the bundled font metadata. The [root Apache license](LICENSE) contains the license terms; [upstream guide](https://developers.google.com/fonts/docs/material_symbols). |

**Proprietary first-party branding:** `webui/static/img/OfficialNavLogo.png` and `webui/static/img/favicon.ico` are reserved brand assets, **not** licensed under the root Apache-2.0 software license. See [BRANDING.md](BRANDING.md) for limited distribution/display permission and fork rebranding requirements. The copyright/trademark status of those graphics is separate from the third-party licenses listed above; the repository owner is responsible for confirming any underlying third-party rights before publication.

Python libraries listed in the requirements files are fetched from upstream during setup; their own distributions retain their respective license obligations. External model weights are downloaded from the model provider and are not bundled. This list covers the directly **bundled non-project binaries and vendored frontend libraries** identified in the release candidate, not every runtime dependency or integration.
