"""
File: solomon_core/docintel/segmentation/chunk_policy.py
Phase: 54 — Document Intelligence System Completion
Purpose: Mechanical policies for chunk formation

This module defines explicit, mechanical rules for how text is segmented
into chunks. Policies here are structural only and must never encode
semantic judgment, relevance, or intent.

CRITICAL INVARIANTS:
- Chunking is deterministic and repeatable
- No semantic heuristics or scoring
- No LLM usage
- Policy decisions are explicit and configurable
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from solomon_core.docintel.segmentation.chunk import Chunk
from solomon_core.docintel.parsing.raw_text_blocks import RawTextBlock


@dataclass(frozen=True)
class ChunkPolicy:
    """
    Defines mechanical limits for chunk construction.

    This policy answers:
        "How big may a chunk be?"

    It does NOT answer:
        - What text is important
        - Where meaning changes
    """

    max_chars: int
    overlap_chars: int = 0

    def assert_valid(self) -> None:
        if self.max_chars <= 0:
            raise ValueError("max_chars must be > 0")
        if self.overlap_chars < 0:
            raise ValueError("overlap_chars must be >= 0")
        if self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars must be < max_chars")


def chunk_raw_blocks(
    *,
    raw_blocks: Iterable[RawTextBlock],
    policy: ChunkPolicy,
) -> List[Chunk]:
    """
    Deterministically segment RawTextBlock objects into Chunks.

    Args:
        raw_blocks: Iterable of RawTextBlock
        policy: ChunkPolicy defining mechanical limits

    Returns:
        List[Chunk]
    """

    policy.assert_valid()

    chunks: List[Chunk] = []

    for block in raw_blocks:
        block.assert_valid()

        text = "".join(span.text for span in block.spans)
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + policy.max_chars, len(text))
            chunk_text = text[start:end]

            chunk = Chunk(
                document_id=block.document_id,
                page_index=block.page_index,
                chunk_index=chunk_index,
                text=chunk_text,
                start_offset=start,
                end_offset=end,
                source_block_id=block.block_id,
            )

            chunk.assert_valid()
            chunks.append(chunk)

            if policy.overlap_chars > 0:
                start = end - policy.overlap_chars
            else:
                start = end

            chunk_index += 1

    return chunks
