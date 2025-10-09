"""Fishing page transformer.

Applies generated fishing content to the Fishing wiki page using parser-driven
transformations.
"""

from __future__ import annotations

from erenshor.application.generators.base import GeneratedContent
from erenshor.application.transformers.base import PageTransformer

__all__ = ["FishingTransformer"]


class FishingTransformer(PageTransformer):
    """Transform Fishing page with generated content.

    Responsibilities:
    1. Extract rendered fishing body from GeneratedContent
    2. Locate the expected header (=List of Fishing Locations=)
    3. Replace everything from that header onward with new content
    4. Preserve any intro text before the header

    Logic extracted from update/fishing_updater.py.
    """

    def transform(
        self,
        original: str,
        generated: GeneratedContent,
    ) -> str:
        """Transform Fishing page with generated content.

        Args:
            original: Original wiki page text (from cache)
            generated: Generated content from FishingGenerator

        Returns:
            Updated wiki page text

        Raises:
            ValueError: If expected header is missing
        """
        import re

        if not generated.rendered_blocks:
            raise ValueError("No rendered blocks in generated content")

        rendered_body = generated.rendered_blocks[0].text

        # Expect a top-level section header exactly named '=List of Fishing Locations='
        h = re.search(
            r"^=\s*List of Fishing Locations\s*=\s*$", original, flags=re.MULTILINE
        )
        if not h:
            raise ValueError(
                "Fishing page missing expected '=List of Fishing Locations=' header"
            )

        prefix = original[: h.start()].rstrip("\n") + "\n\n"
        return (prefix + rendered_body).strip() + "\n"
