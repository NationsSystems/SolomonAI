<!-- -------------------------------------------------------------------
FILE: README.md
DIRECTORY: solomon_workspace/
-------------------------------------------------------------------- -->

# Solomon Workspace Substrate

`solomon_workspace` contains Solomon-native workspace tools that run on top of the protected Solomon drivetrain.

This folder is the common workspace substrate for professional consoles. It is not the Solomon core, not a domain library, not a frontend-only layer, and not an office-suite clone.

## Purpose

The workspace substrate provides reusable professional tools that allow Solomon to operate inside a real working environment.

It owns common workspace capabilities such as:

- document identity
- document metadata
- document sessions
- viewer packets
- workspace panels
- open, close, focus, and minimize actions
- active workspace context
- active document context

These tools are shared by future professional consoles such as construction, legal, accounting, property management, and other Nations Systems libraries.

## Boundary

`solomon_core` defines authority, orchestration, validation, and action permission.

`solomon_workspace` owns reusable workspace applications and state.

`webui` renders the visual experience.

Professional libraries and skills consume the workspace layer without owning it.

## Design Rule

The workspace substrate should behave like a Program Files layer.

It contains installed/common workspace capabilities that Solomon can use, but it does not become the protected drivetrain.

## Current Tool Families

### Documents

Document files define what a workspace document is, what type it has, how it is identified, and how it participates in a workspace session.

### Viewers

Viewer files prepare backend-neutral viewer packets for supported document types.

Initial viewer targets:

- PDF Viewer
- Image Viewer
- Text Document Viewer
- Spreadsheet Viewer

These are Solomon-native viewers, not branded replacements for Word, Excel, Acrobat, Google Drive, or OneDrive.

### Panels

Panel files define workspace object visibility and focus state at the product level.

The frontend renders panels, but the workspace layer defines the state contract.

### Actions

Action files define reusable workspace operations such as opening, closing, focusing, and minimizing workspace documents.

### Context

Context files expose the current workspace state to SolomonAI in a controlled way.

This allows SolomonAI to know which document or workspace object is active without contaminating the core drivetrain.

## First Milestone

The first implementation milestone is:

Open a PDF as a Solomon workspace document, track it as the active document, display it in a workspace panel, allow it to close, and expose active-document context to SolomonAI.