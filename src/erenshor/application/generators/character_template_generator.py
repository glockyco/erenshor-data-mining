"""Character template generator for wiki content.

This module generates MediaWiki {{Character}} template wikitext for individual
characters including NPCs, enemies, vendors, and other in-game entities.

Template generators handle SINGLE entities only. Multi-entity page assembly
is handled by WikiService.

Template structure:
- {{Character}} template + category tags
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.generators.categories import CategoryGenerator
from erenshor.application.generators.formatting import safe_str
from erenshor.application.generators.template_generator_base import TemplateGeneratorBase
from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.registry.resolver import RegistryResolver

if TYPE_CHECKING:
    from erenshor.application.services.character_enricher import EnrichedCharacterData

WIKITEXT_LINE_SEPARATOR = "<br>"


class CharacterTemplateGenerator(TemplateGeneratorBase):
    """Generator for character wiki templates.

    Generates {{Character}} template wikitext for a SINGLE character entity
    with appropriate category tags.

    Multi-entity page assembly is handled by WikiService, not here.

    Example:
        >>> generator = CharacterTemplateGenerator()
        >>> enriched_data = enricher.enrich(character)
        >>> wikitext = generator.generate_template(enriched_data, "Goblin Scout", resolver)
    """

    def __init__(self) -> None:
        """Initialize generator."""
        super().__init__()
        self._category_generator = CategoryGenerator()

    def generate_template(
        self,
        enriched: "EnrichedCharacterData",
        page_title: str,
        resolver: RegistryResolver,
    ) -> str:
        """Generate template wikitext for a single character.

        Args:
            enriched: Enriched character data with spawn/loot/faction data
            page_title: Wiki page title
            resolver: Registry resolver for links and overrides

        Returns:
            Template wikitext for single character (infobox + categories)

        Example:
            >>> enriched = enricher.enrich(character)
            >>> wikitext = generator.generate_template(enriched, "Goblin Scout", resolver)
        """
        logger.debug(f"Generating template for character: {enriched.character.npc_name}")

        character = enriched.character

        # Resolve display name and image from registry
        display_name = resolver.resolve_display_name(character.stable_key, page_title)
        image_name = resolver.resolve_image_name(character.stable_key, page_title) or page_title

        # Format all fields
        enemy_type = self._format_enemy_type(character, enriched.spawn_infos)
        faction = self._format_faction(character, enriched.faction_display_names, resolver)
        faction_change = self._format_faction_modifiers(character, enriched.faction_display_names, page_title, resolver)
        zones = self._format_zones(enriched.spawn_infos, resolver)
        coordinates = self._format_coordinates(enriched.spawn_infos)
        spawn_chance = self._format_spawn_chance(enriched.spawn_infos, character)
        respawn = self._format_respawn(enriched.spawn_infos)
        guaranteed_drops, drop_rates = self._format_loot_drops(enriched.loot_drops, page_title, resolver)

        # Build template context
        context = self._build_character_template_context(
            character=character,
            display_name=display_name,
            image_name=image_name,
            enemy_type=enemy_type,
            faction=faction,
            faction_change=faction_change,
            zones=zones,
            coordinates=coordinates,
            spawn_chance=spawn_chance,
            respawn=respawn,
            guaranteed_drops=guaranteed_drops,
            drop_rates=drop_rates,
        )

        # Render template
        template_wikitext = self.render_template("character.jinja2", context)

        # Generate category tags
        categories = self._category_generator.generate_character_categories(enriched)
        category_wikitext = self._category_generator.format_category_tags(categories)

        # Combine template and categories
        page_content = template_wikitext
        if category_wikitext:
            page_content += "\n" + category_wikitext

        return self.normalize_wikitext(page_content)

    def _format_enemy_type(self, character: Character, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Classify character as Boss/Rare/Enemy/NPC for template display."""
        if character.is_friendly:
            return "[[:Category:Characters|NPC]]"
        if character.is_unique:
            return "[[Enemies|Boss]]"
        if spawn_infos:
            all_rare = all(info.is_rare for info in spawn_infos)
            all_unique = all(info.is_unique for info in spawn_infos)
            if all_unique:
                return "[[Enemies|Boss]]"
            if all_rare:
                return "[[Enemies|Rare]]"
        return "[[Enemies|Enemy]]"

    def _format_faction(
        self, character: Character, faction_display_names: dict[str, str], resolver: RegistryResolver
    ) -> str:
        """Format faction field using MyWorldFaction or MyFaction."""
        if character.my_world_faction:
            faction_desc = faction_display_names.get(character.my_world_faction, character.my_world_faction)
            return resolver.faction_link(character.my_world_faction, faction_desc)

        if character.my_faction in ("Villager", "GoodHuman", "GoodGuard", "OtherGood", "PreyAnimal"):
            faction_desc = faction_display_names.get("GOOD", "The Followers of Good")
            return resolver.faction_link("GOOD", faction_desc)

        if character.my_faction and character.my_faction not in ("Player", "PC", "DEBUG"):
            faction_desc = faction_display_names.get("EVIL", "The Followers of Evil")
            return resolver.faction_link("EVIL", faction_desc)

        return ""

    def _format_faction_modifiers(
        self,
        character: Character,
        faction_display_names: dict[str, str],
        character_name: str,
        resolver: RegistryResolver,
    ) -> str:
        """Format faction modifiers with display names."""
        if not character.faction_modifiers:
            return ""

        nonzero_mods = [m for m in character.faction_modifiers if m.modifier_value != 0]
        if not nonzero_mods:
            return ""

        entries: list[tuple[str, str]] = []
        for mod in nonzero_mods:
            display_name = faction_display_names.get(mod.faction_refname, mod.faction_refname)
            sign = "+" if mod.modifier_value > 0 else ""
            faction_link = resolver.faction_link(mod.faction_refname, display_name)
            formatted = f"{sign}{mod.modifier_value} {faction_link}"
            entries.append((display_name, formatted))

        entries.sort(key=lambda x: x[0])
        return WIKITEXT_LINE_SEPARATOR.join(line for _, line in entries)

    def _format_zones(self, spawn_infos: list[CharacterSpawnInfo], resolver: RegistryResolver) -> str:
        """Format zone list for wiki template."""
        if not spawn_infos:
            return ""

        zone_pairs = sorted({(info.scene, info.zone_display) for info in spawn_infos}, key=lambda x: x[1])
        zone_links = [resolver.zone_link(scene, zone_display) for scene, zone_display in zone_pairs]
        return WIKITEXT_LINE_SEPARATOR.join(zone_links)

    def _format_coordinates(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format coordinates for wiki template."""
        if len(spawn_infos) != 1:
            return ""

        spawn = spawn_infos[0]
        if spawn.x is None or spawn.y is None or spawn.z is None:
            return ""

        return f"{spawn.x:.1f} x {spawn.y:.1f} x {spawn.z:.1f}"

    def _format_spawn_chance(self, spawn_infos: list[CharacterSpawnInfo], character: Character) -> str:
        """Format spawn chance for wiki template."""
        if not spawn_infos:
            return ""

        is_common = bool(character.is_common)
        is_rare = bool(character.is_rare)
        is_unique = bool(character.is_unique)

        if is_common or not (is_rare or is_unique):
            return ""

        chances = [info.spawn_chance for info in spawn_infos]
        if all(c == 100.0 for c in chances):
            return ""

        unique_chances = sorted(set(chances), reverse=True)
        formatted_chances = [f"{int(chance)}%" for chance in unique_chances]
        return WIKITEXT_LINE_SEPARATOR.join(formatted_chances)

    def _format_respawn(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format respawn time for wiki template."""
        if not spawn_infos:
            return ""

        respawn_by_zone: dict[str, float] = {}
        for spawn in spawn_infos:
            zone_display = spawn.zone_display
            base_respawn = spawn.base_respawn or 0.0
            current_respawn = respawn_by_zone.get(zone_display)
            if current_respawn is None:
                respawn_by_zone[zone_display] = base_respawn
            else:
                respawn_by_zone[zone_display] = min(current_respawn, base_respawn)

        zones_sorted = sorted(respawn_by_zone.keys())
        respawn_strs = [(zone, self._seconds_to_duration(respawn_by_zone[zone])) for zone in zones_sorted]

        if len(respawn_strs) == 1:
            return respawn_strs[0][1]

        unique_times = {time_str for _, time_str in respawn_strs}
        if len(unique_times) == 1:
            return respawn_strs[0][1]

        formatted = [f"{time_str} ({zone})" for zone, time_str in respawn_strs]
        return WIKITEXT_LINE_SEPARATOR.join(formatted)

    def _seconds_to_duration(self, seconds: float) -> str:
        """Convert seconds to human-readable duration."""
        if seconds <= 0:
            return ""

        minutes = int(seconds // 60)
        secs = int(seconds % 60)

        if minutes > 0 and secs > 0:
            min_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
            sec_str = f"{secs} second{'s' if secs != 1 else ''}"
            return f"{min_str} {sec_str}"
        if minutes > 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        if secs > 0:
            return f"{secs} second{'s' if secs != 1 else ''}"

        return ""

    def _format_loot_drops(
        self,
        loot_drops: list[LootDropInfo],
        character_name: str,
        resolver: RegistryResolver,
    ) -> tuple[str, str]:
        """Format loot drops for wiki template."""
        if not loot_drops:
            return ("", "")

        guaranteed_entries: list[tuple[str, str]] = []
        all_entries: list[tuple[float, str]] = []

        for drop in loot_drops:
            if not drop.item_name:
                raise ValueError(
                    f"Invalid loot drop for {character_name}: missing item_name (resource_name={drop.resource_name})"
                )
            if not drop.resource_name:
                raise ValueError(
                    f"Invalid loot drop for {character_name}: missing resource_name (item_name={drop.item_name})"
                )
            if drop.drop_probability <= 0:
                continue  # Zero probability drops are valid (disabled drops)

            item_link = resolver.item_link(drop.resource_name, drop.item_name)
            stable_key = f"item:{drop.resource_name}"
            resolved_display_name = resolver.resolve_display_name(stable_key, drop.item_name)

            probability_text = f"{drop.drop_probability:.1f}%"
            entry_with_pct = f"{item_link} ({probability_text})"

            refs: list[str] = []
            if drop.is_visible:
                refs.append(f"<ref>If {character_name} has {item_link} equipped, it is guaranteed to drop.</ref>")
            if drop.item_unique:
                refs.append(
                    f"<ref>If the player is already holding {item_link} in their "
                    f"inventory, another will not drop.</ref>"
                )

            if refs:
                entry_with_pct += "".join(refs)

            sort_key = (-drop.drop_probability, resolved_display_name.lower())
            all_entries.append((sort_key[0], entry_with_pct))

            if drop.is_guaranteed:
                guaranteed_entries.append((resolved_display_name.lower(), item_link))

        def _join_entries(entries: Sequence[tuple[float | str, str]]) -> str:
            if not entries:
                return ""
            sorted_entries = sorted(entries)
            seen = set()
            output = []
            for _, entry_text in sorted_entries:
                if entry_text not in seen:
                    seen.add(entry_text)
                    output.append(entry_text)
            return WIKITEXT_LINE_SEPARATOR.join(output)

        guaranteed_str = ""
        if len(guaranteed_entries) >= 2:
            guaranteed_str = _join_entries(guaranteed_entries)

        return (guaranteed_str, _join_entries(all_entries))

    def _build_character_template_context(
        self,
        character: Character,
        display_name: str,
        image_name: str,
        enemy_type: str,
        faction: str,
        faction_change: str,
        zones: str,
        coordinates: str,
        spawn_chance: str,
        respawn: str,
        guaranteed_drops: str,
        drop_rates: str,
    ) -> dict[str, str]:
        """Build context for {{Character}} template."""
        xp_range = ""
        if character.base_xp_min and character.base_xp_max:
            multiplier = character.boss_xp_multiplier if character.boss_xp_multiplier else 1.0
            if multiplier == 0.0:
                multiplier = 1.0

            xp_min = int(character.base_xp_min * multiplier)
            xp_max = int(character.base_xp_max * multiplier)

            if xp_min == xp_max:
                xp_range = str(xp_min)
            else:
                xp_range = f"{xp_min}-{xp_max}"

        def _format_resistance(
            base_val: int | None, min_val: int | None, max_val: int | None, hand_set: int | None
        ) -> str:
            if hand_set:
                return safe_str(base_val)
            min_r = min_val or 0
            max_r = max_val or 0
            return f"{min_r}-{max_r}" if min_r != max_r else str(min_r)

        context: dict[str, str] = {
            "name": display_name,
            "image": f"{image_name}.png",
            "imagecaption": "",
            "type": enemy_type,
            "faction": faction,
            "faction_change": faction_change,
            "zones": zones,
            "coordinates": coordinates,
            "spawn_chance": spawn_chance,
            "respawn": respawn,
            "guaranteed_drops": guaranteed_drops,
            "drop_rates": drop_rates,
            "level": safe_str(character.level),
            "experience": xp_range,
            "health": safe_str(character.base_hp or character.effective_hp),
            "mana": safe_str(character.base_mana),
            "ac": safe_str(character.base_ac or character.effective_ac),
            "strength": safe_str(character.base_str),
            "endurance": safe_str(character.base_end),
            "dexterity": safe_str(character.base_dex),
            "agility": safe_str(character.base_agi),
            "intelligence": safe_str(character.base_int),
            "wisdom": safe_str(character.base_wis),
            "charisma": safe_str(character.base_cha),
            "magic": _format_resistance(
                character.base_mr,
                character.effective_min_mr,
                character.effective_max_mr,
                character.hand_set_resistances,
            ),
            "poison": _format_resistance(
                character.base_pr,
                character.effective_min_pr,
                character.effective_max_pr,
                character.hand_set_resistances,
            ),
            "elemental": _format_resistance(
                character.base_er,
                character.effective_min_er,
                character.effective_max_er,
                character.hand_set_resistances,
            ),
            "void": _format_resistance(
                character.base_vr,
                character.effective_min_vr,
                character.effective_max_vr,
                character.hand_set_resistances,
            ),
        }

        return context
