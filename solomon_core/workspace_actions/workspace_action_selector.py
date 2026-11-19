# -------------------------------------------------------------
# FILE: workspace_action_selector.py
# DIRECTORY: solomon_core/workspace_actions/
# -------------------------------------------------------------
# Embedding-backed workspace action selector.
#
# CONTRACT
#   Selects only approved registered workspace actions.
#   Does not decide Solomon authority, workflow routing, findings, or answers.
#   Returns an empty selection when confidence or margin is insufficient.
#   Consumes the canonical SIS-owned embedding model and never loads model
#   weights inside the Flask/web process.
# -------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from config import settings
from solomon_core.intelligence_service.intelligence_service_client import (
    execute_embeddings_via_intelligence_service,
)
from solomon_core.logger import get_logger

from .workspace_action_registry import (
    WorkspaceActionProfile,
    get_workspace_action_profiles,
)

logger = get_logger("workspace_action_selector")


@dataclass(frozen=True)
class WorkspaceActionSelection:
    approved: bool
    sequence: str
    action_id: str
    score: float
    margin: float
    elapsed_ms: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": "embedding_workspace_action_selector",
            "approved": self.approved,
            "sequence": self.sequence,
            "action_id": self.action_id,
            "score": round(float(self.score), 6),
            "margin": round(float(self.margin), 6),
            "elapsed_ms": round(float(self.elapsed_ms), 2),
            "reason": self.reason,
        }


def _empty_selection(
    reason: str,
    elapsed_ms: float = 0.0,
) -> WorkspaceActionSelection:
    return WorkspaceActionSelection(
        approved=False,
        sequence="",
        action_id="",
        score=0.0,
        margin=0.0,
        elapsed_ms=elapsed_ms,
        reason=reason,
    )


