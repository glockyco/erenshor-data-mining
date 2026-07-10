"""Parity checks for Cargo relation cutovers."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, Protocol


class RelationRow(Protocol):
    page: str
    fields: Mapping[str, str]


class RelationExpectation(NamedTuple):
    """Expected relation row loaded from a parity fixture."""

    page: str
    fields: dict[str, str]


_LEGACY_DROP_FIELDS = ("Page", "CharacterKey", "ItemKey", "DropProbability", "IsGuaranteed")


def load_legacy_drop_expectations(path: Path) -> list[RelationExpectation]:
    """Load legacy Drops rows for parity only; no Cargo table is queried."""
    rows: list[RelationExpectation] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        values = raw_line.split("\t")
        if len(values) != len(_LEGACY_DROP_FIELDS):
            raise ValueError(f"{path}: expected 5 tab-separated fields, got {len(values)}")
        fields: dict[str, str] = dict(zip(_LEGACY_DROP_FIELDS, values, strict=True))
        rows.append(RelationExpectation(page=fields.pop("Page"), fields=fields))
    return rows


def compare_drop_obtained_from_parity(
    drops: list[RelationExpectation],
    obtained_from: Sequence[RelationRow],
) -> list[str]:
    """Compare canonical Drops relations with item-owned drop rows.

    Manual character override pages duplicate semantic relations. Identical
    tuples across pages collapse to one canonical relation, while duplicate
    rows within a single page retain their multiplicity.
    """
    drop_counts_by_relation: defaultdict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for expectation in drops:
        fields = expectation.fields
        relation = (
            fields["CharacterKey"],
            fields["ItemKey"],
            fields["DropProbability"],
            fields["IsGuaranteed"],
        )
        drop_counts_by_relation[relation][expectation.page] += 1
    canonical_drops = Counter(
        {relation: max(page_counts.values()) for relation, page_counts in drop_counts_by_relation.items()}
    )

    canonical_obtained = Counter(
        (
            fields["SourceKey"],
            fields["ItemKey"],
            fields["Probability"],
            fields["IsGuaranteed"],
        )
        for expectation in obtained_from
        if (fields := expectation.fields)["SourceType"] == "drop"
    )

    failures: list[str] = []
    for relation, count in sorted(canonical_drops.items()):
        if missing := count - canonical_obtained[relation]:
            failures.append(f"ObtainedFrom missing drop relation {relation} x{missing}")
    for relation, count in sorted(canonical_obtained.items()):
        if extra := count - canonical_drops[relation]:
            failures.append(f"ObtainedFrom has extra drop relation {relation} x{extra}")
    return failures
