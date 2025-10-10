"""Character content generator.

Generates wiki content for all characters/enemies from the database, yielding
one character at a time for streaming and progress tracking.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.engine import Engine

from erenshor.application.generators.base import BaseGenerator, GeneratedContent
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities.character import DbCharacter
from erenshor.domain.entities.page import EntityRef
from erenshor.domain.services.drop_calculator import format_drops
from erenshor.infrastructure.database.repositories import (
    get_characters,
    get_faction_desc_by_ref,
    get_factions_map,
    get_loot_for_character,
    get_spawnpoints_for_character,
)
from erenshor.infrastructure.templates.contexts import EnemyInfoboxContext
from erenshor.infrastructure.templates.engine import render_template
from erenshor.registry.core import WikiRegistry
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR
from erenshor.shared.text import normalize_wikitext, seconds_to_duration
from erenshor.shared.zones import get_zone_display_name

__all__ = ["CharacterGenerator"]


class CharacterGenerator(BaseGenerator):
    """Generate character/enemy page content from database.

    Extracts all character/enemy data from database, builds template contexts,
    renders Jinja2 templates, and yields GeneratedContent one character at a time.

    This generator handles all character types:
    - NPCs (friendly characters)
    - Enemies (hostile characters)
    - Bosses (unique enemies)
    - Rare enemies

    All characters use the Enemy template regardless of friendly/hostile status
    per CLAUDE.md conventions.

    The generator is responsible for:
    1. Querying database for characters and related data (spawn points, loot, factions)
    2. Building template contexts (EnemyInfoboxContext)
    3. Rendering templates via render_template
    4. Resolving page titles via registry
    5. Yielding GeneratedContent with rendered blocks
    """

    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate character content with streaming.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for link resolution and page title resolution
            filter: Optional filter string (name or 'id:guid') to process specific characters

        Yields:
            GeneratedContent for each character, one at a time
        """
        link_resolver = RegistryLinkResolver(registry)
        # Map faction REFNAME to display descriptions (for FactionModifiers)
        faction_desc_by_ref = get_faction_desc_by_ref(engine)
        # Map faction names to display descriptions (for MyWorldFaction)
        factions_map = get_factions_map(engine)

        chars = get_characters(engine)
        # Filter out SimPlayers per CLAUDE.md
        chars = [
            char
            for char in chars
            if not char.IsSimPlayer and getattr(char, "HasStats", True)
        ]

        # Apply filter if provided
        if filter:
            chars = [
                char
                for char in chars
                if self._matches_filter(char.NPCName or "", char.Guid or "", filter)
            ]

        # Group characters by page title to detect multi-entity pages
        by_title: dict[str, list[DbCharacter]] = {}
        for char in chars:
            # Construct stable ID for character
            stable_id = (
                char.ObjectName
                if (char.IsPrefab and char.ObjectName)
                else f"{char.ObjectName}|{char.Scene or 'Unknown'}|{char.X or 0:.2f}|{char.Y or 0:.2f}|{char.Z or 0:.2f}"
            )
            page_title = link_resolver.resolve_character_title(
                stable_id, char.NPCName or stable_id
            )
            by_title.setdefault(page_title, []).append(char)

        for char in chars:
            # Construct stable ID for character
            stable_id = (
                char.ObjectName
                if (char.IsPrefab and char.ObjectName)
                else f"{char.ObjectName}|{char.Scene or 'Unknown'}|{char.X or 0:.2f}|{char.Y or 0:.2f}|{char.Z or 0:.2f}"
            )

            # Check if entity is in registry (skip if explicitly excluded)
            entity_ref = EntityRef.from_character(char)
            # Only skip if registry has pages (i.e., has been built)
            # Empty registry means first run or test - don't skip
            if registry.pages and not registry.resolve_entity(entity_ref):
                # Entity excluded from registry - skip generation
                continue

            page_title = link_resolver.resolve_character_title(
                stable_id, char.NPCName or stable_id
            )

            # Skip multi-entity pages per CLAUDE.md policy
            # Multiple DB entities mapping to same page title are skipped
            # Service layer tracks skipped entities via update events
            if len(by_title.get(page_title, [])) > 1:
                continue

            # Fetch spawn points once for all subsequent logic
            spawnpoint_rows = (
                get_spawnpoints_for_character(engine, char.Guid) if char.Guid else []
            )

            # Determine character type
            enemy_type = ""
            if char.IsFriendly:
                enemy_type = "[[:Category:Characters|NPC]]"
            else:
                if char.IsUnique:
                    enemy_type = "[[Enemies|Boss]]"
                elif spawnpoint_rows:
                    all_rare = all(bool(row.get("IsRare")) for row in spawnpoint_rows)
                    all_unique = all(
                        bool(row.get("IsUnique")) for row in spawnpoint_rows
                    )
                    if all_unique:
                        enemy_type = "[[Enemies|Boss]]"
                    elif all_rare:
                        enemy_type = "[[Enemies|Rare]]"
                    else:
                        enemy_type = "[[Enemies|Enemy]]"
                else:
                    enemy_type = "[[Enemies|Enemy]]"

            # Coordinates
            coordinates = ""
            if char.IsUnique:
                if char.X is not None and char.Y is not None and char.Z is not None:
                    # Use direct coordinates from character record
                    coordinates = f"{char.X:.1f} x {char.Y:.1f} x {char.Z:.1f}"
                elif spawnpoint_rows and len(spawnpoint_rows) > 0:
                    # Use coordinates from first spawn point
                    first_spawn = spawnpoint_rows[0]
                    if (
                        first_spawn.get("X") is not None
                        and first_spawn.get("Y") is not None
                        and first_spawn.get("Z") is not None
                    ):
                        coordinates = f"{first_spawn['X']:.1f} x {first_spawn['Y']:.1f} x {first_spawn['Z']:.1f}"

            # Experience
            experience = ""
            if char.BaseXpMin and char.BaseXpMax:
                multiplier = char.BossXpMultiplier if char.BossXpMultiplier else 1.0
                if multiplier == 0.0:
                    multiplier = 1.0

                xp_min = int(char.BaseXpMin * multiplier)
                xp_max = int(char.BaseXpMax * multiplier)

                experience = f"{xp_min}-{xp_max}" if xp_min != xp_max else f"{xp_min}"

            # Spawn information
            respawn_str = ""
            spawn_chance_str = ""
            if spawnpoint_rows:
                zones_set: set[str] = set()
                respawn_by_zone: dict[str, float] = {}
                chances_by_zone: dict[str, list[float]] = {}
                for row in spawnpoint_rows:
                    scene = row.get("Scene") or ""
                    zone_display = get_zone_display_name(scene)
                    zones_set.add(zone_display)
                    base_respawn = float(row.get("BaseRespawn") or 0) or 600.0
                    current_respawn = respawn_by_zone.get(zone_display)
                    respawn_by_zone[zone_display] = (
                        min(current_respawn, base_respawn)
                        if current_respawn
                        else base_respawn
                    )
                    chances_by_zone.setdefault(zone_display, []).append(
                        float(row.get("SpawnChance") or 0)
                    )
                zones_sorted = sorted(zones_set)
                respawn_pairs = [
                    (zone, seconds_to_duration(respawn_by_zone.get(zone, 0)))
                    for zone in zones_sorted
                ]
                respawn_str = (
                    "".join([pair[1] for pair in respawn_pairs])
                    if len(zones_sorted) == 1
                    else WIKITEXT_LINE_SEPARATOR.join(
                        [
                            f"{pair[1]} ({zone})"
                            for zone, pair in zip(zones_sorted, respawn_pairs)
                        ]
                    )
                )

                # Spawn chance only for hostile Boss/Rare per CLAUDE.md
                if not char.IsFriendly and enemy_type in (
                    "[[Enemies|Boss]]",
                    "[[Enemies|Rare]]",
                ):
                    chance_strs: list[str] = []
                    for zone in zones_sorted:
                        chances = [
                            chance
                            for chance in chances_by_zone.get(zone, [])
                            if chance > 0
                        ]
                        if not chances:
                            continue
                        min_chance = min(chances)
                        max_chance = max(chances)
                        display = (
                            f"{min_chance:.0f}%"
                            if min_chance == max_chance
                            else f"{min_chance:.0f}-{max_chance:.0f}%"
                        )
                        chance_strs.append(
                            display if len(zones_sorted) == 1 else f"{display} ({zone})"
                        )
                    spawn_chance_str = WIKITEXT_LINE_SEPARATOR.join(chance_strs)

            # Loot/drops
            loot = get_loot_for_character(engine, char.Guid) if char.Guid else []
            guaranteed_drops_str, regular_drops_str = format_drops(
                loot,
                link_resolver,
                append_visible_ref=True,
                character_name=page_title,
            )

            # Faction change
            faction_change = ""
            if char.FactionModifiers:
                # Build list with display names for sorting
                faction_entries: list[tuple[str, int, str]] = []
                for mod in char.FactionModifiers:
                    sign = "+" if mod.modifier_value > 0 else ""
                    description = faction_desc_by_ref.get(mod.faction_name, mod.faction_name)
                    faction_entries.append((description, mod.modifier_value, sign))

                # Sort by display name
                faction_entries.sort(key=lambda x: x[0])

                # Format sorted entries
                formatted = [f"{sign}{value} [[{desc}]]" for desc, value, sign in faction_entries]
                faction_change = WIKITEXT_LINE_SEPARATOR.join(formatted)

            faction_display = ""
            if char.MyWorldFaction:
                # Use explicit world faction if set, wiki-link it since faction pages exist
                # MyWorldFaction contains FactionName values, not REFNAME
                faction_name = factions_map.get(
                    char.MyWorldFaction, char.MyWorldFaction
                )
                faction_display = f"[[{faction_name}]]" if faction_name else ""
            elif char.MyFaction in (
                # Per the game logic, MyFaction values are auto-mapped to world factions:
                # - Villager, GoodHuman, GoodGuard, OtherGood, PreyAnimal -> "Generic Good"
                # - All others (EvilHuman, OtherEvil, etc.) -> "Generic Evil"
                "Villager",
                "GoodHuman",
                "GoodGuard",
                "OtherGood",
                "PreyAnimal",
            ):
                # Good-aligned factions map to "Generic Good" faction page
                faction_name = factions_map.get("Generic Good", "The Followers of Good")
                faction_display = f"[[{faction_name}]]"
            elif char.MyFaction and char.MyFaction not in ("Player", "PC", "DEBUG"):
                # Evil-aligned factions map to "Generic Evil" faction page
                faction_name = factions_map.get("Generic Evil", "The Followers of Evil")
                faction_display = f"[[{faction_name}]]"

            entity_ref = EntityRef.from_character(char)
            display_name = registry.get_display_name(entity_ref)
            image_name = registry.get_image_name(entity_ref)
            context = EnemyInfoboxContext(
                block_id=stable_id,
                name=display_name,
                image=f"{image_name}.png",
                type=enemy_type,
                faction=faction_display,
                factionChange=faction_change,
                zones=(
                    WIKITEXT_LINE_SEPARATOR.join(
                        sorted(
                            {
                                f"[[{get_zone_display_name(row.get('Scene') or '')}]]"
                                for row in spawnpoint_rows
                            }
                        )
                    )
                    if spawnpoint_rows
                    else (
                        f"[[{get_zone_display_name(char.ZoneName or char.Scene or '')}]]"
                        if char.ZoneName or char.Scene
                        else ""
                    )
                ),
                coordinates=coordinates,
                spawnchance=spawn_chance_str,
                respawn=respawn_str,
                guaranteeddrops=guaranteed_drops_str,
                droprates=regular_drops_str,
                level=str(char.Level) if char.Level is not None else "",
                experience=experience,
                health=str(char.BaseHP) if char.BaseHP is not None else "",
                mana=str(char.BaseMana) if char.BaseMana is not None else "",
                ac=str(char.BaseAC) if char.BaseAC is not None else "",
                strength=str(char.BaseStr) if char.BaseStr is not None else "",
                endurance=str(char.BaseEnd) if char.BaseEnd is not None else "",
                dexterity=str(char.BaseDex) if char.BaseDex is not None else "",
                agility=str(char.BaseAgi) if char.BaseAgi is not None else "",
                intelligence=str(char.BaseInt) if char.BaseInt is not None else "",
                wisdom=str(char.BaseWis) if char.BaseWis is not None else "",
                charisma=str(char.BaseCha) if char.BaseCha is not None else "",
                magic=(
                    f"{char.EffectiveMinMR}-{char.EffectiveMaxMR}"
                    if (
                        char.EffectiveMinMR
                        and char.EffectiveMaxMR
                        and char.EffectiveMinMR != char.EffectiveMaxMR
                    )
                    else str(char.EffectiveMaxMR or char.EffectiveMinMR or "")
                ),
                elemental=(
                    f"{char.EffectiveMinER}-{char.EffectiveMaxER}"
                    if (
                        char.EffectiveMinER
                        and char.EffectiveMaxER
                        and char.EffectiveMinER != char.EffectiveMaxER
                    )
                    else str(char.EffectiveMaxER or char.EffectiveMinER or "")
                ),
                poison=(
                    f"{char.EffectiveMinPR}-{char.EffectiveMaxPR}"
                    if (
                        char.EffectiveMinPR
                        and char.EffectiveMaxPR
                        and char.EffectiveMinPR != char.EffectiveMaxPR
                    )
                    else str(char.EffectiveMaxPR or char.EffectiveMinPR or "")
                ),
                void=(
                    f"{char.EffectiveMinVR}-{char.EffectiveMaxVR}"
                    if (
                        char.EffectiveMinVR
                        and char.EffectiveMaxVR
                        and char.EffectiveMinVR != char.EffectiveMaxVR
                    )
                    else str(char.EffectiveMaxVR or char.EffectiveMinVR or "")
                ),
            )

            # Render enemy template
            rendered = normalize_wikitext(
                render_template("characters/enemy.j2", context)
            )
            blocks = [
                RenderedBlock(
                    page_title=page_title,
                    block_id=stable_id,
                    template_key="Infobox_enemy",
                    text=rendered,
                )
            ]

            entity_ref = EntityRef.from_character(char)

            yield GeneratedContent(
                entity_ref=entity_ref,
                page_title=page_title,
                rendered_blocks=blocks,
            )
