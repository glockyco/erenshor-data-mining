"""Character enrichment service for wiki generation.

This service aggregates and formats all character-related data for wiki template generation:
- Faction modifiers with display name translation
- Spawn point locations (zones, coordinates, respawn times)
- Loot drops with percentages and wiki links
- Enemy type classification (Boss/Rare/Enemy/NPC)
"""

from loguru import logger

from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.infrastructure.database.repositories.factions import FactionRepository
from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
from erenshor.infrastructure.database.repositories.spawn_points import SpawnPointRepository
from erenshor.registry.resolver import RegistryResolver

__all__ = ["CharacterEnricher", "EnrichedCharacterData"]

# MediaWiki line separator for multi-line template fields
WIKITEXT_LINE_SEPARATOR = "<br>"


class EnrichedCharacterData:
    """Enriched character data formatted for wiki templates.

    All fields are pre-formatted as strings ready for template insertion.
    """

    def __init__(
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
    ) -> None:
        """Initialize enriched character data.

        Args:
            character: Original Character entity
            display_name: Display name (with registry overrides applied)
            image_name: Image filename (with registry overrides applied)
            enemy_type: Classified enemy type (Boss/Rare/Enemy/NPC)
            faction: Formatted faction display (wiki link)
            faction_change: Formatted faction modifiers string
            zones: Formatted zone list string
            coordinates: Formatted coordinates string
            spawn_chance: Formatted spawn chance string
            respawn: Formatted respawn time string
            guaranteed_drops: Formatted guaranteed drops list
            drop_rates: Formatted drop rates list
        """
        self.character = character
        self.display_name = display_name
        self.image_name = image_name
        self.enemy_type = enemy_type
        self.faction = faction
        self.faction_change = faction_change
        self.zones = zones
        self.coordinates = coordinates
        self.spawn_chance = spawn_chance
        self.respawn = respawn
        self.guaranteed_drops = guaranteed_drops
        self.drop_rates = drop_rates


