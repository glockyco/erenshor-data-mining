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
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.domain.value_objects.wiki_link import AbilityLink, FactionLink, StandardLink

WIKITEXT_LINE_SEPARATOR = "<br>"


class CharacterSectionGenerator(SectionGeneratorBase):
    """Generator for character wiki sections.

    Generates {{Character}} template wikitext for a SINGLE character entity.
    All name/page resolution uses pre-built link objects and direct entity
    attribute access — no resolver.

    Multi-entity page assembly is handled by PageGenerator classes, not here.
    """

    def __init__(self) -> None:
        super().__init__()

    def generate_template(
        self,
        enriched: EnrichedCharacterData,
        page_title: str,
    ) -> str:
        """Generate template wikitext for a single character."""
        logger.debug(f"Generating template for character: {enriched.character.npc_name}")

        character = enriched.character

        display_name = character.display_name or character.npc_name or ""
        image_name = character.image_name or display_name

        enemy_type = self._format_enemy_type(character, enriched.spawn_infos)
        faction = self._format_faction(character)
        faction_change = self._format_faction_modifiers(character.faction_modifiers or [])
        zones = self._format_zones(enriched.spawn_infos)
        coordinates = self._format_coordinates(enriched.spawn_infos)
        spawn_chance = self._format_spawn_chance(enriched.spawn_infos)
        respawn = self._format_respawn(enriched.spawn_infos)
        guaranteed_drops, drop_rates = self._format_loot_drops(enriched.loot_drops, display_name)
        spells = self._format_ability_links(enriched.spells)

        level_mod_min, level_mod_max = self._calculate_level_mod_range(enriched.spawn_infos)

        is_group_encounter = bool(character.group_encounter)
        variance_min = 0 if is_group_encounter else -1
        variance_max = 0 if is_group_encounter else 1

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
            spells=spells,
            level_mod_min=level_mod_min,
            level_mod_max=level_mod_max,
            variance_min=variance_min,
            variance_max=variance_max,
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
        """Format faction field using pre-built link fields on the character entity."""
        if character.my_world_faction_stable_key:
            # Use pre-populated display/wiki fields from the JOIN in the repository
            display = character.my_world_faction_display_name or character.my_world_faction_stable_key
            wiki = character.my_world_faction_wiki_page_name
            link = FactionLink(page_title=wiki, display_name=display)
            return str(link)

        if character.my_faction in ("Villager", "GoodHuman", "GoodGuard", "OtherGood", "PreyAnimal"):
            return str(FactionLink(page_title="Good", display_name="Good"))

        if character.my_faction and character.my_faction not in ("Player", "PC", "DEBUG"):
            return str(FactionLink(page_title="Evil", display_name="Evil"))

        return ""

    def _format_faction_modifiers(self, faction_modifiers: list[FactionModifier]) -> str:
        """Format faction modifiers using pre-built display/wiki fields."""
        nonzero_mods = [m for m in faction_modifiers if m.modifier_value != 0]
        if not nonzero_mods:
            return ""

        entries: list[tuple[str, str]] = []
        for mod in nonzero_mods:
            display = mod.faction_display_name
            wiki = mod.faction_wiki_page_name
            link = FactionLink(page_title=wiki, display_name=display)
            sign = "+" if mod.modifier_value > 0 else ""
            formatted = f"{sign}{mod.modifier_value} {link}"
            entries.append((display, formatted))

        entries.sort(key=lambda x: x[0])
        return WIKITEXT_LINE_SEPARATOR.join(line for _, line in entries)

    def _format_zones(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format zone list using pre-built zone_link on each spawn info."""
        if not spawn_infos:
            return ""

        seen: dict[str, StandardLink] = {}
        for info in spawn_infos:
            key = info.zone_link.display_name
            if key not in seen:
                seen[key] = info.zone_link

        zone_links = sorted(seen.values(), key=lambda lnk: lnk.display_name.lower())
        return WIKITEXT_LINE_SEPARATOR.join(str(link) for link in zone_links)

    def _format_coordinates(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format coordinates for wiki template."""
        if len(spawn_infos) != 1:
            return ""

        spawn = spawn_infos[0]
        if spawn.x is None or spawn.y is None or spawn.z is None:
            return ""

        return f"{spawn.x:.1f} x {spawn.y:.1f} x {spawn.z:.1f}"

    def _format_spawn_chance(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format spawn chance for wiki template using zone_link.display_name."""
        if not spawn_infos:
            return ""

        any_rare = any(info.is_rare for info in spawn_infos)
        any_unique = any(info.is_unique for info in spawn_infos)

        if not (any_rare or any_unique):
            return ""

        chances = [info.spawn_chance for info in spawn_infos]
        if all(c == 100.0 for c in chances):
            return ""

        chances_by_zone: dict[str, list[float]] = {}
        for info in spawn_infos:
            zone_display = info.zone_link.display_name
            chances_by_zone.setdefault(zone_display, []).append(info.spawn_chance)

        zones_sorted = sorted(chances_by_zone.keys())

        formatted_chances: list[str] = []
        for zone in zones_sorted:
            zone_chances = chances_by_zone[zone]
            min_chance = min(zone_chances)
            max_chance = max(zone_chances)

            if min_chance == max_chance:
                display = f"{round(min_chance)}%"
            else:
                display = f"{round(min_chance)}-{round(max_chance)}%"

            if len(zones_sorted) > 1:
                formatted_chances.append(f"{display} ({zone})")
            else:
                formatted_chances.append(display)

        return WIKITEXT_LINE_SEPARATOR.join(formatted_chances)

    def _format_respawn(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format respawn time using zone_link.display_name."""
        spawn_infos = [s for s in spawn_infos if s.base_respawn is not None]

        if not spawn_infos:
            return ""

        respawns_by_zone: dict[str, list[int]] = {}
        for spawn in spawn_infos:
            zone_display = spawn.zone_link.display_name
            base_respawn = spawn.base_respawn or 0.0
            minutes = round(base_respawn / 60.0)
            respawns_by_zone.setdefault(zone_display, []).append(minutes)

        zones_sorted = sorted(respawns_by_zone.keys())

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

        if len(respawn_strs) == 1:
            return respawn_strs[0][1]

        unique_times = {time_str for _, time_str in respawn_strs}
        if len(unique_times) == 1:
            return respawn_strs[0][1]

        formatted = [f"{time_str} ({zone})" for zone, time_str in respawn_strs]
        return WIKITEXT_LINE_SEPARATOR.join(formatted)

    def _minutes_to_duration(self, minutes: int) -> str:
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
        """Format loot drops using pre-built item_link on each LootDropInfo."""
        if not loot_drops:
            return ("", "")

        guaranteed_entries: list[tuple[tuple[float, str], str]] = []
        all_entries: list[tuple[tuple[float, str], str]] = []

        for drop in loot_drops:
            item_link = drop.item_link
            if item_link.page_title is None:
                continue  # Excluded item — skip
            if drop.drop_probability <= 0:
                continue

            display_name = item_link.display_name
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

    def _calculate_level_mod_range(
        self,
        spawn_infos: list[CharacterSpawnInfo],
    ) -> tuple[int, int]:
        if not spawn_infos:
            return (0, 0)
        level_mods = [info.level_mod for info in spawn_infos]
        return (min(level_mods), max(level_mods))

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
        level_mod_min: int,
        level_mod_max: int,
        variance_min: int,
        variance_max: int,
    ) -> dict[str, str]:
        """Build context for {{Character}} template."""
        xp_multiplier = character.boss_xp_multiplier if character.boss_xp_multiplier else 1.0
        if xp_multiplier == 0.0:
            xp_multiplier = 1.0

        def _format_resistance(
            base_val: int | None, min_val: int | None, max_val: int | None, hand_set: int | None
        ) -> str:
            if hand_set:
                return safe_str(base_val)
            min_r = min_val or 0
            max_r = max_val or 0
            return f"{min_r}-{max_r}" if min_r != max_r else str(min_r)

        return {
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
            "level_mod_min": str(level_mod_min),
            "level_mod_max": str(level_mod_max),
            "variance_min": str(variance_min),
            "variance_max": str(variance_max),
            "xp_multiplier": str(xp_multiplier),
            "health": safe_str(character.effective_hp),
            "mana": safe_str(character.base_mana),
            "ac": safe_str(character.effective_ac),
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

    def _format_ability_links(self, spells: list[AbilityLink]) -> str:
        """Format pre-built AbilityLink objects as <br>-separated wikitext."""
        if not spells:
            return ""
        visible = [link for link in spells if link.page_title is not None]
        visible.sort()
        return "<br>".join(str(link) for link in visible)
