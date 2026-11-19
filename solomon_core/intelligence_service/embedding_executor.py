# -------------------------------------------------------------------
# FILE: embedding_executor.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# SIS-owned execution authority for Solomon's canonical local embedding model.
# Web application processes consume embeddings through the authenticated SIS
# transport and do not load Torch/Transformers embedding weights themselves.
# -------------------------------------------------------------------

from __future__ import annotations

from threading import RLock
from typing import Iterable

from config import settings
from solomon_core.logger import get_logger


logger = get_logger("intelligence_service.embedding_executor")


class EmbeddingExecutor:
    """Own one lazily loaded, process-local Qwen embedding runtime."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._ready = False
        self._tokenizer = None
        self._model = None
        self._torch = None
        self._device = "cpu"
        self._dimension = 0
        self._last_error = ""

    def execute(self, texts: Iterable[str]) -> list[list[float]]:
        clean_texts = [str(text or "").strip() for text in texts]
        if not clean_texts:
            return []
        if any(not text for text in clean_texts):
            raise ValueError("SIS embedding inputs must contain non-empty text.")

        self._ensure_ready()

        with self._lock:
            encoded = self._tokenizer(
                clean_texts,
                padding=True,
                truncation=True,
                max_length=int(settings.WORKSPACE_ACTION_SELECTOR_MAX_LENGTH),
                return_tensors="pt",
            )
            encoded = {
                key: value.to(self._device)
                for key, value in encoded.items()
            }

            with self._torch.inference_mode():
                output = self._model(**encoded)
                vectors = self._last_token_pool(
                    output.last_hidden_state,
                    encoded["attention_mask"],
                )
                vectors = self._torch.nn.functional.normalize(
                    vectors,
                    p=2,
                    dim=1,
                )

            self._sync_device()
            vectors = vectors.detach().float().cpu()

        if vectors.ndim != 2:
            raise RuntimeError("SIS embedding runtime returned an invalid tensor rank.")

        dimension = int(vectors.shape[1])
        expected_dimension = max(1, int(settings.EMBED_DIM))
        if dimension != expected_dimension:
            raise RuntimeError(
                "SIS embedding dimension mismatch: "
                f"expected {expected_dimension}, received {dimension}."
            )

        self._dimension = dimension
        self._last_error = ""
        return vectors.numpy().tolist()

    def get_snapshot(self) -> dict:
        status = (
            "ready"
            if self._ready
            else ("degraded" if self._last_error else "not_loaded")
        )
        return {
            "enabled": bool(settings.SIS_EMBEDDING_ENABLED),
            "ready": bool(self._ready),
            "status": status,
            "model": str(settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME),
            "device": self._device if self._ready else None,
            "dimension": self._dimension or int(settings.EMBED_DIM),
            "last_error": self._last_error,
        }

    def _ensure_ready(self) -> None:
        if self._ready:
            return

        with self._lock:
            if self._ready:
                return

            try:
                torch, AutoModel, AutoTokenizer = self._load_runtime_dependencies()
                model_path = settings.WORKSPACE_ACTION_SELECTOR_MODEL_PATH
                device = self._resolve_device(torch)

                tokenizer = AutoTokenizer.from_pretrained(
                    model_path,
                    local_files_only=(
                        settings.WORKSPACE_ACTION_SELECTOR_REQUIRE_LOCAL_FILES
                    ),
                    padding_side="left",
                )
                model = AutoModel.from_pretrained(
                    model_path,
                    local_files_only=(
                        settings.WORKSPACE_ACTION_SELECTOR_REQUIRE_LOCAL_FILES
                    ),
                )

                if (
                    device == "cuda"
                    and settings.WORKSPACE_ACTION_SELECTOR_DTYPE == "fp16"
                ):
                    model = model.half()

                model.to(device)
                model.eval()

                self._torch = torch
                self._tokenizer = tokenizer
                self._model = model
                self._device = device
                self._dimension = int(settings.EMBED_DIM)
                self._ready = True
                self._last_error = ""

                logger.info(
                    "[SIS][EMBEDDING_MODEL_READY] model=%s device=%s dimension=%s",
                    settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME,
                    self._device,
                    self._dimension,
                )
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("[SIS][EMBEDDING_MODEL_LOAD_FAILED]")
                raise

    def _load_runtime_dependencies(self):
        import torch

        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError:
            from transformers.models.auto.modeling_auto import AutoModel
            from transformers.models.auto.tokenization_auto import AutoTokenizer

        return torch, AutoModel, AutoTokenizer

    def _resolve_device(self, torch_module) -> str:
        configured = str(
            settings.WORKSPACE_ACTION_SELECTOR_DEVICE or "auto"
        ).lower()

        if configured == "auto":
            return "cuda" if torch_module.cuda.is_available() else "cpu"

        if configured == "cuda" and not torch_module.cuda.is_available():
            logger.warning(
                "[SIS][EMBEDDING_CUDA_UNAVAILABLE] falling_back_to=cpu"
            )
            return "cpu"

        return configured

    def _last_token_pool(self, last_hidden_state, attention_mask):
        left_padding = bool(
            (attention_mask[:, -1].sum() == attention_mask.shape[0]).item()
        )

        if left_padding:
            return last_hidden_state[:, -1, :]

        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_state.shape[0]
        return last_hidden_state[
            self._torch.arange(
                batch_size,
                device=last_hidden_state.device,
            ),
            sequence_lengths,
        ]

    def _sync_device(self) -> None:
        if self._device == "cuda":
            self._torch.cuda.synchronize()


_EXECUTOR = EmbeddingExecutor()


def execute_embeddings_on_local_runtime(
    texts: Iterable[str],
) -> list[list[float]]:
    """Return normalized embeddings from the one SIS-owned model runtime."""

    return _EXECUTOR.execute(texts)


def get_embedding_capacity_snapshot() -> dict:
    """Return non-authoritative model availability telemetry for SIS health."""

    return _EXECUTOR.get_snapshot()