class CharacterEnricher:
    """Service for enriching characters with formatted wiki data.

    Aggregates data from multiple repositories and formats it for wiki templates.
    """

    def __init__(
        self,
        faction_repo: FactionRepository,
        spawn_repo: SpawnPointRepository,
        loot_repo: LootTableRepository,
        registry_resolver: RegistryResolver,
    ) -> None:
        """Initialize character enricher.

        Args:
            faction_repo: Repository for faction name translation
            spawn_repo: Repository for spawn point data
            loot_repo: Repository for loot table data
            registry_resolver: Resolver for creating wiki links
        """
        self._faction_repo = faction_repo
        self._spawn_repo = spawn_repo
        self._loot_repo = loot_repo
        self._resolver = registry_resolver

    def enrich(self, character: Character, page_title: str) -> EnrichedCharacterData:
        """Enrich character with formatted wiki data.

        Args:
            character: Character entity to enrich
            page_title: Wiki page title for this character

        Returns:
            EnrichedCharacterData with all fields formatted for wiki templates
        """
        logger.debug(f"Enriching character: {character.npc_name}")

        # Resolve display name from registry (with override support)
        # Default to page title if no override exists
        display_name = self._resolver.resolve_display_name(character.stable_key, page_title)

        # Resolve image name from registry (with override support)
        # Default to page title if no override exists
        image_name = self._resolver.resolve_image_name(character.stable_key, page_title) or page_title

        # Classify enemy type
        enemy_type = self._classify_enemy_type(character)

        # Format faction field
        faction = self._format_faction(character)

        # Format faction modifiers
        faction_change = self._format_faction_modifiers(character.faction_modifiers or [], page_title)

        # Get spawn info
        spawn_infos = self._get_spawn_info(character)

        # Format spawn-related fields
        zones = self._format_zones(spawn_infos)
        coordinates = self._format_coordinates(spawn_infos, character.is_unique or False)
        spawn_chance = self._format_spawn_chance(spawn_infos, character)
        respawn = self._format_respawn(spawn_infos)

        # Format loot drops
        if character.guid:
            loot_drops = self._loot_repo.get_loot_for_character(character.guid)
            guaranteed_drops, drop_rates = self._format_loot_drops(loot_drops, page_title)
        else:
            guaranteed_drops = ""
            drop_rates = ""

        return EnrichedCharacterData(
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

    def _classify_enemy_type(self, character: Character) -> str:
        """Classify character as Boss/Rare/Enemy/NPC.

        Args:
            character: Character entity

        Returns:
            Enemy type string
        """
        if character.is_unique:
            return "Boss"
        if character.is_rare:
            return "Rare"
        if character.is_npc or character.is_friendly:
            return "NPC"
        return "Enemy"

    def _format_faction(self, character: Character) -> str:
        """Format faction field using MyWorldFaction → REFNAME → FactionDesc translation.

        Translation chain: Characters.MyWorldFaction → Factions.REFNAME → Factions.FactionDesc

        Args:
            character: Character entity

        Returns:
            Formatted faction string (wiki link) or empty string
        """
        # Priority 1: MyWorldFaction (direct faction REFNAME lookup)
        if character.my_world_faction:
            # Look up faction display name from REFNAME
            faction_display_names = self._faction_repo.get_faction_display_names([character.my_world_faction])
            faction_desc = faction_display_names.get(character.my_world_faction, character.my_world_faction)
            return self._resolver.faction_link(character.my_world_faction, faction_desc)

        # Priority 2: MyFaction with hardcoded game logic mapping
        # Good-aligned factions: Villager, GoodHuman, GoodGuard, OtherGood, PreyAnimal → "Generic Good"
        # Evil-aligned factions: All others → "Generic Evil"
        if character.my_faction in ("Villager", "GoodHuman", "GoodGuard", "OtherGood", "PreyAnimal"):
            # Map to "Generic Good" faction (REFNAME: GOOD)
            faction_display_names = self._faction_repo.get_faction_display_names(["GOOD"])
            faction_desc = faction_display_names.get("GOOD", "The Followers of Good")
            return self._resolver.faction_link("GOOD", faction_desc)

        # All other MyFaction values (except Player/PC/DEBUG) → "Generic Evil" (REFNAME: EVIL)
        if character.my_faction and character.my_faction not in ("Player", "PC", "DEBUG"):
            faction_display_names = self._faction_repo.get_faction_display_names(["EVIL"])
            faction_desc = faction_display_names.get("EVIL", "The Followers of Evil")
            return self._resolver.faction_link("EVIL", faction_desc)

        return ""

    def _format_faction_modifiers(self, modifiers: list[FactionModifier], character_name: str) -> str:
        """Format faction modifiers with display names.

        Args:
            modifiers: List of FactionModifier objects
            character_name: Character name for wiki link context

        Returns:
            Formatted faction modifiers string (e.g., "+3 [[Citizens of Port Azure]]<br/>-5 [[Savannah Priel]]")
        """
        if not modifiers:
            return ""

        # Filter out zero-value modifiers
        nonzero_mods = [m for m in modifiers if m.modifier_value != 0]
        if not nonzero_mods:
            return ""

        # Get display names for all faction REFNAMEs
        refnames = [m.faction_refname for m in nonzero_mods]
        faction_display_names = self._faction_repo.get_faction_display_names(refnames)

        # Build formatted entries with display names
        entries: list[tuple[str, str]] = []  # (display_name, formatted_line)
        for mod in nonzero_mods:
            display_name = faction_display_names.get(mod.faction_refname, mod.faction_refname)
            sign = "+" if mod.modifier_value > 0 else ""
            faction_link = self._resolver.faction_link(mod.faction_refname, display_name)
            formatted = f"{sign}{mod.modifier_value} {faction_link}"
            entries.append((display_name, formatted))

        # Sort by display name for consistency
        entries.sort(key=lambda x: x[0])

        # Join with line separator
        return WIKITEXT_LINE_SEPARATOR.join(line for _, line in entries)

    def _get_spawn_info(self, character: Character) -> list[CharacterSpawnInfo]:
        """Get spawn info for character.

        Args:
            character: Character entity

        Returns:
            List of CharacterSpawnInfo objects
        """
        return self._spawn_repo.get_spawn_info_for_character(
            character_guid=character.guid,
            character_id=character.id,
            is_prefab=bool(character.is_prefab),
        )

    def _format_zones(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format zone list for wiki template.

        Args:
            spawn_infos: List of spawn point info

        Returns:
            Formatted zone string (e.g., "[[Port Azure]]<br/>[[Hidden Hills]]")
        """
        if not spawn_infos:
            return ""

        # Extract unique zone display names and scene names
        zone_pairs = sorted({(info.scene, info.zone_display) for info in spawn_infos}, key=lambda x: x[1])

        # Format as wiki links
        zone_links = [self._resolver.zone_link(scene, zone_display) for scene, zone_display in zone_pairs]

        return WIKITEXT_LINE_SEPARATOR.join(zone_links)

    def _format_coordinates(self, spawn_infos: list[CharacterSpawnInfo], is_unique: bool) -> str:
        """Format coordinates for wiki template.

        Only shows coordinates for unique/non-prefab characters with single spawn points.

        Args:
            spawn_infos: List of spawn point info
            is_unique: Whether character is unique

        Returns:
            Formatted coordinates string or empty string
        """
        # Only show coordinates for single spawn point (unique characters or non-prefabs)
        if len(spawn_infos) != 1:
            return ""

        spawn = spawn_infos[0]

        # Check if we have coordinates
        if spawn.x is None or spawn.y is None or spawn.z is None:
            return ""

        # Format as X x Y x Z with one decimal place
        return f"{spawn.x:.1f} x {spawn.y:.1f} x {spawn.z:.1f}"

    def _format_spawn_chance(self, spawn_infos: list[CharacterSpawnInfo], character: Character) -> str:
        """Format spawn chance for wiki template.

        Only shows spawn chance for rare and unique characters that have at least
        one spawn point with <100% spawn chance (indicating rare spawn mechanics).
        For unique characters, only shows if not all spawns are 100%.

        Args:
            spawn_infos: List of spawn point info
            character: Character entity for type checking

        Returns:
            Formatted spawn chance string
        """
        if not spawn_infos:
            return ""

        # Only show spawn chance for rare/unique characters
        is_common = bool(character.is_common)
        is_rare = bool(character.is_rare)
        is_unique = bool(character.is_unique)

        if is_common or not (is_rare or is_unique):
            return ""

        # Collect all spawn chances
        chances = [info.spawn_chance for info in spawn_infos]

        # Don't show if all spawns are 100% (no rare spawn mechanics)
        if all(c == 100.0 for c in chances):
            return ""

        # Format unique chances
        unique_chances = sorted(set(chances), reverse=True)
        formatted_chances = [f"{int(chance)}%" for chance in unique_chances]

        return WIKITEXT_LINE_SEPARATOR.join(formatted_chances)

    def _format_respawn(self, spawn_infos: list[CharacterSpawnInfo]) -> str:
        """Format respawn time for wiki template.

        Shows zone-specific respawn times when they vary across zones.
        If all zones have the same respawn, shows single time without zone name.

        Args:
            spawn_infos: List of spawn point info

        Returns:
            Formatted respawn time string (e.g., "2 minutes" or "2 minutes (Port Azure)<br>3 minutes (Hidden Hills)")
        """
        if not spawn_infos:
            return ""

        # Group by zone and get minimum respawn time for each zone
        respawn_by_zone: dict[str, float] = {}
        for spawn in spawn_infos:
            zone_display = spawn.zone_display
            base_respawn = spawn.base_respawn or 0.0

            # Use minimum respawn time for each zone
            current_respawn = respawn_by_zone.get(zone_display)
            if current_respawn is None:
                respawn_by_zone[zone_display] = base_respawn
            else:
                respawn_by_zone[zone_display] = min(current_respawn, base_respawn)

        # Sort zones by name for consistent output
        zones_sorted = sorted(respawn_by_zone.keys())

        # Format respawn times
        respawn_strs = [(zone, self._seconds_to_duration(respawn_by_zone[zone])) for zone in zones_sorted]

        # If only one zone, return just the time (no zone name)
        if len(respawn_strs) == 1:
            return respawn_strs[0][1]

        # If all zones have the same respawn time, return just the time
        unique_times = {time_str for _, time_str in respawn_strs}
        if len(unique_times) == 1:
            return respawn_strs[0][1]

        # Otherwise, show zone-specific respawn times
        formatted = [f"{time_str} ({zone})" for zone, time_str in respawn_strs]
        return WIKITEXT_LINE_SEPARATOR.join(formatted)

    def _seconds_to_duration(self, seconds: float) -> str:
        """Convert seconds to human-readable duration.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string (e.g., "2 minutes 30 seconds")
        """
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

    def _format_loot_drops(self, loot_drops: list[LootDropInfo], character_name: str) -> tuple[str, str]:
        """Format loot drops for wiki template.

        Args:
            loot_drops: List of loot drop info
            character_name: Character name for reference notes

        Returns:
            Tuple of (guaranteed_drops, drop_rates) formatted strings
        """
        if not loot_drops:
            return ("", "")

        # Separate guaranteed and regular drops
        guaranteed_entries: list[tuple[str, str]] = []
        all_entries: list[tuple[float, str]] = []

        for drop in loot_drops:
            if not drop.item_name or drop.drop_probability <= 0:
                continue

            # Create item link using resolver
            item_link = self._resolver.item_link(drop.resource_name, drop.item_name)

            # Get resolved display name for sorting
            stable_key = f"item:{drop.resource_name}"
            resolved_display_name = self._resolver.resolve_display_name(stable_key, drop.item_name)

            # Format with percentage
            probability_text = f"{drop.drop_probability:.1f}%"
            entry_with_pct = f"{item_link} ({probability_text})"

            # Add reference notes
            refs: list[str] = []
            if drop.is_visible:
                refs.append(f"<ref>If {character_name} has {item_link} equipped, it is guaranteed to drop.</ref>")
            if drop.item_unique:
                refs.append(
                    f"<ref>If the player is already holding {item_link} in their inventory, another will not drop.</ref>"
                )

            if refs:
                entry_with_pct += "".join(refs)

            # Sort key for drop_rates: descending probability, ascending name
            sort_key = (-drop.drop_probability, resolved_display_name.lower())

            all_entries.append((sort_key[0], entry_with_pct))

            # Guaranteed drops also get entry without percentage
            # Sort guaranteed drops alphabetically by resolved display name
            if drop.is_guaranteed:
                guaranteed_entries.append((resolved_display_name.lower(), item_link))

        # Sort and format
        def _join_entries(entries: list[tuple[float | str, str]]) -> str:
            if not entries:
                return ""
            entries.sort()
            seen = set()
            output = []
            for _, entry_text in entries:
                if entry_text not in seen:
                    seen.add(entry_text)
                    output.append(entry_text)
            return WIKITEXT_LINE_SEPARATOR.join(output)

        # Only show guaranteed drops if there are 2+ (single 100% is obvious)
        guaranteed_str = ""
        if len(guaranteed_entries) >= 2:
            guaranteed_str = _join_entries(guaranteed_entries)

        return (guaranteed_str, _join_entries(all_entries))
