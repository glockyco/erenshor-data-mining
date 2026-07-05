"""Zone page generator.

Generates individual wiki pages for each zone (grouped by wiki_page_name so
Mysterious Portal's three instances produce a single page).

Pages are written to wiki/zones/ (set via GeneratorRegistration.output_dir)
rather than the standard WikiStorage. The generator handles its own field
preservation so manually-edited fields (level, image, prose, tables) survive
regeneration.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.base import GeneratedPage, PageGenerator, PageMetadata
from erenshor.application.wiki.generators.field_preservation import FieldPreservationHandler

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.context import GeneratorContext
    from erenshor.domain.entities.zone import Zone

# Path to zone-positions.json is version-controlled and stable.
_ZONE_POSITIONS_PATH = Path("src/maps/src/lib/data/zone-positions.json")

# Default output directory; the registry overrides via the output_dir param.
# Kept as a module constant so the generator and registry share one source of
# truth for the path and tests can inject a tmp_path.
_DEFAULT_OUTPUT_DIR = Path("wiki/zones")


class ZonePageGenerator(PageGenerator):
    """Generates individual wiki pages for all zones.

    Groups zones by wiki_page_name so Mysterious Portal's three distinct scene
    names sharing one page produces a single output file.

    Field preservation reads the existing on-disk output file (the authoritative
    source of hand-curated content) and falls back to fetched wiki storage when
    no output file exists yet (e.g. first generation of a new zone). Reading
    from fetched storage alone was insufficient: fetched pages are only present
    after ``wiki fetch``, so a generate-without-fetch run would clobber curated
    content with bare template stubs.

    Output: ``{output_dir}/{Title_With_Spaces_As_Underscores}.txt``
    """

    def __init__(self, context: GeneratorContext, output_dir: Path = _DEFAULT_OUTPUT_DIR) -> None:
        super().__init__(context)
        self._preservation_handler = FieldPreservationHandler()
        self._output_dir = output_dir

        # Load valid map keys from the version-controlled zone-positions.json.
        # Zones whose scene_name is NOT in this set have no interactive map.
        try:
            self._map_keys: set[str] = set(json.loads(_ZONE_POSITIONS_PATH.read_text(encoding="utf-8")).keys())
        except FileNotFoundError:
            logger.warning(f"zone-positions.json not found at {_ZONE_POSITIONS_PATH}; no map links will be generated")
            self._map_keys = set()

    def get_pages_to_fetch(self) -> list[str]:
        """Return unique wiki page names for all zones (for field preservation fetch)."""
        return list({z.wiki_page_name for z in self.context.zone_repo.get_all_zones() if z.wiki_page_name})

    def generate_pages(self) -> Iterator[GeneratedPage]:
        """Yield one GeneratedPage per unique wiki_page_name."""
        # Group zones by wiki_page_name.
        # Zones without wiki_page_name are excluded from the wiki entirely.
        groups: dict[str, list[Zone]] = {}
        for zone in self.context.zone_repo.get_all_zones():
            if zone.wiki_page_name:
                groups.setdefault(zone.wiki_page_name, []).append(zone)

        logger.info(f"ZonePageGenerator: generating {len(groups)} zone pages")

        for wiki_name, zone_group in groups.items():
            # Collect connections from all zones in the group, excluding self-references.
            # (Mysterious Portal 1/2/3 each have their own zone_lines entries.)
            connections: list[str] = sorted(
                {
                    conn
                    for zone in zone_group
                    if zone.scene_name
                    for conn in self.context.zone_repo.get_zone_connections(zone.scene_name)
                    if conn != wiki_name
                }
            )

            # Use the first zone in the group whose scene_name is a valid map key.
            map_scene: str | None = next(
                (z.scene_name for z in zone_group if z.scene_name in self._map_keys),
                None,
            )

            content = self._render_template(
                "zone.jinja2",
                {
                    "wiki_name": wiki_name,
                    "zone_group": zone_group,
                    "connections": connections,
                    "map_scene": map_scene,
                },
            )

            # Apply field preservation from the existing on-disk output file
            # (the authoritative source of hand-curated content), falling back
            # to fetched wiki storage when no output file exists yet (e.g.
            # first generation of a new zone, or after a clean checkout).
            # Reading from fetched storage alone was a bug: fetched pages are
            # only present after `wiki fetch`, so a generate-without-fetch run
            # would clobber curated content with bare template stubs.
            on_disk_path = self._output_dir / f"{wiki_name.replace(' ', '_')}.txt"
            existing = on_disk_path.read_text(encoding="utf-8") if on_disk_path.exists() else None
            if existing is None:
                existing = self.context.storage.read_fetched_by_title(wiki_name)
            if existing:
                # Redirect pages have no template to merge against.
                if existing.strip().startswith("#REDIRECT"):
                    logger.debug(f"Skipping field preservation for redirect page: {wiki_name!r}")
                else:
                    # Normalise {{Dungeon|...}} → {{Zone|...}} so dungeon pages are
                    # migrated to the unified template. Field names overlap in both.
                    normalized = existing.replace("{{Dungeon", "{{Zone")
                    # Strip wikilinks from |type= (e.g. [[Zones#Dungeons|Dungeon]] → Dungeon)
                    # so prefer_manual retains the classification in plain-text form,
                    # which Template:Zone's #ifeq requires for category injection.
                    normalized = re.sub(
                        r"(\|type=)\[\[[^\]]*\|([^\]]+)\]\]",
                        r"\1\2",
                        normalized,
                    )
                    content = self._preservation_handler.merge_templates(
                        old_wikitext=normalized,
                        new_wikitext=content,
                        template_names=["Zone"],
                    )

            logger.debug(f"Generated zone page: {wiki_name!r} (connections: {len(connections)}, map: {map_scene!r})")

            yield GeneratedPage(
                title=wiki_name,
                content=content,
                metadata=PageMetadata(summary="Update zone data from game export"),
                stable_keys=[z.stable_key for z in zone_group],
            )
