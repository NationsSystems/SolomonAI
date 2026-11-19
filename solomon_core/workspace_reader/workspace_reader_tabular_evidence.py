# -------------------------------------------------------------------
# FILE: workspace_reader_tabular_evidence.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Shared row-preserving text evidence for read-only tabular Reader previews.
# -------------------------------------------------------------------

import json
from typing import Dict, List


TABULAR_EVIDENCE_CONTRACT = "source_row_column_pairs_v1"


def build_tabular_evidence_text_blocks(
    sheets: List[Dict],
    *,
    source_label: str,
    max_blocks: int,
    truncated_message: str,
) -> List[str]:
    """Return bounded row-preserving text evidence from Reader table previews.

    The evidence deliberately does not guess which source row is a header. Every
    populated source row remains explicit and every populated cell stays paired
    with its rendered column label so downstream intelligence can infer table
    semantics without losing row boundaries or merging neighboring records.
    """

    blocks: List[str] = []

    for sheet in sheets:
        if len(blocks) >= max_blocks:
            break

        sheet_name = str(sheet.get("name") or source_label).strip()
        data_range_label = str(
            sheet.get("data_range_label")
            or sheet.get("range_label")
            or "No readable cells"
        ).strip()
        blocks.append(
            f"{source_label}: {sheet_name} (data range {data_range_label})"
        )

        columns = [
            str(column or "").strip()
            for column in (sheet.get("columns") or [])
        ]

        for row in sheet.get("rows") or []:
            if len(blocks) >= max_blocks:
                break

            row_number = int(row.get("row_number") or 0)
            cells = list(row.get("cells") or [])
            cell_pairs: List[str] = []

            for column_index, cell in enumerate(cells):
                value = str(cell or "").strip()
                if not value:
                    continue

                column_label = (
                    columns[column_index]
                    if column_index < len(columns) and columns[column_index]
                    else f"Column {column_index + 1}"
                )
                cell_pairs.append(
                    f"{column_label}={json.dumps(value, ensure_ascii=False)}"
                )

            if not cell_pairs:
                continue

            row_label = row_number if row_number > 0 else "?"
            blocks.append(
                f"Source row {row_label}: " + " | ".join(cell_pairs)
            )

        if sheet.get("truncated") and len(blocks) < max_blocks:
            blocks.append(truncated_message)

    return blocks


__all__ = [
    "TABULAR_EVIDENCE_CONTRACT",
    "build_tabular_evidence_text_blocks",
]
