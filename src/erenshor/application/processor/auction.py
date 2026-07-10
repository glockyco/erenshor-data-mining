"""Derive the clean item auctionability flag from player auction code facts.

The predicate is verified against GameData.ActivateSlotForAuction. The
extracted comparison strings and the exact listing-gate AST are tripwires: if
the player-facing auction rules change, validation fails before item rows are
written so the rule can be re-derived instead of silently drifting.
"""

from __future__ import annotations

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
