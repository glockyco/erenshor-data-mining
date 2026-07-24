"""Wiki generate service for creating wiki pages locally.

This service handles generating wiki pages from database entities, merging with
fetched content, and preserving manual edits.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.progress import track

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    import mwparserfromhell
    import mwparserfromhell.nodes
    import mwparserfromhell.wikicode

    from erenshor.application.wiki.generators.base import GeneratedPage
    from erenshor.application.wiki.generators.context import GeneratorContext
    from erenshor.application.wiki.generators.registry import GeneratorRegistration

from erenshor.application.wiki.generators.field_preservation import FieldPreservationHandler
from erenshor.application.wiki.generators.legacy_template_remover import LegacyTemplateRemover
from erenshor.application.wiki.generators.page_normalizer import PageNormalizer
from erenshor.application.wiki.generators.registry import get_generators_by_name
from erenshor.application.wiki.services.helpers import normalise_generated_page_content
from erenshor.application.wiki.services.page import OperationResult


class WikiGenerateService:
    """Service for generating wiki pages locally."""

    def __init__(
        self,
        context: GeneratorContext,
        console: Console | None = None,
    ) -> None:
        """Initialize generate service with a shared generator context."""
        self._context = context
        self._storage = context.storage
        self._console = console or Console()

        # Handlers for preservation and normalization
        self._preservation_handler = FieldPreservationHandler()
        self._legacy_remover = LegacyTemplateRemover()
        self._page_normalizer = PageNormalizer()

        logger.debug("WikiGenerateService initialized")

    def generate_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        page_titles: list[str] | None = None,
        generator_names: list[str] | None = None,
        preflight: Callable[[Mapping[str, str]], None] | None = None,
    ) -> OperationResult:
        """Generate wiki pages using registered generators.

        Workflow:
        1. Instantiate generators from registry
        2. Each generator produces GeneratedPage objects
        3. Apply preservation and normalization
        4. Save to storage

        Args:
            dry_run: If True, generate content but don't save to storage.
            limit: Maximum number of pages to generate (for testing).
            page_titles: If specified, only generate these specific page titles. If None, generate all pages.
            generator_names: Optional list of generator names to use. If None, use all registered generators.
            preflight: Optional callback invoked with an immutable mapping of the exact
                successfully processed standard page titles and content.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(
            f"Generating wiki pages (dry_run={dry_run}, limit={limit}, "
            f"page_titles={len(page_titles) if page_titles else 'all'}, "
            f"generators={generator_names or 'all'})"
        )

        # Get (registration, generator) pairs from registry
        pairs = get_generators_by_name(self._context, generator_names)
        logger.debug(f"Using {len(pairs)} generators")

        # Separate pages by destination: output_dir generators write directly to
        # files (the generator handles its own field preservation); standard
        # generators go through the service's preservation/normalization pipeline.
        standard_pages: list[GeneratedPage] = []
        file_pairs: list[tuple[GeneratorRegistration, GeneratedPage]] = []

        for reg, generator in pairs:
            logger.debug(f"Running generator: {generator.__class__.__name__}")
            generated_pages = list(generator.generate_pages())
            logger.debug(f"  Generated {len(generated_pages)} pages")
            if reg.output_dir is not None:
                file_pairs.extend((reg, page) for page in generated_pages)
            else:
                standard_pages.extend(generated_pages)

        logger.info(f"Total pages generated: {len(standard_pages)} standard, {len(file_pairs)} to output_dir")

        # Remove stale storage entries on full unfiltered generation
        # (output_dir generators are not in storage, so exclude their titles)
        if not page_titles and not limit and not generator_names:
            valid_titles = {p.title for p in standard_pages}
            removed = self._storage.remove_stale_pages(valid_titles)
            if removed:
                logger.info(f"Cleaned up {removed} stale pages")

        # Filter standard pages by requested page titles
        if page_titles:
            page_titles_set = set(page_titles)
            filtered = [p for p in standard_pages if p.title in page_titles_set]
            logger.info(
                f"Filtered to {len(filtered)} standard pages matching requested titles "
                f"(out of {len(standard_pages)} total)"
            )
            standard_pages = filtered
            file_pairs = [(r, p) for r, p in file_pairs if p.title in page_titles_set]

        # Apply limit to standard pages
        if limit:
            standard_pages = standard_pages[:limit]
            logger.info(f"Limited to {len(standard_pages)} standard pages")

        # Write output_dir pages as plain .txt files (skip in dry-run)
        if file_pairs and not dry_run:
            self._write_file_pages(file_pairs)

        # Process and save standard pages through the preservation/normalization pipeline.
        # If there are no standard pages (e.g. zones-only run), return success directly
        # rather than letting _process_generated_pages emit a misleading warning.
        if not standard_pages:
            if preflight is not None:
                preflight(MappingProxyType({}))
            file_count = len(file_pairs)
            return OperationResult(
                total=file_count,
                succeeded=file_count,
                failed=0,
                skipped=0,
                warnings=[],
                errors=[],
            )
        return self._process_generated_pages(standard_pages, dry_run, preflight)

    def _write_file_pages(
        self,
        file_pairs: list[tuple[GeneratorRegistration, GeneratedPage]],
    ) -> None:
        """Write output_dir pages as plain .txt files.

        Generators with output_dir set handle their own field preservation and
        normalization before yielding. This method just routes their output to
        the configured directory, creating it if needed.

        The filename convention: replace spaces with underscores and append .txt.
        This matches MediaWiki's own URL-encoding convention.

        Args:
            file_pairs: (registration, page) pairs from output_dir generators.
        """
        for reg, page in file_pairs:
            assert reg.output_dir is not None  # invariant: callers only pass output_dir pairs
            output_dir = reg.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = page.title.replace(" ", "_") + ".txt"
            dest = output_dir / filename
            dest.write_text(normalise_generated_page_content(page.content), encoding="utf-8")
            logger.debug(f"Wrote {page.title!r} to {dest}")

        logger.info(f"Wrote {len(file_pairs)} pages to output directories")

    def _process_generated_pages(
        self,
        generated_pages: list[GeneratedPage],
        dry_run: bool,
        preflight: Callable[[Mapping[str, str]], None] | None = None,
    ) -> OperationResult:
        """Process generated pages with preservation and normalization.

        Args:
            generated_pages: List of GeneratedPage objects from generators.
            dry_run: If True, skip saving to storage.

        Returns:
            OperationResult with statistics and warnings/errors.
        """

        total = len(generated_pages)
        succeeded = 0
        failed = 0
        warnings: list[str] = []
        errors: list[str] = []
        processed_content: dict[str, str] = {}

        self._console.print(f"\n[bold]Generating {total} wiki pages...[/bold]\n")

        if not generated_pages:
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=["No pages to generate"],
                errors=[],
            )

        # Process each generated page with progress bar
        for gen_page in track(
            generated_pages,
            description="Processing pages",
            total=total,
        ):
            try:
                # Get generated content
                page_content = gen_page.content

                # Fetch existing content for preservation
                existing = self._storage.read_fetched_by_title(gen_page.title)

                # Apply preservation and legacy removal if page exists
                if existing:
                    # Check if this is an overview page (Weapons, Armor)
                    # These pages need special handling: preserve intro, replace table
                    if gen_page.title in ["Weapons", "Armor"]:
                        final_content = self._replace_overview_table(existing, page_content)
                        # Normalize page
                        final_content = self._page_normalizer.normalize(final_content, page_content)
                    else:
                        # Standard entity page processing
                        # Remove legacy templates FIRST
                        if self._legacy_remover.has_legacy_templates(existing):
                            migrated_content = self._legacy_remover.remove_legacy_templates(existing)
                            logger.debug(f"Legacy templates migrated: {gen_page.title}")
                        else:
                            migrated_content = existing

                        # Preserve manual edits
                        final_content = self._preservation_handler.merge_templates(
                            old_wikitext=migrated_content,
                            new_wikitext=page_content,
                            template_names=["Item", "Character", "Ability"],
                        )

                        # Ability tooltip companions are keyed, generated cards that
                        # belong to their top-level Ability/Stance root. Reconcile them
                        # before the item-specific migrations and final normalization.
                        final_content = self._replace_ability_tooltip_templates(
                            final_content,
                            page_content,
                        )

                        # Replace fancy tables (weapons, armor, charms)
                        final_content = self._replace_fancy_tables(final_content, page_content)

                        # Replace/insert item type templates (aura, spellscroll, skillbook, consumable, mold, general)
                        final_content = self._replace_item_type_templates(final_content, page_content)

                        # Normalize page
                        final_content = self._page_normalizer.normalize(final_content, page_content)
                else:
                    # New page, just normalize
                    final_content = self._page_normalizer.normalize(page_content)

                # Save to storage (skip in dry-run)
                if not dry_run:
                    self._storage.save_generated_by_title(
                        gen_page.title,
                        gen_page.stable_keys,
                        final_content,
                    )

                processed_content[gen_page.title] = final_content
                succeeded += 1

            except Exception as e:
                error_msg = f"Error generating page {gen_page.title}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        if preflight is not None and failed == 0:
            ordered_content = dict(sorted(processed_content.items(), key=lambda item: (item[0].casefold(), item[0])))
            preflight(MappingProxyType(ordered_content))

        # Display summary
        from erenshor.application.wiki.services.helpers import display_operation_summary

        display_operation_summary(
            console=self._console,
            operation="Generate",
            total=total,
            succeeded=succeeded,
            failed=failed,
            skipped=0,
            warnings=warnings,
            errors=errors,
            dry_run=dry_run,
        )

        return OperationResult(
            total=total,
            succeeded=succeeded,
            failed=failed,
            skipped=0,
            warnings=warnings,
            errors=errors,
        )

    def _replace_ability_tooltip_templates(self, old_wikitext: str, new_wikitext: str) -> str:
        """Reconcile generated ability tooltip companions by stable key.

        Ability and stance roots are preserved by ``merge_templates`` because
        their article prose is editor-owned. The keyed ``*Tooltip`` templates
        generated beside those roots are instead reconciled structurally. Only
        top-level templates participate. This keeps nested/manual templates and
        all unrelated bytes untouched.
        """
        from mwparserfromhell import parse
        from mwparserfromhell.nodes import Template, Text

        companion_to_root = {
            "SpellTooltip": ("Ability", "spell:"),
            "SkillTooltip": ("Ability", "skill:"),
            "StanceTooltip": ("Stance", "stance:"),
        }
        companion_names = frozenset(companion_to_root)
        root_names = frozenset(root for root, _ in companion_to_root.values())

        def template_name(node: object) -> str | None:
            if isinstance(node, Template):
                return str(node.name).strip()
            return None

        def direct_templates(code: object, names: frozenset[str]) -> list[Template]:
            return [
                node
                for node in code.nodes  # type: ignore[attr-defined]
                if isinstance(node, Template) and template_name(node) in names
            ]

        def previous_significant(nodes: Sequence[object], index: int) -> object | None:
            cursor = index - 1
            while cursor >= 0:
                node = nodes[cursor]
                if not (isinstance(node, Text) and not str(node).strip()):
                    return node
                cursor -= 1
            return None

        def parameter_value(template: Template, name: str) -> str | None:
            if not template.has(name):
                return None
            value = str(template.get(name).value).strip()
            return value or None

        def identity_index(nodes: Sequence[object], target: object) -> int:
            for index, node in enumerate(nodes):
                if node is target:
                    return index
            raise ValueError("Ability tooltip reconciliation lost a parsed node")

        def ordinal(nodes: Sequence[object], target: object, name: str) -> int:
            target_index = identity_index(nodes, target)
            return sum(1 for node in nodes[:target_index] if template_name(node) == name)

        new_code = parse(new_wikitext)
        new_nodes = list(new_code.nodes)
        new_companions = direct_templates(new_code, companion_names)

        # A generated page with no cards is intentionally a no-op. In particular,
        # do not erase an existing page when Lua data is temporarily unavailable.
        if not new_companions:
            return old_wikitext

        new_records: list[tuple[Template, Template, str, str, int]] = []
        new_keys: set[str] = set()
        for companion in new_companions:
            name = template_name(companion)
            assert name is not None
            root_name, prefix = companion_to_root[name]
            companion_index = identity_index(new_nodes, companion)
            preceding = previous_significant(new_nodes, companion_index)
            if not isinstance(preceding, Template) or template_name(preceding) != root_name:
                raise ValueError(f"{name} must immediately follow a top-level {root_name} root")

            key = parameter_value(companion, "stablekey")
            if key is None or not key.startswith(prefix) or len(key) == len(prefix):
                raise ValueError(f"{name} requires a stablekey with {prefix} prefix")
            if key in new_keys:
                raise ValueError(f"Duplicate generated ability tooltip key: {key}")
            new_keys.add(key)
            new_records.append(
                (
                    companion,
                    preceding,
                    name,
                    key,
                    ordinal(new_nodes, preceding, root_name),
                )
            )

        old_code = parse(old_wikitext)
        old_nodes = list(old_code.nodes)
        old_roots: dict[str, list[Template]] = {
            name: [node for node in old_nodes if isinstance(node, Template) and template_name(node) == name]
            for name in root_names
        }

        # A keyed Stance root identifies the already-converted thin/Cargo page.
        # Re-running the legacy generator against it is an invalid shape.
        for stance_root in old_roots["Stance"]:
            if isinstance(stance_root, Template) and parameter_value(stance_root, "stablekey"):
                raise ValueError("Keyed old Stance roots cannot be reconciled")

        old_companions = direct_templates(old_code, companion_names)
        old_records: list[tuple[Template, str | None, Template | None, int | None]] = []
        old_by_key: dict[str, tuple[Template, Template, int]] = {}
        for companion in old_companions:
            name = template_name(companion)
            assert name is not None
            key = parameter_value(companion, "stablekey")
            if key is None:
                old_records.append((companion, None, None, None))
                continue

            root_name, prefix = companion_to_root[name]
            # Invalid old invocations are stale compatibility markup. They are
            # removed rather than allowed to influence generated association.
            if not key.startswith(prefix) or len(key) == len(prefix):
                old_records.append((companion, key, None, None))
                continue

            companion_index = identity_index(old_nodes, companion)
            preceding = previous_significant(old_nodes, companion_index)
            if not isinstance(preceding, Template) or template_name(preceding) != root_name:
                raise ValueError(f"Nonadjacent generated {name} companion for key {key}")
            root = preceding
            root_ordinal = ordinal(old_nodes, root, root_name)
            if key in old_by_key:
                raise ValueError(f"Duplicate old ability tooltip key: {key}")
            old_by_key[key] = (companion, root, root_ordinal)
            old_records.append((companion, key, root, root_ordinal))

        # Resolve each generated companion against the old root ordinal. The
        # ordinal is intentionally independent of stable keys because legacy
        # roots are unkeyed and merge_templates preserves their order.
        resolved_new: list[tuple[Template, Template, str, str, int, Template]] = []
        for companion, _new_root, name, key, root_ordinal in new_records:
            root_name, _ = companion_to_root[name]
            roots = old_roots[root_name]
            if root_ordinal >= len(roots):
                raise ValueError(f"Missing old {root_name} root ordinal {root_ordinal} for {key}")
            resolved_new.append((companion, _new_root, name, key, root_ordinal, roots[root_ordinal]))

        # Remove stale/unkeyed companions first. Replacement keeps the old node
        # in place, while relocation removes it and is inserted below.
        insertions: list[tuple[Template, list[str]]] = []
        for companion, old_key, _old_root, _old_root_ordinal in old_records:
            if old_key is None or old_key not in new_keys:
                old_code.replace(companion, "")

        for _new_companion, _new_root, _name, key, _root_ordinal, old_root in resolved_new:
            old_match = old_by_key.get(key)
            if old_match is not None:
                old_companion, old_companion_root, _old_ordinal = old_match
                if old_companion_root is old_root:
                    # Raw replacement preserves the generated formatting from
                    # this run and all bytes around the old companion.
                    old_code.replace(old_companion, str(_new_companion))
                    continue
                old_code.replace(old_companion, "")

            for insertion_root, raw_list in insertions:
                if insertion_root is old_root:
                    raw_list.append(str(_new_companion))
                    break
            else:
                insertions.append((old_root, [str(_new_companion)]))

        # Insert from the end of each root's desired companion sequence so each
        # insertion remains directly after its root and preserves generated order.
        for root, raw_companions in insertions:
            for raw in reversed(raw_companions):
                current_index = identity_index(list(old_code.nodes), root)
                old_code.insert(current_index + 1, f"\n{raw}")

        return str(old_code)

    def _replace_overview_table(self, old_wikitext: str, new_wikitext: str) -> str:
        """Replace overview page wikitable while preserving intro text.

        Overview pages (Weapons, Armor) have:
        1. Manual intro paragraphs
        2. Large wikitable with game data

        We need to:
        - Preserve the manual intro text
        - Replace the entire wikitable with freshly generated content

        Args:
            old_wikitext: Existing page content (has manual intro + old table)
            new_wikitext: New generated content (has fresh table)

        Returns:
            Updated wikitext with preserved intro and new table
        """
        # Find where the wikitable starts in old content
        old_table_start = old_wikitext.find("{|")

        if old_table_start == -1:
            # No old table found, just return new content
            logger.debug("No wikitable found in old content, using new content")
            return new_wikitext

        # Extract intro text (everything before the table)
        intro_text = old_wikitext[:old_table_start].rstrip()

        # Find the wikitable in new content
        new_table_start = new_wikitext.find("{|")

        if new_table_start == -1:
            # No new table generated, keep old content
            logger.warning("No wikitable in new content, keeping old content")
            return old_wikitext

        # Extract new table (everything from {| onwards)
        new_table = new_wikitext[new_table_start:]

        # Combine: intro + new table
        result = f"{intro_text}\n\n{new_table}"

        logger.debug("Replaced overview wikitable while preserving intro text")
        return result

    def _replace_fancy_tables(self, old_wikitext: str, new_wikitext: str) -> str:
        """Replace item quality tables/templates with freshly generated versions.

        Weapons/Armor: legacy {| ... {{Item/Weapon}}/{{Item/Armor}} ... |} quality tables
        are replaced by one parameterized {{ItemTooltip}} call (the Lua module
        derives all eight qualities from Standard).
        Charms: {{Item/Charm\n...\n}}  (single template, charms don't upgrade)

        Old pages may still have {{Fancy-weapon}}, {{Fancy-armor}}, {{Fancy-charm}}
        which need to be replaced with the new {{Item/Weapon}}, {{Item/Armor}}, {{Item/Charm}}.

        These contain no manual content and should be completely replaced to ensure
        consistent formatting.  The replacement is deliberately idempotent: an
        existing parameterized ItemTooltip is replaced with the same generated raw
        template, while surrounding prose and categories remain untouched.

        Args:
            old_wikitext: Existing page content (may have old or new templates)
            new_wikitext: New generated content (has new Item/* templates)

        Returns:
            Updated wikitext with item quality templates replaced
        """
        from mwparserfromhell import parse

        # Parse old content only (we'll extract raw text from new_wikitext)
        old_code = parse(old_wikitext)

        # New template names (what we generate now)
        new_template_names = ["Item/Weapon", "Item/Armor", "Item/Charm"]
        # Legacy template names (what old pages may have)
        legacy_template_names = ["Fancy-weapon", "Fancy-armor", "Fancy-charm"]
        # All possible names to look for in old content
        all_template_names = new_template_names + legacy_template_names

        # Find Item/* templates in new content (to determine type)
        new_code = parse(new_wikitext)
        new_item_templates = [t for t in new_code.filter_templates() if str(t.name).strip() in new_template_names]

        if not new_item_templates:
            # No item quality templates in new content
            return old_wikitext

        # Determine if we're dealing with a table or standalone template
        # Tables contain Item/Weapon or Item/Armor quality templates.
        # Standalone is Item/Charm (single template, no table)
        has_weapon_or_armor = any(str(t.name).strip() in ["Item/Weapon", "Item/Armor"] for t in new_item_templates)

        if has_weapon_or_armor:
            # Find and replace the wiki table containing item quality templates
            return self._replace_wiki_table(old_code, new_wikitext, all_template_names)
        # Find and replace standalone charm template
        return self._replace_fancy_charm_template(old_code, new_wikitext)

    def _replace_wiki_table(
        self, old_code: mwparserfromhell.wikicode.Wikicode, new_wikitext: str, template_names: list[str]
    ) -> str:
        """Replace wiki table containing item quality templates.

        Args:
            old_code: Parsed old wikitext
            new_wikitext: Raw new wikitext (not parsed, preserves formatting)
            template_names: List of template names to look for (both new and legacy)

        Returns:
            Updated wikitext
        """
        from mwparserfromhell import parse

        # Parse new content to find the table node
        new_code = parse(new_wikitext)

        # Find the table in new content
        new_table_node = None
        for node in new_code.nodes:
            node_str = str(node)
            if node_str.startswith("{|") and any(name in node_str for name in template_names):
                new_table_node = node
                break

        if not new_table_node:
            return str(old_code)

        # The table in new_wikitext should be identical to what we just found
        # So we can use the original from new_wikitext which has correct formatting
        table_start = new_wikitext.find("{|")
        table_end = new_wikitext.find("|}", table_start) + 2
        new_table_raw = new_wikitext[table_start:table_end]

        # Find and replace the table in old content (check for both old and new template names)
        for node in old_code.nodes:
            node_str = str(node)
            if node_str.startswith("{|") and any(name in node_str for name in template_names):
                old_code.replace(node, new_table_raw)
                logger.debug("Replaced item quality table with raw text")
                return str(old_code)

        # No old table found, insert after {{Item}}
        item_template = self._find_item_template(old_code)
        if item_template:
            # Insert after {{Item}}
            item_index = old_code.index(item_template)
            old_code.insert(item_index + 1, f"\n\n{new_table_raw}")
            logger.debug("Inserted item quality table after {{Item}}")
            return str(old_code)

        # If no {{Item}} template found, append table at the end
        old_code.append(f"\n\n{new_table_raw}")
        logger.debug("Appended item quality table")
        return str(old_code)

    def _replace_fancy_charm_template(self, old_code: mwparserfromhell.wikicode.Wikicode, new_wikitext: str) -> str:
        """Replace standalone charm template (Item/Charm or legacy Fancy-charm).

        Args:
            old_code: Parsed old wikitext
            new_wikitext: Raw new wikitext (not parsed, preserves formatting)

        Returns:
            Updated wikitext
        """
        from mwparserfromhell import parse

        # New and legacy charm template names
        new_charm_name = "Item/Charm"
        legacy_charm_name = "Fancy-charm"

        # Parse new content to find Item/Charm template
        new_code = parse(new_wikitext)

        # Find Item/Charm in new content
        new_charm_node = None
        for node in new_code.filter_templates():
            if str(node.name).strip() == new_charm_name:
                new_charm_node = node
                break

        if not new_charm_node:
            return str(old_code)

        # Find the template in the original new_wikitext to preserve formatting
        # Look for {{Item/Charm at the start and }} at the end
        charm_start = new_wikitext.find("{{Item/Charm")
        if charm_start == -1:
            return str(old_code)

        # Find the matching closing braces
        # Count opening {{ and closing }} to handle nested templates
        brace_count = 0
        i = charm_start
        while i < len(new_wikitext):
            if new_wikitext[i : i + 2] == "{{":
                brace_count += 1
                i += 2
            elif new_wikitext[i : i + 2] == "}}":
                brace_count -= 1
                if brace_count == 0:
                    new_charm_raw = new_wikitext[charm_start : i + 2]
                    break
                i += 2
            else:
                i += 1
        else:
            # Couldn't find closing braces
            return str(old_code)

        # Find and replace in old content (check for both new and legacy charm)
        for node in old_code.filter_templates():
            template_name = str(node.name).strip()
            if template_name in [new_charm_name, legacy_charm_name]:
                old_code.replace(node, new_charm_raw)
                logger.debug(f"Replaced {{{{{template_name}}}}} template with {{{{Item/Charm}}}}")
                return str(old_code)

        # No old charm, insert after {{Item}}
        item_template = self._find_item_template(old_code)
        if item_template:
            item_index = old_code.index(item_template)
            old_code.insert(item_index + 1, f"\n\n{new_charm_raw}")
            logger.debug("Inserted {{Item/Charm}} after {{Item}}")
            return str(old_code)

        # If no {{Item}} template found, append charm template at the end
        old_code.append(f"\n\n{new_charm_raw}")
        logger.debug("Appended {{Item/Charm}}")
        return str(old_code)

    def _find_item_template(self, code: mwparserfromhell.wikicode.Wikicode) -> mwparserfromhell.nodes.Template | None:
        """Find {{Item}} template in parsed wikicode.

        Args:
            code: Parsed wikicode

        Returns:
            Item template node or None
        """
        for node in code.filter_templates():
            if str(node.name).strip() == "Item":
                return node
        return None

    def _replace_item_type_templates(self, old_wikitext: str, new_wikitext: str) -> str:
        """Replace or insert generated item tooltip templates.

        Current equipment pages generate a single parameterized {{ItemTooltip}}
        call carrying only Standard/base stats.  The Lua module derives all
        quality variants.  This also migrates legacy three-or-more-column
        weapon/armor tables and standalone subtype templates.
        """
        from mwparserfromhell import parse

        tooltip_templates = [
            "ItemTooltip",
            "Item/Aura",
            "Item/SpellScroll",
            "Item/SkillBook",
            "Item/Consumable",
            "Item/Mold",
            "Item/General",
            "Item/Charm",
            "Fancy-charm",
        ]
        legacy_table_templates = [
            "Item/Weapon",
            "Item/Armor",
            "Fancy-weapon",
            "Fancy-armor",
        ]

        new_code = parse(new_wikitext)
        new_tooltip_names = [
            str(template.name).strip()
            for template in new_code.filter_templates()
            if str(template.name).strip() in tooltip_templates
        ]

        if not new_tooltip_names:
            return old_wikitext

        name_occurrence_count: dict[str, int] = {}
        new_tooltip_raw_list: list[str] = []
        for tooltip_name in new_tooltip_names:
            occurrence_index = name_occurrence_count.get(tooltip_name, 0)
            raw = self._extract_nth_template_raw(new_wikitext, tooltip_name, occurrence_index)
            if raw:
                new_tooltip_raw_list.append(raw)
                name_occurrence_count[tooltip_name] = occurrence_index + 1

        if not new_tooltip_raw_list:
            return old_wikitext

        old_code = parse(old_wikitext)

        removed_table = False
        for node in list(old_code.nodes):
            node_str = str(node)
            if node_str.lstrip().startswith("{|") and any(name in node_str for name in legacy_table_templates):
                old_code.replace(node, "")
                removed_table = True
                logger.debug("Removed legacy item tooltip table")

        old_tooltip_templates: list[mwparserfromhell.nodes.Template] = []
        for template in old_code.filter_templates():
            name = str(template.name).strip()
            if name in tooltip_templates:
                old_tooltip_templates.append(template)

        if not old_tooltip_templates and len(new_tooltip_raw_list) > 1 and not removed_table:
            logger.debug(f"Multi-item legacy page with {len(new_tooltip_raw_list)} tooltips - using new structure")
            return new_wikitext

        extras_to_insert: list[str] = []
        for i, new_raw in enumerate(new_tooltip_raw_list):
            if i < len(old_tooltip_templates):
                old_template = old_tooltip_templates[i]
                old_name = str(old_template.name).strip()
                old_code.replace(old_template, new_raw)
                logger.debug(f"Replaced tooltip {i}: {{{{{old_name}}}}} with {{{{{new_tooltip_names[i]}}}}}")
            else:
                extras_to_insert.append(new_raw)
                logger.debug(f"Will insert tooltip {i}: {{{{{new_tooltip_names[i]}}}}}")

        for stale_template in old_tooltip_templates[len(new_tooltip_raw_list) :]:
            old_code.replace(stale_template, "")
            logger.debug(f"Removed stale tooltip {{{{{str(stale_template.name).strip()}}}}}")

        if extras_to_insert:
            item_template = self._find_item_template(old_code)
            insertion = "".join(f"\n\n{raw}" for raw in extras_to_insert)
            if item_template:
                old_code.insert(old_code.index(item_template) + 1, insertion)
                logger.debug("Inserted item tooltip after {{Item}}")
            else:
                old_code.append(insertion)
                logger.debug("Appended item tooltip")

        return str(old_code)

    def _extract_template_raw(self, wikitext: str, template_name: str) -> str | None:
        """Extract raw template text from wikitext preserving formatting.

        Args:
            wikitext: Raw wikitext
            template_name: Template name to find (e.g., "Item/Aura")

        Returns:
            Raw template text including {{ and }}, or None if not found
        """
        return self._extract_nth_template_raw(wikitext, template_name, 0)

    def _extract_nth_template_raw(self, wikitext: str, template_name: str, n: int = 0) -> str | None:
        """Extract the Nth occurrence of a template from wikitext.

        Args:
            wikitext: Raw wikitext
            template_name: Template name to find (e.g., "Item/General")
            n: 0-based index of which occurrence to extract

        Returns:
            Raw template text including {{ and }}, or None if not found
        """
        search_str = "{{" + template_name
        start = 0
        occurrences_found = 0

        while start < len(wikitext):
            pos = wikitext.find(search_str, start)
            if pos == -1:
                return None

            if occurrences_found == n:
                # Found the Nth occurrence, extract it
                return self._extract_template_at_position(wikitext, pos)

            # Skip past this occurrence and continue searching
            occurrences_found += 1
            start = pos + len(search_str)

        return None

    def _extract_template_at_position(self, wikitext: str, start: int) -> str:
        """Extract template starting at given position.

        Args:
            wikitext: Raw wikitext
            start: Position where template starts (at the first '{')

        Returns:
            Raw template text including {{ and }}
        """
        brace_count = 0
        i = start
        while i < len(wikitext):
            if wikitext[i : i + 2] == "{{":
                brace_count += 1
                i += 2
            elif wikitext[i : i + 2] == "}}":
                brace_count -= 1
                i += 2
                if brace_count == 0:
                    return wikitext[start:i]
            else:
                i += 1
        return wikitext[start:]  # Unclosed template, return rest