class WorkspaceActionSelector:
    def __init__(self) -> None:
        self._lock = RLock()
        self._ready = False
        self._profiles: List[WorkspaceActionProfile] = []
        self._profile_vectors: Optional[np.ndarray] = None

    def warm(self) -> WorkspaceActionSelection:
        start = perf_counter()

        if not settings.WORKSPACE_ACTION_SELECTOR_ENABLED:
            return _empty_selection("disabled", self._elapsed_ms(start))

        try:
            self._ensure_ready()
            self._warm_query_path()
        except Exception as exc:
            logger.exception(
                "[WORKSPACE_ACTION_SELECTOR][WARM_FAILED] error=%s",
                str(exc),
            )
            return _empty_selection("warm_failed", self._elapsed_ms(start))

        return WorkspaceActionSelection(
            approved=False,
            sequence="",
            action_id="",
            score=0.0,
            margin=0.0,
            elapsed_ms=self._elapsed_ms(start),
            reason="ready",
        )

    def select(
        self,
        *,
        task_text: str,
        command_context: Optional[Dict[str, Any]] = None,
        workspace_context: Optional[Dict[str, Any]] = None,
    ) -> WorkspaceActionSelection:
        start = perf_counter()

        clean_task = str(task_text or "").strip()
        if not clean_task:
            return _empty_selection("empty_input", self._elapsed_ms(start))

        if not settings.WORKSPACE_ACTION_SELECTOR_ENABLED:
            return _empty_selection("disabled", self._elapsed_ms(start))

        try:
            self._ensure_ready()
        except Exception as exc:
            logger.exception(
                "[WORKSPACE_ACTION_SELECTOR][LOAD_FAILED] error=%s",
                str(exc),
            )
            return _empty_selection("load_failed", self._elapsed_ms(start))

        selection_text = self._build_selection_text(
            task_text=clean_task,
            command_context=command_context or {},
            workspace_context=workspace_context or {},
        )

        try:
            query_vector = self._embed_texts(
                [selection_text],
                call_site="workspace_action_selector_query",
            )[0]
        except Exception as exc:
            logger.exception(
                "[WORKSPACE_ACTION_SELECTOR][QUERY_EMBED_FAILED] error=%s",
                str(exc),
            )
            return _empty_selection(
                "embedding_unavailable",
                self._elapsed_ms(start),
            )

        scores = np.dot(self._profile_vectors, query_vector.reshape(-1))

        ranked = np.argsort(scores)[::-1]
        best_index = int(ranked[0])
        second_index = int(ranked[1]) if len(ranked) > 1 else best_index

        best_profile = self._profiles[best_index]
        best_score = float(scores[best_index])
        second_score = (
            float(scores[second_index])
            if second_index != best_index
            else 0.0
        )
        margin = best_score - second_score

        elapsed_ms = self._elapsed_ms(start)

        if best_score < settings.WORKSPACE_ACTION_SELECTOR_MIN_SCORE:
            return WorkspaceActionSelection(
                approved=False,
                sequence="",
                action_id=best_profile.action_id,
                score=best_score,
                margin=margin,
                elapsed_ms=elapsed_ms,
                reason="score_below_threshold",
            )

        if margin < settings.WORKSPACE_ACTION_SELECTOR_MIN_MARGIN:
            return WorkspaceActionSelection(
                approved=False,
                sequence="",
                action_id=best_profile.action_id,
                score=best_score,
                margin=margin,
                elapsed_ms=elapsed_ms,
                reason="margin_below_threshold",
            )

        return WorkspaceActionSelection(
            approved=True,
            sequence=best_profile.sequence,
            action_id=best_profile.action_id,
            score=best_score,
            margin=margin,
            elapsed_ms=elapsed_ms,
            reason="approved",
        )

    def embed_texts(
        self,
        texts: Iterable[str],
    ) -> List[List[float]]:
        """Return normalized embeddings from the SIS-owned model."""

        clean_texts = [str(text or "").strip() for text in texts]
        if not clean_texts:
            return []
        if any(not text for text in clean_texts):
            raise ValueError("Embedding inputs must contain non-empty text.")

        vectors = self._embed_texts(
            clean_texts,
            call_site="workspace_embedding_compatibility",
        )
        return vectors.astype(np.float32).tolist()

    def _ensure_ready(self) -> None:
        if self._ready:
            return

        with self._lock:
            if self._ready:
                return

            profiles = list(get_workspace_action_profiles())
            if not profiles:
                raise RuntimeError(
                    "Workspace action selector has no registered profiles."
                )

            profile_vectors = self._embed_texts(
                [profile.description for profile in profiles],
                call_site="workspace_action_selector_profiles",
            )

            if profile_vectors.shape[0] != len(profiles):
                raise RuntimeError(
                    "Workspace action profile embedding count mismatch."
                )

            self._profiles = profiles
            self._profile_vectors = profile_vectors
            self._ready = True

            logger.info(
                "[WORKSPACE_ACTION_SELECTOR][READY] model=%s provider=sis profiles=%s",
                settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME,
                len(self._profiles),
            )

    def _warm_query_path(self) -> None:
        if not self._ready or self._profile_vectors is None:
            return

        warm_text = self._build_selection_text(
            task_text="Show me where I upload documents.",
            command_context={
                "module": "documents",
                "route": "/docs",
            },
            workspace_context={
                "active_section": "workspace",
            },
        )

        query_vector = self._embed_texts(
            [warm_text],
            call_site="workspace_action_selector_warmup",
        )[0]
        _ = np.dot(self._profile_vectors, query_vector.reshape(-1))

    def _embed_texts(
        self,
        texts: Iterable[str],
        *,
        call_site: str,
    ) -> np.ndarray:
        vectors = execute_embeddings_via_intelligence_service(
            texts,
            call_site=call_site,
        )
        array = np.asarray(vectors, dtype=np.float32)

        if array.ndim != 2:
            raise RuntimeError(
                "SIS embedding response had an invalid vector shape."
            )
        if array.shape[1] != int(settings.EMBED_DIM):
            raise RuntimeError(
                "SIS embedding response dimension does not match config.py."
            )

        return array

    def _build_selection_text(
        self,
        *,
        task_text: str,
        command_context: Dict[str, Any],
        workspace_context: Dict[str, Any],
    ) -> str:
        module = str(command_context.get("module") or "home").strip()
        route = str(command_context.get("route") or "/").strip()
        active_section = str(
            workspace_context.get("active_section") or ""
        ).strip()

        context_parts = [
            f"User request: {task_text}",
            f"Current module: {module}",
            f"Current route: {route}",
        ]

        if active_section:
            context_parts.append(
                f"Active workspace section: {active_section}"
            )

        return "\n".join(context_parts)

    def _elapsed_ms(self, start: float) -> float:
        return (perf_counter() - start) * 1000.0


_SELECTOR = WorkspaceActionSelector()


def warm_workspace_action_selector() -> WorkspaceActionSelection:
    return _SELECTOR.warm()


def select_workspace_action(
    *,
    task_text: str,
    command_context: Optional[Dict[str, Any]] = None,
    workspace_context: Optional[Dict[str, Any]] = None,
) -> WorkspaceActionSelection:
    return _SELECTOR.select(
        task_text=task_text,
        command_context=command_context,
        workspace_context=workspace_context,
    )


def embed_workspace_text(text: str) -> List[float]:
    """Return one normalized embedding from the SIS-owned workspace model."""

    vectors = _SELECTOR.embed_texts([text])
    if not vectors:
        return []
    return vectors[0]


def embed_workspace_texts(
    texts: Iterable[str],
) -> List[List[float]]:
    """Return normalized embeddings from the SIS-owned workspace model."""

    return _SELECTOR.embed_texts(texts)
