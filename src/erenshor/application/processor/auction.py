"""Derive the clean item auctionability flag from player auction code facts.

The predicate is verified against GameData.ActivateSlotForAuction. The
extracted comparison strings and the exact listing-gate AST are tripwires: if
the player-facing auction rules change, validation fails before item rows are
written so the rule can be re-derived instead of silently drifting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .writer import Writer

EXPECTED_AUCTION_GATES: dict[tuple[str, str], str] = {
    # code-fact: auction.player_listing_gates
    ("auction.player_listing_gates", "item_level"): "!= 0",
    ("auction.player_listing_gates", "item_value"): "!= 0",
    # code-fact: auction.player_listing_gate
    ("auction.player_listing_gate", "ok"): "true",
}


def validate_auction_gates(code_facts: dict[tuple[str, str], str]) -> None:
    """Reject auction predicate use when player listing rules have drifted."""
    for key, expected in EXPECTED_AUCTION_GATES.items():
        actual = code_facts.get(key)
        if actual != expected:
            message = (
                f"auction gate drift: {key} expected {expected!r}, got {actual!r}. "
                + "Re-derive IsAuctionable from GameData.ActivateSlotForAuction."
            )
            raise ValueError(message)


def derive_is_auctionable(
    item_level: int | None,
    item_value: int | None,
    no_trade_no_destroy: bool | int | None,
    required_slot: str | None,
) -> bool:
    """Return whether the player-facing auction UI accepts an item."""
    return (
        item_level is not None
        and item_level != 0
        and item_value is not None
        and item_value != 0
        and not no_trade_no_destroy
        and required_slot is not None
        and required_slot != "General"
    )


@dataclass(frozen=True)
class ListingRules:
    """Extracted bounds for successful draws, not exhausted-retry outliers."""

    direct_cap: int
    direct_above: int
    direct_below: int
    sim_cap: int
    player_cap: int

    @classmethod
    def from_facts(cls, facts: dict[tuple[str, str], str]) -> ListingRules:
        # code-fact: auction.item_database_pool
        # code-fact: auction.direct_draw
        # code-fact: auction.sim_level_clamp
        # code-fact: auction.display_item
        # code-fact: auction.replacement_draw
        # code-fact: auction.gear_draw
        # code-fact: auction.gear_rival_bounds
        # code-fact: auction.gear_lower_window
        # code-fact: auction.gear_class_gate
        # code-fact: auction.gear_duelist_effect
        # code-fact: auction.gear_paladin_effect
        # code-fact: auction.stored_items_transfer
        # code-fact: auction.broker_gate
        # code-fact: auction.admission
        # code-fact: auction.gear_incompatible_storage
        # code-fact: auction.gear_primary_storage
        # code-fact: auction.gear_secondary_storage
        # code-fact: auction.gear_base_upper
        # code-fact: auction.gear_normal_upper
        # code-fact: auction.gear_base_lower
        # code-fact: auction.gear_initial_lower
        assertions = (
            "item_database_pool",
            "direct_draw",
            "sim_level_clamp",
            "display_item",
            "replacement_draw",
            "gear_draw",
            "gear_rival_bounds",
            "gear_lower_window",
            "gear_class_gate",
            "gear_duelist_effect",
            "gear_paladin_effect",
            "stored_items_transfer",
            "broker_gate",
            "admission",
            "gear_incompatible_storage",
            "gear_primary_storage",
            "gear_secondary_storage",
            "gear_base_upper",
            "gear_normal_upper",
            "gear_base_lower",
            "gear_initial_lower",
        )
        for name in assertions:
            if facts.get((f"auction.{name}", "ok")) != "true":
                raise ValueError(f"Auction listing code fact missing: auction.{name}")
        # code-fact: auction.updateah_gates
        # Cleanup's item_value comparison is not an admission gate.
        if facts.get(("auction.updateah_gates", "item_level")) != ">= 40":
            raise ValueError("Re-derive auction listing admission level cap")
        # code-fact: auction.replacebag_gates
        if facts.get(("auction.replacebag_gates", "item_level")) != "<= 0,> 39":
            raise ValueError("Re-derive auction replacement level bounds")
        # code-fact: auction.direct_level_cap
        # code-fact: auction.direct_level_above
        # code-fact: auction.direct_level_below
        # code-fact: auction.sim_level_cap
        # code-fact: auction.player_level_cap
        return cls(
            *(
                int(facts[(f"auction.{name}", "value")])
                for name in (
                    "direct_level_cap",
                    "direct_level_above",
                    "direct_level_below",
                    "sim_level_cap",
                    "player_level_cap",
                )
            )
        )


@dataclass(frozen=True)
class ListingItem:
    key: str
    item_id: str
    level: int
    value: int
    no_trade: bool = False
    furniture: bool = False
    unique: bool = False
    cannot_sell: bool = False
    sim_cannot_get: bool = False
    taught_spell_level: int | None = None
    slot: str | None = None
    classes: frozenset[str] = frozenset()
    worn_effect_id: str | None = None


def derive_listing_routes(
    item: ListingItem,
    rules: ListingRules,
    currency_keys: set[str],
    playable_classes: set[str],
) -> list[dict[str, object]]:
    """Return ordinary routes that can put this item in front of the player.

    The game caps retries rather than guaranteeing a valid final draw. Neither
    direct nor replacement windows are empty at normal levels in shipped data;
    the table describes successful draws, not those exceptional fallthroughs.
    Replacement is deliberately NOT passed through the original display gate.
    """
    rows: list[dict[str, object]] = []

    def add(
        route: str,
        sim_min: int | None = None,
        sim_max: int | None = None,
        player_min: int | None = None,
        player_max: int | None = None,
    ) -> None:
        rows.append(
            {
                "item_stable_key": item.key,
                "route": route,
                "min_sim_level": sim_min,
                "max_sim_level": sim_max,
                "min_player_level": player_min,
                "max_player_level": player_max,
            }
        )

    # code-fact: auction.display_item
    preserved = (
        item.item_id not in {"315843", "1574025"}
        and item.key not in currency_keys
        and not item.no_trade
        and item.value > 0
        and not item.cannot_sell
        and not item.furniture
        and not item.unique
        and (item.taught_spell_level is None or item.taught_spell_level >= 0)
    )
    # code-fact: auction.direct_draw
    sim_min = max(1, item.level - rules.direct_above)
    sim_max = min(rules.sim_cap, item.level + rules.direct_below)
    if preserved and 0 <= item.level <= rules.direct_cap and sim_min <= sim_max:
        add("direct", sim_min, sim_max)

    # code-fact: auction.replacement_draw
    # Rare items have a nonzero acceptance chance. PlayerCannotSell and taught
    # spells are checked before replacement, not on the replacement itself.
    if (
        not item.sim_cannot_get
        and not item.unique
        and not item.no_trade
        and not item.furniture
        and item.value != 0
        and item.key not in currency_keys
        and 1 <= item.level <= min(39, rules.player_cap)
    ):
        add("replacement", player_min=item.level, player_max=rules.player_cap)

    # code-fact: auction.gear_class_gate
    # code-fact: auction.gear_duelist_effect
    # code-fact: auction.gear_paladin_effect
    can_store = (
        bool(playable_classes - item.classes)
        or item.slot in {"Primary", "Secondary", "PrimaryOrSecondary"}
        or item.worn_effect_id in {"45807425", "18068040", "16613100"}
    )
    # code-fact: auction.gear_draw
    # code-fact: auction.gear_rival_bounds
    # code-fact: auction.gear_lower_window
    # Rival windows contain ordinary windows: +6, and a possible -3. Below
    # sim level 35 the rival cap is 37; at 35 it rises to 45. UpdateAH still
    # rejects >=40. Class-incompatible draws go to StoredItems, not to waste.
    gear_min = max(1, item.level - 6, 35 if item.level > 37 else 1)
    gear_max = min(rules.sim_cap, item.level + 3)
    if preserved and not item.sim_cannot_get and can_store and 1 <= item.level < 40 and gear_min <= gear_max:
        add("gear_surplus", gear_min, gear_max)
    return rows


def process_auction_listings(writer: Writer) -> None:
    """Derive all listing routes and broker identities from the clean inputs."""
    conn = writer.conn
    facts = {
        (str(row[0]), str(row[1])): str(row[2]) for row in conn.execute("SELECT fact_id, key, value FROM code_facts")
    }
    rules = ListingRules.from_facts(facts)
    currency_keys = {
        str(row[0])
        for row in conn.execute(
            "SELECT item_stable_key FROM special_world_drops WHERE pool IN ('Planar', 'Sivak', 'PlanarShard')"
        )
    }
    if len(currency_keys) != 3:
        raise ValueError("Auction currency references do not resolve to three exported world-drop items")
    playable_classes = {str(row[0]) for row in conn.execute("SELECT DISTINCT class_name FROM class_starting_items")}
    if not playable_classes:
        raise ValueError("Auction gear derivation has no playable starting classes")
    classes: dict[str, set[str]] = {}
    for row in conn.execute("SELECT item_stable_key, class_name FROM item_classes"):
        classes.setdefault(str(row[0]), set()).add(str(row[1]))
    rows: list[dict[str, object]] = []
    for row in conn.execute("""
        SELECT i.*, taught.required_level AS taught_level, worn.id AS worn_id
        FROM items i
        LEFT JOIN spells taught ON taught.stable_key = i.teach_spell_stable_key
        LEFT JOIN spells worn ON worn.stable_key = i.worn_effect_stable_key
        ORDER BY i.stable_key
    """):
        item = ListingItem(
            key=row["stable_key"],
            item_id=row["id"],
            level=row["item_level"],
            value=row["item_value"],
            no_trade=bool(row["no_trade_no_destroy"]),
            furniture=bool(row["furniture_set"]),
            unique=bool(row["is_unique"]),
            cannot_sell=bool(row["player_cannot_sell"]),
            sim_cannot_get=bool(row["sim_players_cant_get"]),
            taught_spell_level=row["taught_level"],
            slot=row["required_slot"],
            classes=frozenset(classes.get(row["stable_key"], ())),
            worn_effect_id=row["worn_id"],
        )
        rows.extend(derive_listing_routes(item, rules, currency_keys, playable_classes))
    writer.insert_auction_house_items(rows)
    # code-fact: auction.broker_names
    # The game compares the GameObject name, not the display name. Summoned
    # Pocket Auctions has no permanent exported character and no invented pin.
    names = facts[("auction.broker_names", "strings")].split(",")
    placeholders = ",".join("?" for _ in names)
    brokers: list[dict[str, object]] = [
        {"character_stable_key": str(row[0])}
        for row in conn.execute(
            f"SELECT stable_key FROM characters WHERE object_name IN ({placeholders}) ORDER BY stable_key", names
        )
    ]
    if not brokers:
        raise ValueError("Auction broker code fact resolves to no exported characters")
    writer.insert_auction_house_brokers(brokers)
    logger.info(f"Auction House: {len(rows)} item routes, {len(brokers)} broker copies")
