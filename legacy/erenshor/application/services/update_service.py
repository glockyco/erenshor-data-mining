"""Update service for orchestrating wiki content updates.

Coordinates the complete update pipeline:

1. Generate content (via ContentGenerator)
2. Transform pages (via PageTransformer)
3. Validate content (via ContentValidator, optional)
4. Write to storage (via PageStorage)
5. Stream progress events

Sits between the CLI (presentation) and core logic (domain), handling
orchestration, error recovery, and state management.
"""

from __future__ import annotations

import logging
import time
from typing import Iterator

from sqlalchemy.engine import Engine

from erenshor.application.generators.base import ContentGenerator, GeneratedContent
from erenshor.application.transformers.base import PageTransformer
from erenshor.domain.entities.page import WikiPage
from erenshor.domain.events import UpdateEvent
from erenshor.domain.validation.base import ContentValidator
from erenshor.domain.value_objects.entity_type import EntityType
from erenshor.infrastructure.storage.page_storage import PageStorage
from erenshor.registry.core import WikiRegistry

__all__ = ["UpdateService"]


logger = logging.getLogger(__name__)


class UpdateService:
    """Orchestrates wiki content update operations.

    Coordinates all components needed for updates:
    - ContentGenerator: Generates content from database
    - PageTransformer: Applies content to existing pages
    - ContentValidator: Validates structure and completeness
    - PageStorage: Reads cached pages and writes updated pages
    - WikiRegistry: Maps entities to pages and manages page IDs

    Streams UpdateEvent instances to enable real-time progress tracking:
    - Live progress bars
    - Granular status updates per entity
    - Early termination on errors
    - Memory-efficient processing

    Example usage:
        ```python
        generator = ItemGenerator(renderer)
        transformer = ItemTransformer(parser, merger)
        validator = ItemValidator()

        service = UpdateService(
            generator=generator,
            transformer=transformer,
            validator=validator,
            cache_storage=cache_storage,
            output_storage=output_storage,
            registry=registry,
        )

        for event in service.update_pages(engine, skip_validation=False):
            if isinstance(event, ContentGenerated):
                print(f"Generated: {event.page_title}")
            elif isinstance(event, PageUpdated):
                print(f"Updated: {event.page_title}")
            elif isinstance(event, UpdateComplete):
                print(f"Done: {event.updated} updated, {event.failed} failed")
        ```

    Design principles:
    - Streaming: Process one entity at a time (memory efficient)
    - Event-driven: Emit events for progress tracking
    - Fail gracefully: Continue processing on per-entity errors
    - No business logic: Delegate to generators/transformers/validators
    """

    def __init__(
        self,
        generator: ContentGenerator,
        transformer: PageTransformer,
        validator: ContentValidator | None,
        cache_storage: PageStorage,
        output_storage: PageStorage,
        registry: WikiRegistry,
    ) -> None:
        """Initialize update service with all dependencies.

        Args:
            generator: Content generator for this content type
            transformer: Page transformer for this content type
            validator: Optional content validator (None to skip validation)
            cache_storage: Storage for reading cached wiki pages
            output_storage: Storage for writing updated wiki pages
            registry: Wiki registry for entity-to-page mapping
        """
        self._generator = generator
        self._transformer = transformer
        self._validator = validator
        self._cache = cache_storage
        self._output = output_storage
        self._registry = registry

    def _merge_multi_entity_page(
        self,
        original: str,
        generated_list: list[GeneratedContent],
        page: WikiPage,
    ) -> str:
        """Merge multiple entities into a single page.

        When multiple entities (e.g., skill + spell) map to the same page,
        combine their generated content into one page with multiple infoboxes.

        This method PRESERVES all content outside the {{Ability}} infoboxes:
        - Content before the first infobox
        - Content between infoboxes
        - Content after the last infobox

        Args:
            original: Original wiki page content from cache
            generated_list: List of generated content (2+ entities for same page)
            page: WikiPage object for this page

        Returns:
            Combined page content with all infoboxes updated and manual content preserved

        Algorithm:
            1. Parse original to find all {{Ability}} templates
            2. Sort generated content (SKILL before SPELL for abilities)
            3. Replace each existing template in order
            4. If more generated than templates, append extras
            5. If more templates than generated, remove extras
            6. Preserve all content outside templates (parser-driven)
        """
        from erenshor.shared.wiki_parser import (
            find_templates as mw_find_templates,
        )
        from erenshor.shared.wiki_parser import (
            parse as mw_parse,
        )
        from erenshor.shared.wiki_parser import (
            replace_template_with_text as mw_replace_template,
        )

        # Sort entities: SKILL before SPELL (for abilities)
        # For other entity types, maintain generation order
        def sort_key(gen: GeneratedContent) -> int:
            """Sort key: skills first (0), then spells (1), then others (2)."""
            if gen.entity_ref.entity_type == EntityType.SKILL:
                return 0
            elif gen.entity_ref.entity_type == EntityType.SPELL:
                return 1
            else:
                return 2

        sorted_list = sorted(generated_list, key=sort_key)

        # Extract rendered infoboxes from generated content
        infoboxes: list[str] = []
        for generated in sorted_list:
            if not generated.rendered_blocks:
                continue
            infobox = generated.rendered_blocks[0].text
            infoboxes.append(infobox.strip())

        if not infoboxes:
            # No content generated - return original unchanged
            return original

        # Parse original to find existing {{Ability}} templates
        try:
            code = mw_parse(original)
        except Exception as exc:
            # If parsing fails, fall back to simple concatenation
            # (better than losing all content)
            logger.warning(
                f"Failed to parse multi-entity page {page.title}: {exc}. "
                "Using simple concatenation."
            )
            combined = "\n\n".join(infoboxes)
            # Try to preserve original content after infoboxes
            if original.strip():
                # Find where the original templates likely end
                # This is a fallback heuristic - not perfect but better than nothing
                last_template_end = original.rfind("}}")
                if last_template_end > 0:
                    remaining = original[last_template_end + 2 :].lstrip("\n")
                    if remaining:
                        return combined + "\n\n" + remaining
            return combined + "\n\n"

        existing_templates = mw_find_templates(code, ["Ability"])

        # Replace existing templates with generated infoboxes
        text = original
        for i, infobox in enumerate(infoboxes):
            if i < len(existing_templates):
                # Replace existing template in place
                try:
                    code_i = mw_parse(text)
                    templates = mw_find_templates(code_i, ["Ability"])
                    if templates and i < len(templates):
                        text = mw_replace_template(
                            code_i, templates[i], infobox.rstrip("\n")
                        )
                except Exception as exc:
                    logger.warning(
                        f"Failed to replace Ability template {i} in {page.title}: {exc}"
                    )
            else:
                # More generated content than existing templates - append at end
                # Insert before any trailing content
                try:
                    code_append = mw_parse(text)
                    templates_append = mw_find_templates(code_append, ["Ability"])
                    if templates_append:
                        # Find position after last template
                        last_tpl = templates_append[-1]
                        tpl_str = str(last_tpl)
                        pos = text.find(tpl_str)
                        if pos >= 0:
                            end_pos = pos + len(tpl_str)
                            # Insert new template after last existing one
                            text = (
                                text[:end_pos]
                                + "\n\n"
                                + infobox.strip()
                                + "\n\n"
                                + text[end_pos:].lstrip("\n")
                            )
                    else:
                        # No templates found - prepend
                        text = infobox.strip() + "\n\n" + text.lstrip("\n")
                except Exception as exc:
                    logger.warning(
                        f"Failed to append Ability template {i} in {page.title}: {exc}"
                    )

        # Remove any extra templates (more templates than generated content)
        if len(existing_templates) > len(infoboxes):
            try:
                code_final = mw_parse(text)
                templates_final = mw_find_templates(code_final, ["Ability"])
                # Remove templates beyond what we generated
                for extra_tpl in templates_final[len(infoboxes) :]:
                    code_final.replace(extra_tpl, "")
                text = str(code_final)
            except Exception as exc:
                logger.warning(
                    f"Failed to remove extra Ability templates in {page.title}: {exc}"
                )

        return text

    def update_pages(
        self,
        engine: Engine,
        *,
        skip_validation: bool = False,
        validate_only: bool = False,
        dry_run: bool = False,
        filter: str | None = None,
    ) -> Iterator[UpdateEvent]:
        """Update all pages for this content type.

        Orchestrates the complete pipeline:

        1. Generate content (stream from generator)
        2. Group generated content by page title (handles multi-entity pages)
        3. For each page:
           a. Emit ContentGenerated events for all entities on that page
           b. Resolve or register page in registry
           c. Read original content from cache
           d. Transform page (apply all generated content)
           e. Validate (if not skipped)
           f. Write to output storage
           g. Emit PageUpdated/ValidationFailed/UpdateFailed event
        4. Save registry (persist any new pages)
        5. Emit UpdateComplete event with statistics

        Args:
            engine: SQLAlchemy engine for database queries
            skip_validation: If True, skip validation step (faster but less safe)
            validate_only: If True, only validate content without writing files
            dry_run: If True, skip writing files but show what would change
            filter: Optional filter string (name or 'id:1234') to process specific entities

        Yields:
            UpdateEvent instances (ContentGenerated, PageUpdated, etc.)

        Notes:
            - Multiple entities can map to the same page (multi-entity pages)
            - Processing continues on per-entity errors (fail gracefully)
            - Registry is saved at the end (atomic operation)
            - All events include enough context for logging/reporting
            - Validation errors block write but don't stop processing

        Example event stream:
            ```
            ContentGenerated(page_title="Time Stone", ...)
            PageUpdated(page_title="Time Stone", changed=True, ...)
            ContentGenerated(page_title="Envenomed Arrow", ...)  # skill
            ContentGenerated(page_title="Envenomed Arrow", ...)  # spell
            PageUpdated(page_title="Envenomed Arrow", changed=True, ...)  # merged page
            ...
            UpdateComplete(total=100, updated=98, failed=2, ...)
            ```
        """
        from erenshor.domain.events import (
            ContentGenerated,
            PageUpdated,
            UpdateComplete,
            UpdateFailed,
            ValidationFailed,
        )

        start_time = time.time()
        stats = {"generated": 0, "updated": 0, "unchanged": 0, "failed": 0}

        # Filter parameter is optional in ContentGenerator protocol
        generated_iter = self._generator.generate(engine, self._registry, filter=filter)

        # Group generated content by page title
        page_groups: dict[str, list[GeneratedContent]] = {}
        for generated in generated_iter:
            stats["generated"] += 1
            page_title = generated.page_title
            if page_title not in page_groups:
                page_groups[page_title] = []
            page_groups[page_title].append(generated)

        # Process each page
        for page_title, generated_list in page_groups.items():
            # Emit ContentGenerated event for each entity
            for generated in generated_list:
                yield ContentGenerated(
                    page_title=generated.page_title,
                    content_type=generated.entity_ref.entity_type.value,
                    byte_size=generated.total_bytes,
                )

            try:
                # Register all entities on this page
                page = None
                for generated in generated_list:
                    page = self._registry.resolve_entity(generated.entity_ref)
                    if not page:
                        page = self._registry.register_entity(
                            generated.entity_ref, page_title
                        )

                if not page:
                    raise ValueError(f"Failed to resolve or create page: {page_title}")

                original = self._cache.read(page) or ""

                # Transform page with all generated content
                if len(generated_list) == 1:
                    # Single entity - use transformer directly
                    updated = self._transformer.transform(original, generated_list[0])
                else:
                    # Multi-entity page - merge content
                    updated = self._merge_multi_entity_page(
                        original, generated_list, page
                    )

                # Validation step (always run unless skip_validation is True)
                if not skip_validation and self._validator:
                    validation = self._validator.validate(page, updated)
                    if not validation.passed:
                        yield ValidationFailed(
                            page_title=page.title,
                            violations=validation.violations,
                        )
                        stats["failed"] += 1
                        continue

                # Skip write step if validate_only or dry_run
                if not validate_only and not dry_run:
                    self._output.write(page, updated)

                changed = updated != original
                if changed:
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1

                yield PageUpdated(
                    page_title=page.title,
                    changed=changed,
                    validation_passed=True,
                )

            except Exception as exc:
                stats["failed"] += 1
                yield UpdateFailed(
                    page_title=page_title,
                    error=str(exc),
                )

        # Skip registry save if validate_only or dry_run
        if not validate_only and not dry_run:
            self._registry.save()

        duration = time.time() - start_time
        yield UpdateComplete(
            total=stats["generated"],
            updated=stats["updated"],
            unchanged=stats["unchanged"],
            failed=stats["failed"],
            duration_seconds=duration,
        )
