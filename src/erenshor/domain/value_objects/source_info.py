"""Item source information value object."""

from dataclasses import dataclass, field

from erenshor.domain.value_objects.wiki_link import CharacterLink, ClassLink, ItemLink, QuestLink, WikiLink, ZoneLink

__all__ = ["ObtainedFromInfo", "SourceInfo", "UsedInInfo", "WorldDropInfo"]


@dataclass(frozen=True)
class ObtainedFromInfo:
    """Stable-keyed provenance edge for an item-owned obtainability row."""

    source_type: str
    source_key: str | None
    probability: float | None = None
    is_guaranteed: bool = False
    quantity: int | None = None
    condition: str | None = None


@dataclass(frozen=True)
class UsedInInfo:
    """Stable-keyed item usage edge for an item-owned UsedIn row."""

    use_type: str
    target_key: str
    quantity: int | None = None
    slot: int | None = None


@dataclass(frozen=True)
class WorldDropInfo:
    """A special world drop roll that yields an item on any loot-table kill."""

    # Chance per kill in percent at the default loot rate.
    probability: float
    # The killed character's level must exceed this. 0 means any level.
    min_level_exclusive: int

    @property
    def condition(self) -> str | None:
        return f"enemy level above {self.min_level_exclusive}" if self.min_level_exclusive > 0 else None


@dataclass
class SourceInfo:
    """All source information for an item.

    All fields carry pre-built WikiLink objects populated by repository JOINs.
    Section generators iterate link lists and call str(link) — no resolver
    or lookup at generation time.
    """

    # Vendors
    vendors: list[CharacterLink] = field(default_factory=list)

    # Drops from characters
    drops: list[tuple[WikiLink, float]] = field(default_factory=list)

    # Dialog givers with the quest that each one requires first
    givers: list[tuple[CharacterLink, QuestLink | None]] = field(default_factory=list)

    # Items whose use yields this item: (item_link, chance, zone the use needs)
    item_uses: list[tuple[ItemLink, float | None, str | None]] = field(default_factory=list)

    # Zones with mining nodes of this item: (zone_link, chance per node)
    mining: list[tuple[ZoneLink, float]] = field(default_factory=list)

    # Zones with water that yields this item: (zone_link, "day" or "night", chance per catch)
    fishing: list[tuple[ZoneLink, str, float]] = field(default_factory=list)

    # Chances per catch in any water, from the fishing bonus
    fishing_bonus: list[float] = field(default_factory=list)

    # Zones with item bags of this item
    item_bags: list[ZoneLink] = field(default_factory=list)

    # Classes that start with this item
    starting_classes: list[ClassLink] = field(default_factory=list)

    # Whether every playable class starts with this item
    every_class_starts_with_item: bool = False

    # Quests
    quest_rewards: list[QuestLink] = field(default_factory=list)
    quest_requirements: list[QuestLink] = field(default_factory=list)

    # Crafting
    craft_sources: list[ItemLink] = field(default_factory=list)
    # Full recipe to craft this item: mold link + ingredient links with quantities
    craft_recipe: list[tuple[ItemLink, int]] = field(default_factory=list)
    # Items that require this item as a crafting component
    component_for: list[ItemLink] = field(default_factory=list)
    # What this mold produces: (result_link, quantity)
    crafting_results: list[tuple[ItemLink, int]] = field(default_factory=list)
    # What this mold needs as ingredients: (ingredient_link, quantity)
    recipe_ingredients: list[tuple[ItemLink, int]] = field(default_factory=list)

    # Items produced by using this item (e.g. a fossil's random pool):
    # (dropped_item_link, drop_probability, is_guaranteed).
    item_drops: list[tuple[ItemLink, float, bool]] = field(default_factory=list)

    # Special world drops that any loot-table kill can roll.
    world_drops: list[WorldDropInfo] = field(default_factory=list)

    # Unified item-owned obtainability rows with stable source identity.
    obtained_from: list[ObtainedFromInfo] = field(default_factory=list)

    # Unified item-owned usage rows keyed by target StableKey.
    used_in: list[UsedInInfo] = field(default_factory=list)
