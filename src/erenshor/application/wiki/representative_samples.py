"""Validated representative-page specifications for wiki golden snapshots."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

import mwparserfromhell

from erenshor.application.wiki.generators.registry import WIKI_GENERATORS
from erenshor.domain.entities.item_kind import ItemKind

_ENTITY_BOUNDARIES = frozenset(
    {
        "entity.item",
        "entity.character",
        "entity.spell",
        "entity.skill",
        "entity.stance",
        "entity.multi_entity",
        "entity.item.equipment_tooltip",
        "entity.item.proc",
        "entity.item.preserved_content",
        "entity.character.preserved_content",
        "entity.ability.tooltip",
        "zone.map_and_connections",
    }
)


@dataclass(frozen=True, slots=True)
class RepresentativePageSample:
    """One stable page identity and the output boundaries it represents."""

    identity: str
    generator: str
    title: str
    stable_keys: tuple[str, ...]
    boundaries: tuple[str, ...]
    required_templates: Mapping[str, int]
    required_text: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepresentativeSampleSpec:
    """A complete, validated representative wiki page selection."""

    samples: tuple[RepresentativePageSample, ...]

    @property
    def titles(self) -> tuple[str, ...]:
        return tuple(sample.title for sample in self.samples)

    @property
    def boundaries(self) -> frozenset[str]:
        return frozenset(boundary for sample in self.samples for boundary in sample.boundaries)


def registered_generator_names() -> frozenset[str]:
    """Return the generator registry identities covered by the sample contract."""
    return frozenset(registration.name for registration in WIKI_GENERATORS)


def required_sample_boundaries() -> frozenset[str]:
    """Return every generator and branch that representative snapshots must cover."""
    generator_boundaries = {f"generator.{name}" for name in registered_generator_names()}
    item_boundaries = {f"item_kind.{kind.value}" for kind in ItemKind}
    return frozenset(generator_boundaries | item_boundaries | _ENTITY_BOUNDARIES)


def load_representative_sample_spec(path: Path, *, max_pages: int = 99) -> RepresentativeSampleSpec:
    """Load and validate a checked-in representative-page specification."""
    try:
        data = cast("object", json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid representative sample JSON in {path}: {exc}") from exc
    return parse_representative_sample_spec(data, max_pages=max_pages)


def parse_representative_sample_spec(data: object, *, max_pages: int = 99) -> RepresentativeSampleSpec:
    """Validate decoded sample data against the current generator branch inventory."""
    root = _mapping(data, "specification")
    if set(root) != {"version", "samples"}:
        raise ValueError("Representative sample specification must contain only 'version' and 'samples'")
    if root["version"] != 1:
        raise ValueError(f"Unsupported representative sample specification version: {root['version']!r}")

    raw_samples = _sequence(root["samples"], "samples")
    if not raw_samples:
        raise ValueError("Representative sample specification has no pages")
    if len(raw_samples) > max_pages:
        raise ValueError(
            f"Representative sample specification selects {len(raw_samples)} pages, maximum is {max_pages}"
        )

    samples = tuple(_parse_sample(raw, index) for index, raw in enumerate(raw_samples))
    _reject_duplicates(samples)

    known_generators = registered_generator_names()
    unknown_generators = sorted({sample.generator for sample in samples} - known_generators)
    if unknown_generators:
        raise ValueError(f"Unknown representative sample generators: {unknown_generators}")
    _validate_boundary_owners(samples)

    required = required_sample_boundaries()
    covered = {boundary for sample in samples for boundary in sample.boundaries}
    missing = sorted(required - covered)
    unknown = sorted(covered - required)
    if missing or unknown:
        parts: list[str] = []
        if missing:
            parts.append(f"uncovered boundaries: {missing}")
        if unknown:
            parts.append(f"unknown boundaries: {unknown}")
        raise ValueError("Representative sample boundary mismatch: " + ". ".join(parts))

    return RepresentativeSampleSpec(samples=samples)


def validate_representative_sample_content(sample: RepresentativePageSample, content: str) -> None:
    """Validate the structural markers that make one selected page representative."""
    templates = Counter(
        str(template.name).strip() for template in mwparserfromhell.parse(content).filter_templates(recursive=False)
    )
    errors: list[str] = []
    for template_name, minimum in sample.required_templates.items():
        if templates[template_name] < minimum:
            errors.append(
                f"expected at least {minimum} top-level {template_name!r} templates, found {templates[template_name]}"
            )
    for marker in sample.required_text:
        if marker not in content:
            errors.append(f"required marker is missing: {marker!r}")
    if errors:
        raise ValueError(f"Representative sample {sample.title!r} is invalid: " + ". ".join(errors))


def _parse_sample(value: object, index: int) -> RepresentativePageSample:
    raw = _mapping(value, f"samples[{index}]")
    expected_fields = {
        "identity",
        "generator",
        "title",
        "stable_keys",
        "boundaries",
        "required_templates",
        "required_text",
    }
    if set(raw) != expected_fields:
        missing = sorted(expected_fields - set(raw))
        extra = sorted(set(raw) - expected_fields)
        raise ValueError(f"samples[{index}] field mismatch: missing={missing}, extra={extra}")

    required_templates_raw = _mapping(raw["required_templates"], f"samples[{index}].required_templates")
    required_templates: dict[str, int] = {}
    for name, count in required_templates_raw.items():
        template_name = _nonblank(name, f"samples[{index}].required_templates key")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError(f"Template count for {template_name!r} must be a positive integer")
        required_templates[template_name] = count

    return RepresentativePageSample(
        identity=_nonblank(raw["identity"], f"samples[{index}].identity"),
        generator=_nonblank(raw["generator"], f"samples[{index}].generator"),
        title=_nonblank(raw["title"], f"samples[{index}].title"),
        stable_keys=_strings(raw["stable_keys"], f"samples[{index}].stable_keys"),
        boundaries=_strings(raw["boundaries"], f"samples[{index}].boundaries", require_nonempty=True),
        required_templates=MappingProxyType(required_templates),
        required_text=_strings(raw["required_text"], f"samples[{index}].required_text"),
    )


def _validate_boundary_owners(samples: tuple[RepresentativePageSample, ...]) -> None:
    for sample in samples:
        for boundary in sample.boundaries:
            expected_generator: str | None = None
            if boundary.startswith("generator."):
                expected_generator = boundary.removeprefix("generator.")
            elif boundary.startswith(("entity.", "item_kind.")):
                expected_generator = "entities"
            elif boundary.startswith("zone."):
                expected_generator = "zones"
            if expected_generator is not None and sample.generator != expected_generator:
                raise ValueError(
                    f"Boundary {boundary!r} belongs to generator {expected_generator!r}, not {sample.generator!r}"
                )


def _reject_duplicates(samples: tuple[RepresentativePageSample, ...]) -> None:
    _require_unique((sample.identity for sample in samples), "sample identities")
    _require_unique((sample.title for sample in samples), "sample titles")
    _require_unique((key for sample in samples for key in sample.stable_keys), "stable keys")
    _require_unique((boundary for sample in samples for boundary in sample.boundaries), "boundaries")
    for sample in samples:
        if sample.stable_keys and sample.identity not in sample.stable_keys:
            raise ValueError(f"Sample identity {sample.identity!r} is not one of its stable keys")
        if not sample.stable_keys and sample.identity != f"generator:{sample.generator}":
            raise ValueError(f"Keyless sample identity must be 'generator:{sample.generator}', got {sample.identity!r}")
        _require_unique(sample.stable_keys, f"stable keys for {sample.identity}")
        _require_unique(sample.boundaries, f"boundaries for {sample.identity}")
        _require_unique(sample.required_text, f"required text for {sample.identity}")


def _require_unique(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"Duplicate {label}: {sorted(duplicates)}")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object with string keys")
    untyped = cast("Mapping[object, object]", value)
    if not all(isinstance(key, str) for key in untyped):
        raise ValueError(f"{label} must be an object with string keys")
    return cast("Mapping[str, object]", untyped)


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return cast("list[object]", value)


def _strings(value: object, label: str, *, require_nonempty: bool = False) -> tuple[str, ...]:
    values = _sequence(value, label)
    result = tuple(_nonblank(item, label) for item in values)
    if require_nonempty and not result:
        raise ValueError(f"{label} must not be empty")
    return result


def _nonblank(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")
    return value


__all__ = [
    "RepresentativePageSample",
    "RepresentativeSampleSpec",
    "load_representative_sample_spec",
    "parse_representative_sample_spec",
    "registered_generator_names",
    "required_sample_boundaries",
    "validate_representative_sample_content",
]
