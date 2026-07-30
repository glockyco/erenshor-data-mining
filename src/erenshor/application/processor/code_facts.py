"""Carry code_facts from raw to clean. The table's absence means the
extract step was skipped; that is an ordering error, not a soft case."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .writer import Writer

_ORDERING_ERROR = (
    "code_facts tables missing or empty in raw DB. Run 'erenshor extract code-facts' after 'erenshor extract export'."
)


def process_code_facts(raw: sqlite3.Connection, writer: Writer) -> None:
    """Copy code_facts + code_facts_meta verbatim (values stay TEXT).

    Raises ValueError if the raw tables are missing or the meta row is
    absent: code_facts runs first in the build, so this means the extract
    step was skipped and the pipeline order was violated.
    """
    try:
        fact_rows = [
            {"fact_id": r["fact_id"], "key": r["key"], "value": r["value"], "value_type": r["value_type"]}
            for r in raw.execute("SELECT fact_id, key, value, value_type FROM code_facts").fetchall()
        ]
        meta = raw.execute(
            "SELECT assembly_sha256, extracted_at, game_build_id, game_build_published_at FROM code_facts_meta"
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise ValueError(_ORDERING_ERROR) from exc

    if meta is None:
        raise ValueError(_ORDERING_ERROR)

    writer.insert_code_facts(fact_rows)
    writer.insert_code_facts_meta(
        [
            {
                "assembly_sha256": meta["assembly_sha256"],
                "extracted_at": meta["extracted_at"],
                "game_build_id": meta["game_build_id"],
                "game_build_published_at": meta["game_build_published_at"],
            }
        ]
    )
    logger.info(
        f"code_facts: {len(fact_rows)} rows "
        f"(assembly {str(meta['assembly_sha256'])[:12]}, game build {meta['game_build_id'] or 'unknown'})"
    )
