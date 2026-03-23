"""Quest guide generator — thin orchestrator.

Delegates to repository (data loading), assembler (guide construction),
levels (level estimation), and serializer (JSON output).
"""

from __future__ import annotations

from pathlib import Path

from .schema import GuideOutput
from .serializer import guides_to_json

__all__ = ["generate", "guides_to_json"]


def generate(db_path: Path) -> GuideOutput:
    """Load quest data, assemble guides, compute levels, return v3 output."""
    from .assembler import assemble_guides
    from .levels import compute_levels
    from .repository import load_quest_data, materialize_sub_trees

    ctx = load_quest_data(db_path)
    guides = assemble_guides(ctx)
    compute_levels(guides, ctx)
    materialize_sub_trees(guides, ctx)
    return GuideOutput(
        version=3,
        zone_lookup=ctx.zone_lookup,
        character_spawns=ctx.character_spawns,
        zone_lines=ctx.zone_lines,
        chain_groups=ctx.chain_groups,
        quests=guides,
    )
