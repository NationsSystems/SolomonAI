# -------------------------------------------------------------------
# FILE: workspace_reader_docx_xml.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# XML fallback extraction for first-party DOCX workspace previews.
# -------------------------------------------------------------------

from typing import List
from xml.etree import ElementTree

from solomon_core.workspace_reader.workspace_reader_docx_preview import (
    get_xml_local_name,
    load_docx_preview_xml_parts,
    normalize_preview_text_block,
)


def extract_docx_paragraph_text(paragraph) -> str:
    """Extract plain text from one DOCX paragraph XML node."""

    fragments = []

    for element in paragraph.iter():
        local_name = get_xml_local_name(element.tag)

        if local_name == "t":
            fragments.append(element.text or "")
        elif local_name == "tab":
            fragments.append("\t")
        elif local_name in {"br", "cr"}:
            fragments.append("\n")

    return normalize_preview_text_block("".join(fragments))


def build_docx_preview_blocks_from_xml_parts(
    source_path: str,
    *,
    request_id: str,
) -> List[str]:
    """Build fallback DOCX text blocks directly from visible XML parts."""

    blocks: List[str] = []

    for _part_name, document_xml in load_docx_preview_xml_parts(
        source_path,
        request_id=request_id,
    ):
        root = ElementTree.fromstring(document_xml)

        for element in root.iter():
            if get_xml_local_name(element.tag) != "p":
                continue

            block = extract_docx_paragraph_text(element)

            if block:
                blocks.append(block)

    return blocks