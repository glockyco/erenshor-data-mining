"""Contracts for representative wiki sample specifications."""

from __future__ import annotations

from typing import cast

import pytest

from erenshor.application.wiki.representative_samples import (
    parse_representative_sample_spec,
    required_sample_boundaries,
)


def _sample(identity: str, generator: str, boundaries: list[str]) -> dict[str, object]:
    return {
        "identity": identity,
        "generator": generator,
        "title": identity.title(),
        "stable_keys": [identity],
        "boundaries": boundaries,
        "required_templates": {},
        "required_text": [],
    }


def _valid_data() -> dict[str, object]:
    required = required_sample_boundaries()
    entity_boundaries = sorted(
        boundary
        for boundary in required
        if boundary.startswith(("entity.", "item_kind.")) or boundary == "generator.entities"
    )
    zone_boundaries = sorted(
        boundary for boundary in required if boundary.startswith("zone.") or boundary == "generator.zones"
    )
    return {
        "version": 1,
        "samples": [
            _sample("sample:entities", "entities", entity_boundaries),
            _sample("sample:weapons", "weapons_overview", ["generator.weapons_overview"]),
            _sample("sample:armor", "armor_overview", ["generator.armor_overview"]),
            _sample("sample:zones", "zones", zone_boundaries),
        ],
    }


def _samples(data: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", data["samples"])


def _boundaries(sample: dict[str, object]) -> list[str]:
    return cast("list[str]", sample["boundaries"])


def test_complete_spec_is_accepted() -> None:
    spec = parse_representative_sample_spec(_valid_data())

    assert spec.boundaries == required_sample_boundaries()


@pytest.mark.parametrize(
    ("field", "message"),
    [("identity", "Duplicate sample identities"), ("title", "Duplicate sample titles")],
)
def test_duplicate_page_identity_is_rejected(field: str, message: str) -> None:
    data = _valid_data()
    samples = _samples(data)
    samples[1][field] = samples[0][field]

    with pytest.raises(ValueError, match=message):
        _ = parse_representative_sample_spec(data)


def test_duplicate_boundary_is_rejected() -> None:
    data = _valid_data()
    boundaries = _boundaries(_samples(data)[0])
    boundaries.append(boundaries[0])

    with pytest.raises(ValueError, match="Duplicate boundaries"):
        _ = parse_representative_sample_spec(data)


def test_uncovered_boundary_is_rejected() -> None:
    data = _valid_data()
    _ = _boundaries(_samples(data)[0]).pop()

    with pytest.raises(ValueError, match="uncovered boundaries"):
        _ = parse_representative_sample_spec(data)


def test_unknown_boundary_is_rejected() -> None:
    data = _valid_data()
    _boundaries(_samples(data)[0]).append("entity.imaginary")

    with pytest.raises(ValueError, match="unknown boundaries"):
        _ = parse_representative_sample_spec(data)


def test_boundary_owned_by_wrong_generator_is_rejected() -> None:
    data = _valid_data()
    samples = _samples(data)
    entity_boundaries = _boundaries(samples[0])
    weapon_boundaries = _boundaries(samples[1])
    weapon_boundaries.append(entity_boundaries.pop())

    with pytest.raises(ValueError, match="belongs to generator"):
        _ = parse_representative_sample_spec(data)


def test_identity_must_resolve_to_a_stable_key() -> None:
    data = _valid_data()
    _samples(data)[0]["identity"] = "item:unrelated"

    with pytest.raises(ValueError, match="is not one of its stable keys"):
        _ = parse_representative_sample_spec(data)


def test_page_budget_is_enforced() -> None:
    with pytest.raises(ValueError, match="maximum is 0"):
        _ = parse_representative_sample_spec(_valid_data(), max_pages=0)
