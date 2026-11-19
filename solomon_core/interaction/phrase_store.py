# solomon_core/interaction/phrase_store.py
# ---------------------------------------------------------------------
# Phase 31 — Phrase Store (DB-backed, Read-Only)
#
# PURPOSE:
#   • Load interaction phrasing from the database
#   • Provide deterministic, ordered phrase variants
#   • Serve the presentation layer ONLY
#
# GUARANTEES:
#   • Read-only access
#   • No business logic
#   • No language generation
#   • Deterministic ordering
#   • Safe to cache
#
# IMPORTANT:
#   • Core logic MUST NEVER import this module
#   • Uses existing Solomon SQLAlchemy session management
# ---------------------------------------------------------------------

from typing import List, Dict, Any
import json

from sqlalchemy import text

from solomon_core.db import SessionLocal


class PhraseStore:
    """
    Read-only phrase store for hybrid interaction rendering.
    """

    @staticmethod
    def get_variants(intent: str, field: str, version: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch active phrase variants for a given intent + field.

        Returns:
            List of dicts:
              [
                {
                  "variant_index": int,
                  "template": str,
                  "options": list[str]
                },
                ...
              ]
        """

        sql = text(
            """
            SELECT
                variant_index,
                template,
                options
            FROM interaction_phrases
            WHERE intent = :intent
              AND field = :field
              AND version = :version
              AND active = TRUE
            ORDER BY variant_index ASC
            """
        )

        session = SessionLocal()
        try:
            result = session.execute(
                sql,
                {
                    "intent": intent,
                    "field": field,
                    "version": version,
                },
            )

            rows = result.fetchall()
        finally:
            session.close()

        variants: List[Dict[str, Any]] = []

        for row in rows:
            options = row.options

            # MariaDB may return JSON as str
            if isinstance(options, str):
                options = json.loads(options)

            variants.append(
                {
                    "variant_index": row.variant_index,
                    "template": row.template,
                    "options": options,
                }
            )

        return variants
