# -------------------------------------------------------------------
# FILE: workspace_reader_text_preview.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# First-party read-only TXT document preview helpers.
# -------------------------------------------------------------------

from pathlib import Path
from typing import List, Tuple

from solomon_core.logger import get_logger

logger = get_logger("workspace_reader.text_preview")

MAX_TEXT_PREVIEW_BYTES = 750_000
MAX_TEXT_PREVIEW_CHARS = 100_000
MAX_TEXT_PREVIEW_BLOCKS = 220
MAX_TEXT_BLOCK_CHARS = 1800

TEXT_ENCODING_ATTEMPTS = (
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin-1",
)


def get_text_preview_block_total_chars(blocks: List[str]) -> int:
    """Return the total rendered text preview character count."""

    return sum(len(str(block or "")) for block in blocks)


def _read_text_preview_bytes(source_path: str) -> Tuple[bytes, bool]:
    """Read a bounded byte sample for safe TXT preview."""

    path = Path(str(source_path or "").strip())
    file_size = path.stat().st_size
    truncated = file_size > MAX_TEXT_PREVIEW_BYTES

    with path.open("rb") as handle:
        return handle.read(MAX_TEXT_PREVIEW_BYTES), truncated


def _decode_text_preview_bytes(raw_bytes: bytes) -> Tuple[str, str]:
    """Decode TXT preview bytes using conservative local encodings."""

    if not raw_bytes:
        return "", "empty"

    for encoding in TEXT_ENCODING_ATTEMPTS:
        try:
            return raw_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    return raw_bytes.decode("utf-8", errors="replace"), "utf-8-replace"


def _clean_text_preview(text: str) -> str:
    """Normalize unsafe control characters while preserving readable layout."""

    normalized = str(text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\x00", " ")

    clean_chars = []

    for character in normalized:
        if character in ("\n", "\t"):
            clean_chars.append(character)
            continue

        if character.isprintable():
            clean_chars.append(character)

    clean_text = "".join(clean_chars)

    if len(clean_text) > MAX_TEXT_PREVIEW_CHARS:
        clean_text = clean_text[:MAX_TEXT_PREVIEW_CHARS].rstrip()

    return clean_text.strip()


def _split_large_block(block: str) -> List[str]:
    """Split a large text block into bounded preview chunks."""

    clean_block = str(block or "").strip()

    if len(clean_block) <= MAX_TEXT_BLOCK_CHARS:
        return [clean_block] if clean_block else []

    chunks: List[str] = []
    start = 0

    while start < len(clean_block):
        chunk = clean_block[start:start + MAX_TEXT_BLOCK_CHARS].strip()

        if chunk:
            chunks.append(chunk)

        start += MAX_TEXT_BLOCK_CHARS

    return chunks


def _split_text_preview_blocks(text: str) -> List[str]:
    """Split normalized TXT content into bounded readable blocks."""

    if not text:
        return ["This text document is empty."]

    lines = [line.rstrip() for line in text.split("\n")]
    raw_blocks: List[str] = []
    active_lines: List[str] = []

    for line in lines:
        if line.strip():
            active_lines.append(line)
            continue

        if active_lines:
            raw_blocks.append("\n".join(active_lines).strip())
            active_lines = []

    if active_lines:
        raw_blocks.append("\n".join(active_lines).strip())

    if not raw_blocks:
        raw_blocks = [text.strip()]

    preview_blocks: List[str] = []

    for block in raw_blocks:
        if len(preview_blocks) >= MAX_TEXT_PREVIEW_BLOCKS:
            break

        for chunk in _split_large_block(block):
            if len(preview_blocks) >= MAX_TEXT_PREVIEW_BLOCKS:
                break

            preview_blocks.append(chunk)

    return preview_blocks or ["This text document is empty."]


def build_text_preview_blocks(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> Tuple[List[str], bool]:
    """Build safe first-party TXT preview text blocks."""

    clean_path = str(source_path or "").strip()
    raw_bytes, byte_truncated = _read_text_preview_bytes(clean_path)
    decoded_text, encoding = _decode_text_preview_bytes(raw_bytes)
    clean_text = _clean_text_preview(decoded_text)
    char_truncated = len(str(decoded_text or "")) > MAX_TEXT_PREVIEW_CHARS
    preview_blocks = _split_text_preview_blocks(clean_text)
    block_truncated = len(preview_blocks) >= MAX_TEXT_PREVIEW_BLOCKS
    truncated = byte_truncated or char_truncated or block_truncated

    logger.info(
        "[workspace.reader.text_preview_ready] request_id=%s path=%s "
        "encoding=%s blocks=%s rendered_chars=%s truncated=%s",
        request_id,
        Path(clean_path).name,
        encoding,
        len(preview_blocks),
        get_text_preview_block_total_chars(preview_blocks),
        truncated,
    )

    return preview_blocks, truncated