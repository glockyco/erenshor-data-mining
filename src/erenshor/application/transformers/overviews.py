"""Overview page transformer.

Applies generated overview content to wiki pages using parser-driven
transformations.
"""

from __future__ import annotations

from erenshor.application.generators.base import GeneratedContent
from erenshor.application.transformers.base import PageTransformer

__all__ = ["OverviewTransformer"]


class OverviewTransformer(PageTransformer):
    """Transform overview pages (Weapons, Armor) with generated content.

    Responsibilities:
    1. Extract rendered overview table from GeneratedContent
    2. Locate the first section heading (===) or wikitable
    3. Replace everything from that point onward with new content
    4. Preserve any intro text before the first section/table
    5. Ensure datatable class is present on wikitables

    Logic extracted from update/overview_tables.py.
    """

    def transform(
        self,
        original: str,
        generated: GeneratedContent,
    ) -> str:
        """Transform overview page with generated content.

        Args:
            original: Original wiki page text (from cache)
            generated: Generated content from OverviewGenerator

        Returns:
            Updated wiki page text

        Raises:
            ValueError: If expected structure is missing
        """
        import re

        if not generated.rendered_blocks:
            raise ValueError("No rendered blocks in generated content")

        rendered_body = generated.rendered_blocks[0].text

        # First try to find section headings
        m = re.search(r"^===.+?===\s*$", original, flags=re.MULTILINE)
        if m:
            prefix = original[: m.start()].rstrip("\n") + "\n\n"
            new_text = (prefix + rendered_body).strip() + "\n"
            return self._ensure_datatable(new_text)

        # If no section headings, look for wikitable start
        m = re.search(r'^{\|\s*class="wikitable', original, flags=re.MULTILINE)
        if m:
            prefix = original[: m.start()].rstrip("\n") + "\n\n"
            new_text = (prefix + rendered_body).strip() + "\n"
            return self._ensure_datatable(new_text)

        raise ValueError("Page missing expected section headings (===) or wikitable")

    def _ensure_datatable(self, page_text: str) -> str:
        """Ensure all top-level table openings include the 'datatable' class.

        Args:
            page_text: Wiki page text

        Returns:
            Updated text with datatable class added to tables
        """
        import re

        lines = page_text.splitlines()
        out: list[str] = []
        table_open_re = re.compile(r"^\{\|(?P<attrs>.*)$")
        class_re = re.compile(r'\bclass\s*=\s*"([^"]*)"')

        for line in lines:
            m = table_open_re.match(line)
            if not m:
                out.append(line)
                continue

            attrs = m.group("attrs")
            cm = class_re.search(attrs)
            if cm:
                classes = cm.group(1)
                parts = [c for c in re.split(r"\s+", classes.strip()) if c]
                if "datatable" not in parts:
                    parts.append("datatable")
                new_classes = " ".join(parts)
                start, end = cm.span(1)
                new_attrs = attrs[:start] + new_classes + attrs[end:]
                out.append("{|" + new_attrs)
            else:
                spacer = " " if not attrs.startswith(" ") else ""
                new_attrs = f'{spacer}class="datatable"{attrs}'
                out.append("{|" + new_attrs)

        return "\n".join(out) + ("\n" if page_text.endswith("\n") else "")
