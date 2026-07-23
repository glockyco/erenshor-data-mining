"""Representative wiki snapshots selected by stable generator identities."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import cast
from urllib.parse import quote

from erenshor.application.wiki.representative_samples import (
    RepresentativePageSample,
    load_representative_sample_spec,
    registered_generator_names,
    required_sample_boundaries,
    validate_representative_sample_content,
)
from erenshor.domain.entities.item_kind import classify_item_kind

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "tests" / "golden" / "wiki-samples.json"
GOLDEN_WIKI_DIR = REPO_ROOT / "tests" / "golden" / "wiki"
WIKI_DIR = REPO_ROOT / "variants" / "main" / "wiki"
GENERATED_DIR = WIKI_DIR / "generated"
METADATA_PATH = WIKI_DIR / "metadata.json"
DATABASE_PATH = REPO_ROOT / "variants" / "main" / "erenshor-main.sqlite"


def _content_path(sample: RepresentativePageSample) -> Path:
    if sample.generator == "zones":
        return REPO_ROOT / "wiki" / "zones" / f"{sample.title.replace(' ', '_')}.txt"
    filename = f"{quote(sample.title, safe='_-.')}.txt"
    return GENERATED_DIR / filename


def _standard_samples() -> tuple[RepresentativePageSample, ...]:
    spec = load_representative_sample_spec(SPEC_PATH)
    return tuple(sample for sample in spec.samples if sample.generator != "zones")


def test_sample_spec_covers_every_generator_and_behavior_boundary() -> None:
    spec = load_representative_sample_spec(SPEC_PATH)

    assert len(spec.samples) == len(set(spec.titles)) < 100
    assert {sample.generator for sample in spec.samples} == registered_generator_names()
    assert spec.boundaries == required_sample_boundaries()


def test_sample_pages_resolve_stable_identities_and_expected_shapes() -> None:
    spec = load_representative_sample_spec(SPEC_PATH)
    metadata = cast("dict[str, dict[str, object]]", json.loads(METADATA_PATH.read_text(encoding="utf-8")))

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        for sample in spec.samples:
            if sample.generator == "zones":
                zone_rows = cast(
                    "list[tuple[str]]",
                    connection.execute(
                        "SELECT stable_key FROM zones WHERE wiki_page_name = ? ORDER BY stable_key",
                        (sample.title,),
                    ).fetchall(),
                )
                assert zone_rows, f"Zone sample is missing from the clean database: {sample.title}"
                observed_keys = tuple(row[0] for row in zone_rows)
            else:
                assert sample.title in metadata, f"Sample is missing from wiki metadata: {sample.title}"
                raw_keys = metadata[sample.title]["stable_keys"]
                assert isinstance(raw_keys, list)
                key_values = cast("list[object]", raw_keys)
                assert all(isinstance(key, str) for key in key_values)
                observed_keys = tuple(cast("list[str]", key_values))

            assert observed_keys == sample.stable_keys, sample.title

            content_path = _content_path(sample)
            assert content_path.is_file(), f"Representative output is missing: {content_path}"
            content = content_path.read_text(encoding="utf-8")
            validate_representative_sample_content(sample, content)


def test_item_kind_samples_reach_the_declared_classifier_branches() -> None:
    spec = load_representative_sample_spec(SPEC_PATH)

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        for sample in spec.samples:
            item_boundaries = [boundary for boundary in sample.boundaries if boundary.startswith("item_kind.")]
            if not item_boundaries:
                continue
            assert len(item_boundaries) == 1
            assert len(sample.stable_keys) == 1
            item_row = cast(
                "tuple[object, object, object, object, object, object] | None",
                connection.execute(
                    """
                    SELECT required_slot, teach_spell_stable_key, teach_skill_stable_key,
                           template, item_effect_on_click_stable_key, disposable
                    FROM items
                    WHERE stable_key = ?
                    """,
                    (sample.stable_keys[0],),
                ).fetchone(),
            )
            assert item_row is not None, f"Item sample is missing from the clean database: {sample.identity}"
            required_slot, teach_spell, teach_skill, template_flag, click_effect, disposable = item_row
            assert required_slot is None or isinstance(required_slot, str)
            assert teach_spell is None or isinstance(teach_spell, str)
            assert teach_skill is None or isinstance(teach_skill, str)
            assert isinstance(template_flag, int)
            assert click_effect is None or isinstance(click_effect, str)
            assert isinstance(disposable, int)
            kind = classify_item_kind(
                required_slot=required_slot,
                teach_spell=teach_spell,
                teach_skill=teach_skill,
                template_flag=template_flag,
                click_effect=click_effect,
                disposable=bool(disposable),
            )
            assert item_boundaries == [f"item_kind.{kind.value}"], sample.title


def test_selected_standard_pages_match_the_existing_exhaustive_snapshots() -> None:
    for sample in _standard_samples():
        filename = f"{quote(sample.title, safe='_-.')}.txt"
        generated = GENERATED_DIR / filename
        golden = GOLDEN_WIKI_DIR / filename
        assert golden.is_file(), f"Selected page is absent from the existing exhaustive baseline: {sample.title}"
        assert generated.read_bytes() == golden.read_bytes(), sample.title
