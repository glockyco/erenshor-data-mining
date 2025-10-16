"""Base class for page transformers.

Page transformers apply generated content to existing wiki pages using
mwparserfromhell for parser-driven AST manipulation, ensuring deterministic
and idempotent updates without marker comments.
"""

from __future__ import annotations

from erenshor.application.generators.base import GeneratedContent

__all__ = ["PageTransformer"]


class PageTransformer:
    """Base class for page content transformers.

    Responsibilities:
    1. Parsing the original page (mwparserfromhell)
    2. Locating templates to replace (infoboxes, tables)
    3. Merging manual fields when appropriate
    4. Placing templates in correct locations
    5. Removing outdated templates
    6. Returning updated wikitext

    Design principles:
    - Parser-driven: All edits use AST manipulation, no regex on wikitext
    - No markers: Templates placed by structure, not comments
    - Idempotent: Re-running produces identical output
    - Deterministic: Same input always produces same output

    Example:
        ```python
        class ItemTransformer(PageTransformer):
            def transform(
                self,
                original: str,
                generated: GeneratedContent
            ) -> str:
                snippets = self._extract_snippets(generated)
                code = mwparserfromhell.parse(original)
                self._replace_infobox(code, snippets["infobox"])
                self._ensure_fancy_table(code, snippets["table"])
                return str(code)
        ```

    Notes:
        - Preserve existing content where appropriate
        - Manual field preservation is type-specific (see CLAUDE.md)
        - All parsing errors should be raised, not silently caught
    """

    def transform(
        self,
        original: str,
        generated: GeneratedContent,
    ) -> str:
        """Apply generated content to original page.

        Args:
            original: Original wiki page text (from cache)
            generated: Generated content from ContentGenerator

        Returns:
            Updated wiki page text with generated content applied

        Raises:
            ValueError: If page structure is invalid
            Any parsing errors should propagate to caller
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement transform()"
        )
