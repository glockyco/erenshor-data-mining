"""Fishing content generator.

Generates wiki content for fishing zones from the database, yielding the
Fishing page with all zone tables.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.engine import Engine

from erenshor.application.generators.base import GeneratedContent
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities.page import EntityRef
from erenshor.domain.value_objects.entity_type import EntityType
from erenshor.infrastructure.database.repositories import (
    get_water_fishables,
    get_waters,
)
from erenshor.infrastructure.templates.engine import render_template
from erenshor.registry.core import WikiRegistry
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.text import normalize_wikitext

__all__ = ["FishingGenerator"]


class FishingGenerator:
    """Generate fishing page content from database.

    Extracts all fishing data from Waters and WaterFishables tables,
    groups by zone, builds fishing tables, and yields a single GeneratedContent
    for the Fishing page.

    The generator is responsible for:
    1. Querying database for waters and fishables
    2. Grouping fishables by zone
    3. Building zone-specific fishing tables
    4. Rendering the canonical fishing template
    5. Resolving the "Fishing" page title via registry
    6. Yielding GeneratedContent with the complete fishing page body
    """

    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate fishing page content.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for link resolution and page title resolution
            filter: Not used for fishing (single-page generator)

        Yields:
            GeneratedContent for the Fishing page (single page)
        """
        link_resolver = RegistryLinkResolver(registry)

        waters = get_waters(engine)

        # Build fishables map by water ID
        from typing import Any

        fishables_by_water: dict[str, list[dict[str, Any]]] = {}
        for water in waters:
            water_id = str(water.get("WaterId"))
            fishables_by_water[water_id] = get_water_fishables(engine, water_id)

        # Group zones by display name
        from erenshor.shared.zones import get_zone_display_name

        by_zone: dict[str, list[dict[str, Any]]] = {}

        for water in waters:
            water_id = str(water.get("WaterId"))
            zone_name = get_zone_display_name(water.get("Scene") or "") or (
                water.get("ZoneName") or ""
            )
            fishable_rows = fishables_by_water.get(water_id) or []

            for fishable in fishable_rows:
                item_name = fishable.get("ItemName") or ""
                if not item_name:
                    continue

                # Format rate
                try:
                    drop_rate = float(fishable.get("DropChance") or 0)
                    rate_str = f"{drop_rate:.2f}%"
                except (TypeError, ValueError) as e:
                    raise ValueError(
                        f"Invalid drop chance for fishable item '{item_name}' in zone '{zone_name}': "
                        f"{fishable.get('DropChance')!r}"
                    ) from e

                by_zone.setdefault(zone_name, []).append(
                    {
                        "name": link_resolver.item_link(
                            fishable.get("ResourceName") or "", item_name
                        ),
                        "rate": rate_str,
                    }
                )

        zones_sorted = sorted(zone_key for zone_key in by_zone.keys() if zone_key)
        model = {
            "zones": [
                {"name": zone, "rows": by_zone.get(zone, [])} for zone in zones_sorted
            ],
        }

        rendered = normalize_wikitext(render_template("fishing/canonical.j2", model))

        # Register Fishing as an overview page
        title = "Fishing"
        entity_ref = EntityRef(
            entity_type=EntityType.OVERVIEW,
            db_id=None,
            db_name="Fishing",
            resource_name="fishing_overview",
        )

        page = registry.resolve_entity(entity_ref)
        if not page:
            page = registry.register_entity(entity_ref, title)

        blocks = [
            RenderedBlock(
                page_title=title,
                block_id="fishing_canonical",
                template_key="Fishing_canonical",
                text=rendered,
            )
        ]

        yield GeneratedContent(
            entity_ref=entity_ref,
            page_title=title,
            rendered_blocks=blocks,
        )
