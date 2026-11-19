"""
File: solomon_core/docintel/parsing/raw_text_blocks.py
Phase: 54 — Document Intelligence System Completion
Purpose: Mechanical representation of extracted text blocks

This module defines raw, non-semantic text block structures produced by
document extractors. These blocks represent *what exists* in a document,
not what it means.

CRITICAL INVARIANTS:
- No interpretation, summarization, or analysis
- No LLM usage
- No execution or authorization concepts
- Blocks are positional and addressable
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class TextSpan:
    """
    Represents a contiguous span of text within a document region.
    """
    text: str
    start_offset: int
    end_offset: int

    def assert_valid(self) -> None:
        if self.start_offset < 0:
            raise ValueError("start_offset must be non-negative")
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset must be >= start_offset")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")


@dataclass(frozen=True)
class RawTextBlock:
    """
    Atomic extracted text block with positional context.
    """
    document_id: str
    page_index: int
    spans: List[TextSpan]
    source: str
    block_id: Optional[str] = None

    def assert_valid(self) -> None:
        if not self.document_id:
            raise ValueError("RawTextBlock missing document_id")
        if self.page_index < 0:
            raise ValueError("page_index must be >= 0")
        if not self.spans:
            raise ValueError("RawTextBlock must contain at least one TextSpan")
        if not self.source:
            raise ValueError("RawTextBlock missing source")
        for span in self.spans:
            span.assert_valid()
