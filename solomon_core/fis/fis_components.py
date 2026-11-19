# ------------------------------------------------------------------
# FILE: solomon_core/fis/fis_components.py
# DIRECTORY: solomon_core/fis/
# ------------------------------------------------------------------

from __future__ import annotations

import hashlib
import string
from typing import List

from .fis_types import (
    FISToken,
    FISValidationResult,
    FISTokenStatus,
    FISFingerprintResult,
)


# ------------------------------------------------------------------
# Tokenization
# ------------------------------------------------------------------

def tokenize(raw_input: str) -> List[str]:
    if not isinstance(raw_input, str):
        return []
    return raw_input.split()


# ------------------------------------------------------------------
# Normalization (FIXED)
# ------------------------------------------------------------------

def normalize(token: str) -> str:
    if not isinstance(token, str):
        return ""

    normalized = token.strip().lower()

    # Remove non-printable characters
    normalized = "".join(ch for ch in normalized if ch.isprintable())

    # Strip punctuation from edges only
    normalized = normalized.strip(string.punctuation)

    return normalized


# ------------------------------------------------------------------
# Admissibility Validation (PURE STRUCTURAL SIGNAL)
# ------------------------------------------------------------------

def validate(token: FISToken) -> FISValidationResult:
    normalized = token.normalized

    if not normalized:
        return FISValidationResult(
            token=token,
            status=FISTokenStatus.REJECTED,
            reason="empty_normalized_token",
        )

    length = len(normalized)

    if length < 2:
        return FISValidationResult(
            token=token,
            status=FISTokenStatus.REJECTED,
            reason="token_too_short",
        )

    if length > 128:
        return FISValidationResult(
            token=token,
            status=FISTokenStatus.REJECTED,
            reason="token_too_long",
        )

    # Must contain at least one alphanumeric
    if not any(ch.isalnum() for ch in normalized):
        return FISValidationResult(
            token=token,
            status=FISTokenStatus.REJECTED,
            reason="no_alphanumeric_characters",
        )

    # ------------------------------------------------------------------
    # 🔒 STRUCTURAL SIGNAL FILTER (FINAL)
    #
    # Accept if:
    #   (A) Strong consonant cluster (>=3 in a row) → supports dns, tcp, http
    #   OR
    #   (B) Natural word structure:
    #         - length >= 5
    #         - at least 2 vowels
    #
    # Rejects:
    #   what, is, can, you, does, why, it
    #
    # No keyword lists
    # No semantic interpretation
    # Pure structural identity
    # ------------------------------------------------------------------

    vowels = set("aeiou")

    vowel_count = sum(1 for ch in normalized if ch in vowels)

    max_consonant_run = 0
    current_run = 0

    for ch in normalized:
        if ch.isalpha() and ch not in vowels:
            current_run += 1
            if current_run > max_consonant_run:
                max_consonant_run = current_run
        else:
            current_run = 0

    has_strong_cluster = max_consonant_run >= 3
    has_word_structure = length >= 5 and vowel_count >= 2

    if not (has_strong_cluster or has_word_structure):
        return FISValidationResult(
            token=token,
            status=FISTokenStatus.REJECTED,
            reason="insufficient_structural_signal",
        )

    return FISValidationResult(
        token=token,
        status=FISTokenStatus.VALID,
        reason=None,
    )


# ------------------------------------------------------------------
# Fingerprinting
# ------------------------------------------------------------------

def fingerprint(token: FISToken) -> FISFingerprintResult:
    normalized = token.normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    return FISFingerprintResult(
        token=token,
        fingerprint=digest,
    )