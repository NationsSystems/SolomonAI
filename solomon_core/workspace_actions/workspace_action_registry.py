# -------------------------------------------------------------
# FILE: solomon_core/workspace_actions/workspace_action_registry.py
# DIRECTORY: solomon_core/workspace_actions/
# -------------------------------------------------------------
# Approved workspace action registry.
#
# CONTRACT
#   This file defines the only visual workspace sequences the selector
#   may return. Descriptions are semantic profiles for closed-set matching;
#   they are not keyword routing rules.
# -------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class WorkspaceActionProfile:
    action_id: str
    sequence: str
    description: str
    enabled: bool = True


_APPROVED_WORKSPACE_ACTIONS: Tuple[WorkspaceActionProfile, ...] = (
    WorkspaceActionProfile(
        action_id="home_console",
        sequence="show_home_console",
        description=(
            "Return the user to the main Nations Systems command console, "
            "home screen, primary dashboard, or central workspace landing area."
        ),
    ),
    WorkspaceActionProfile(
        action_id="documents_workspace",
        sequence="show_documents_workspace",
        description=(
            "Open the document workspace where the user can upload, view, "
            "inspect, organize, and manage company files, PDFs, office "
            "documents, spreadsheets, text files, source documents, and "
            "business records."
        ),
    ),
    WorkspaceActionProfile(
        action_id="text_review_area",
        sequence="show_text_review_area",
        description=(
            "Open the workspace area for pasted business text, notes, "
            "messages, summaries, clauses, comments, instructions, and "
            "manually entered text that should be reviewed or improved."
        ),
    ),
    WorkspaceActionProfile(
        action_id="review_start_action",
        sequence="show_review_start_action",
        description=(
            "Bring the governed review start action into focus when the user "
            "is ready to run, start, submit, or launch Document Analysis after "
            "documents or pasted text are prepared."
        ),
    ),
    WorkspaceActionProfile(
        action_id="solomon_assistant",
        sequence="show_solomon_assistant",
        description=(
            "Bring the SolomonAI assistant panel into focus when the user wants "
            "to ask Solomon a question, type to the assistant, find the chat "
            "panel, or use workspace-aware guidance."
        ),
    ),
    WorkspaceActionProfile(
        action_id="document_analysis",
        sequence="open_document_analysis",
        description=(
            "Open or launch the Document Analysis workflow for selected files, "
            "document summaries, issue detection, missing information, notable "
            "details, decision-ready risk signals, and governed review output."
        ),
    ),
    WorkspaceActionProfile(
        action_id="guided_walkthrough",
        sequence="start_guided_walkthrough",
        description=(
            "Start a guided walkthrough, orientation, tour, or workspace "
            "explanation that shows the user where important areas and actions "
            "are located."
        ),
    ),
    WorkspaceActionProfile(
        action_id="clear_guidance",
        sequence="clear_guidance",
        description=(
            "Clear active visual guidance, remove highlights, stop the "
            "walkthrough, reset guidance state, or return the workspace to a "
            "neutral visual state."
        ),
    ),
)


def get_workspace_action_profiles() -> Tuple[WorkspaceActionProfile, ...]:
    return tuple(profile for profile in _APPROVED_WORKSPACE_ACTIONS if profile.enabled)


def get_approved_workspace_sequences() -> frozenset[str]:
    return frozenset(profile.sequence for profile in get_workspace_action_profiles())