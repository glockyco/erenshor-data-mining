"""What one copy of a vendor sells."""

from dataclasses import dataclass

__all__ = ["VendorStockEntry"]


@dataclass(frozen=True)
class VendorStockEntry:
    """One item that one copy of a vendor sells.

    A vendor is a deduplication group: the copies that share its page, such as
    backup copies or the placements of a furniture set.
    """

    vendor_key: str
    copy_key: str
    # The Reliquary furniture set whose placement spawns this copy, if any.
    furniture_key: str | None
    item_key: str
    # The quest whose completion adds the item, or None when it is always in stock.
    quest_key: str | None
