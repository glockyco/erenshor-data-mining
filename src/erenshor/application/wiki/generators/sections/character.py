"""Character section generator for wiki content.

This module generates MediaWiki {{Character}} template wikitext for individual
characters including NPCs, enemies, vendors, and other in-game entities.

This section generator produces templates for single characters. Multi-entity page
assembly is handled by PageGenerator classes.

Template structure:
- {{Character}} template + category tags
"""

from collections.abc import Sequence

from loguru import logger

from erenshor.application.wiki.generators.formatting import safe_str
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase
from erenshor.domain.enriched_data.character import EnrichedCharacterData
from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.registry.resolver import RegistryResolver

WIKITEXT_LINE_SEPARATOR = "<br>"


class CharacterSectionGenerator(SectionGeneratorBase):
    """Generator for character wiki sections.

    Generates {{Character}} template wikitext for a SINGLE character entity
    with appropriate category tags.

    Multi-entity page assembly is handled by PageGenerator classes, not here.

    Example:
        >>> resolver = RegistryResolver(...)
        >>> category_generator = CategoryGenerator(resolver)
        >>> generator = CharacterSectionGenerator(resolver, category_generator)
        >>> enriched_data = enricher.enrich(character)
        >>> wikitext = generator.generate_template(enriched_data, "Goblin Scout")
    """

    def __init__(self, resolver: RegistryResolver) -> None:
        """Initialize character section generator.

        Args:
            resolver: Registry resolver for links and display names
        """
        super().__init__()
        self._resolver = resolver

    def generate_template(
        self,
        enriched: EnrichedCharacterData,
        page_title: str,
    ) -> str:
        """Generate template wikitext for a single character.

        Args:
            enriched: Enriched character data with spawn/loot/faction data
            page_title: Wiki page title

        Returns:
            Template wikitext for single character (infobox + categories)

        Example:
            >>> enriched = enricher.enrich(character)
            >>> wikitext = generator.generate_template(enriched, "Goblin Scout")
        """
        logger.debug(f"Generating template for character: {enriched.character.npc_name}")

        character = enriched.character

        # Resolve display name and image from registry
        display_name = self._resolver.resolve_display_name(character.stable_key)
        image_name = self._resolver.resolve_image_name(character.stable_key)

        # Format all fields
        enemy_type = self._format_enemy_type(character, enriched.spawn_infos)
        faction = self._format_faction(character)
        faction_change = self._format_faction_modifiers(character)
        zones = self._format_zones(enriched.spawn_infos)
        coordinates = self._format_coordinates(enriched.spawn_infos)
        spawn_chance = self._format_spawn_chance(enriched.spawn_infos, character)
        respawn = self._format_respawn(enriched.spawn_infos)
        guaranteed_drops, drop_rates = self._format_loot_drops(enriched.loot_drops, display_name)
        spells = self._format_ability_links(enriched.spells)

        # Build template context
        context = self._build_character_template_context(
            character=character,
            display_name=display_name,
            image_name=image_name or "",
            enemy_type=enemy_type,
            faction=faction,
            faction_change=faction_change,
            zones=zones,
            coordinates=coordinates,
            spawn_chance=spawn_chance,
            respawn=respawn,
            guaranteed_drops=guaranteed_drops,
            drop_rates=drop_rates,
            spells=spells,
        )

        template_wikitext = self.render_template("character.jinja2", context)
        return self.normalize_wikitext(template_wikitext)

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

    def _format_faction(self, character: Character) -> str:
        """Format faction field using MyWorldFactionStableKey or MyFaction."""
        if character.my_world_faction_stable_key:
            return str(self._resolver.faction_link(character.my_world_faction_stable_key))

        if character.my_faction in ("Villager", "GoodHuman", "GoodGuard", "OtherGood", "PreyAnimal"):
            return str(self._resolver.faction_link("faction:good"))

        if character.my_faction and character.my_faction not in ("Player", "PC", "DEBUG"):
            return str(self._resolver.faction_link("faction:evil"))

        return ""

    def _format_faction_modifiers(self, character: Character) -> str:
        """Format faction modifiers with display names."""
        if not character.faction_modifiers:
            return ""

        nonzero_mods = [m for m in character.faction_modifiers if m.modifier_value != 0]
        if not nonzero_mods:
            return ""

        entries: list[tuple[str, str]] = []
        for mod in nonzero_mods:
            display_name = self._resolver.resolve_display_name(mod.faction_stable_key)
            sign = "+" if mod.modifier_value > 0 else ""
            faction_link = self._resolver.faction_link(mod.faction_stable_key)
            formatted = f"{sign}{mod.modifier_value} {faction_link}"
            entries.append((display_name, formatted))

        entries.sort(key=lambda x: x[0])
        return WIKITEXT_LINE_SEPARATOR.join(line for _, line in entries)

    def _format_zones(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format zone list for wiki template."""
        if not spawn_infos:
            return ""

        # Get unique zone stable keys
        zone_stable_keys = {info.zone_stable_key for info in spawn_infos}

        # Build (display_name, link) tuples and sort by display name
        zone_data = []
        for stable_key in zone_stable_keys:
            display_name = self._resolver.resolve_display_name(stable_key)
            link = self._resolver.zone_link(stable_key)
            zone_data.append((display_name, link))

        zone_data.sort(key=lambda x: x[0].lower())
        return WIKITEXT_LINE_SEPARATOR.join(str(link) for _, link in zone_data)

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

        # Group spawn chances by zone
        chances_by_zone: dict[str, list[float]] = {}
        for info in spawn_infos:
            zone_display = self._resolver.resolve_display_name(info.zone_stable_key)
            chances_by_zone.setdefault(zone_display, []).append(info.spawn_chance)

        # Get unique zones sorted alphabetically
        zones_sorted = sorted(chances_by_zone.keys())

        # Format spawn chances with zone names if multiple zones
        formatted_chances: list[str] = []
        for zone in zones_sorted:
            zone_chances = chances_by_zone[zone]
            min_chance = min(zone_chances)
            max_chance = max(zone_chances)

            if min_chance == max_chance:
                display = f"{round(min_chance)}%"
            else:
                display = f"{round(min_chance)}-{round(max_chance)}%"

            # Include zone name only if character spawns in multiple zones
            if len(zones_sorted) > 1:
                formatted_chances.append(f"{display} ({zone})")
            else:
                formatted_chances.append(display)

        return WIKITEXT_LINE_SEPARATOR.join(formatted_chances)

    def _format_respawn(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format respawn time for wiki template.

        Rounds to nearest minute for readability. Shows ranges if respawn times
        differ within a zone.
        """
        if not spawn_infos:
            return ""

        # Group respawn times by zone and round to nearest minute
        respawns_by_zone: dict[str, list[int]] = {}
        for spawn in spawn_infos:
            zone_display = self._resolver.resolve_display_name(spawn.zone_stable_key)
            base_respawn = spawn.base_respawn or 0.0
            # Round to nearest minute
            minutes = round(base_respawn / 60.0)
            respawns_by_zone.setdefault(zone_display, []).append(minutes)

        zones_sorted = sorted(respawns_by_zone.keys())

        # Format respawn times with ranges if they differ within a zone
        respawn_strs: list[tuple[str, str]] = []
        for zone in zones_sorted:
            zone_minutes = respawns_by_zone[zone]
            min_minutes = min(zone_minutes)
            max_minutes = max(zone_minutes)

            if min_minutes == max_minutes:
                time_str = self._minutes_to_duration(min_minutes)
            else:
                time_str = f"{min_minutes}-{max_minutes} minutes"

            respawn_strs.append((zone, time_str))

        # Single zone - no zone name needed
        if len(respawn_strs) == 1:
            return respawn_strs[0][1]

        # All zones have same time - no zone names needed
        unique_times = {time_str for _, time_str in respawn_strs}
        if len(unique_times) == 1:
            return respawn_strs[0][1]

        # Multiple zones with different times - show zone names
        formatted = [f"{time_str} ({zone})" for zone, time_str in respawn_strs]
        return WIKITEXT_LINE_SEPARATOR.join(formatted)

    def _minutes_to_duration(self, minutes: int) -> str:
        """Convert minutes to human-readable duration.

        Args:
            minutes: Number of minutes (already rounded)

        Returns:
            Human-readable duration string (e.g., "7 minutes", "1 minute")
        """
        if minutes <= 0:
            return ""
        if minutes == 1:
            return "1 minute"
        return f"{minutes} minutes"

    def _format_loot_drops(
        self,
        loot_drops: list[LootDropInfo],
        character_display_name: str,
    ) -> tuple[str, str]:
        """Format loot drops for wiki template."""
        if not loot_drops:
            return ("", "")

        guaranteed_entries: list[tuple[tuple[float, str], str]] = []
        all_entries: list[tuple[tuple[float, str], str]] = []

        for drop in loot_drops:
            if not drop.item_stable_key:
                raise ValueError(f"Invalid loot drop for {character_display_name}: missing item_stable_key")
            if drop.drop_probability <= 0:
                continue  # Zero probability drops are valid (disabled drops)

            item_link = self._resolver.item_link(drop.item_stable_key)
            display_name = self._resolver.resolve_display_name(drop.item_stable_key)

            probability_text = f"{drop.drop_probability:.1f}%"
            entry_with_pct = f"{item_link} ({probability_text})"

            refs: list[str] = []
            if drop.is_visible:
                refs.append(
                    f"<ref>If {character_display_name} has {item_link} equipped, it is guaranteed to drop.</ref>"
                )
            if drop.item_unique:
                refs.append(
                    f"<ref>If the player is already holding {item_link} in their "
                    f"inventory, another will not drop.</ref>"
                )

            if refs:
                entry_with_pct += "".join(refs)

            sort_key = (-drop.drop_probability, display_name.lower())
            all_entries.append((sort_key, entry_with_pct))

            if drop.is_guaranteed:
                guaranteed_entries.append(((0.0, display_name.lower()), str(item_link)))

        def _join_entries(entries: Sequence[tuple[tuple[float, str], str]]) -> str:
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
        spells: str,
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
            "spells": spells,
        }

        return context

    def _format_ability_links(
        self,
        spells: list[str],
    ) -> str:
        """Format list of spells as {{AbilityLink}} templates separated by <br>.

        Args:
            spells: List of spell stable keys

        Returns:
            Formatted string like "{{AbilityLink|Spell1}}<br>{{AbilityLink|Spell2}}"
            sorted alphabetically by display name, or empty string if no spells

        Examples:
            >>> spells = ["spell:fireball"]
            >>> self._format_ability_links(spells)
            '{{AbilityLink|Fireball}}'
        """
        if not spells:
            return ""

        # Create link objects and filter out excluded spells (page_title=None)
        links = [self._resolver.ability_link(key) for key in spells]
        links = [link for link in links if link.page_title is not None]

        # Sort by display name (WikiLink.__lt__ handles this)
        links.sort()

        return "<br>".join(str(link) for link in links)
