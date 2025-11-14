"""Page normalization for wiki content.

This module normalizes wiki pages by:
- Extracting all category tags and placing them after spoiler tags (if present) or at the top
- Deduplicating categories
- Removing multiple consecutive empty lines (max 1)
"""

import re
from typing import ClassVar


class PageNormalizer:
    """Normalize wiki page content."""

    LEGACY_CATEGORIES: ClassVar[set[str]] = {
        "[[Category:Duskenlight Coast]]",
        "[[Category:Duskenlight_Coast]]",
        "[[Category:Elderstone Mines]]",
        "[[Category:Loomingwood]]",
        "[[Category:The Bone Pits]]",
        "[[Category:Silkengrass_Meadowlands]]",
        "[[Category: Bosses]]",
        "[[Category: Enemies]]",
        "[[Category: Abyssal Lake]]",
        "[[Category: Faerie's Brake]]",
        "[[Category: Fernalla's Revival Plains]]",
        "[[Category: Hidden Hills]]",
        "[[Category: Island Tomb]]",
        "[[Category: Old Krakengard]]",
        "[[Category: Soluna's Landing]]",
        "[[Category: Stowaway's Step]]",
        "[[Category: Vendors]]",
    }

    def normalize(self, wikitext: str, new_wikitext: str | None = None) -> str:
        """Normalize wiki page content.

        Args:
            wikitext: Wiki page content (typically after preservation)
            new_wikitext: Newly generated content with fresh categories (optional)

        Returns:
            Normalized wikitext with merged categories at top and clean formatting
        """
        # Extract categories from both old and new content
        categories = self._extract_categories(wikitext)

        # If new content provided, merge its categories too
        if new_wikitext:
            new_categories = self._extract_categories(new_wikitext)
            # Merge while avoiding duplicates
            seen = set(categories)
            for cat in new_categories:
                if cat not in seen:
                    seen.add(cat)
                    categories.append(cat)

        # Filter out legacy categories
        categories = [cat for cat in categories if cat not in self.LEGACY_CATEGORIES]

        # Sort categories alphabetically
        categories.sort()

        # Remove categories from content
        content_without_categories = self._remove_categories(wikitext)

        # Normalize empty lines (max 1 consecutive)
        normalized_content = self._normalize_empty_lines(content_without_categories)

        # Strip leading/trailing whitespace to avoid extra empty lines
        normalized_content = normalized_content.strip()

        # Check if content starts with {{spoiler}} tag
        spoiler_match = re.match(r"^(\{\{spoiler\}\}\s*)", normalized_content)

        # Reassemble: If spoiler tag exists, put it first, then categories, then rest of content
        # Otherwise, categories at top, then content
        if categories:
            category_text = "\n".join(categories)
            if spoiler_match:
                # Extract spoiler tag and remaining content
                spoiler_tag = spoiler_match.group(1).rstrip()
                remaining_content = normalized_content[len(spoiler_match.group(0)) :]
                result = f"{spoiler_tag}\n{category_text}\n\n{remaining_content}"
            else:
                result = f"{category_text}\n\n{normalized_content}"
        else:
            result = normalized_content

        # Ensure page ends with newline (empty last line)
        if result and not result.endswith("\n"):
            result += "\n"

        return result

    def _extract_categories(self, wikitext: str) -> list[str]:
        """Extract all category tags from wikitext.

        Args:
            wikitext: Wiki page content

        Returns:
            Deduplicated list of category tags in original order
        """
        # Find all category tags
        category_pattern = r"\[\[Category:[^\]]+\]\]"
        matches = re.findall(category_pattern, wikitext)

        # Deduplicate while preserving order
        seen = set()
        categories = []
        for cat in matches:
            if cat not in seen:
                seen.add(cat)
                categories.append(cat)

        return categories

    def _remove_categories(self, wikitext: str) -> str:
        """Remove all category tags from wikitext.

        Args:
            wikitext: Wiki page content

        Returns:
            Wikitext with categories removed
        """
        # Remove category tags
        category_pattern = r"\[\[Category:[^\]]+\]\]\n?"
        return re.sub(category_pattern, "", wikitext)

    def _normalize_empty_lines(self, wikitext: str) -> str:
        """Normalize consecutive empty lines to max 1.

        Args:
            wikitext: Wiki page content

        Returns:
            Wikitext with normalized empty lines
        """
        # Replace 2+ consecutive newlines with just 2 (1 empty line)
        # This preserves paragraph breaks but removes excessive spacing
        return re.sub(r"\n{3,}", "\n\n", wikitext)
