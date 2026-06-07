#!/usr/bin/env python3
"""Run local MediaWiki parse and Cargo smoke tests."""

from __future__ import annotations

import argparse
from pathlib import Path

from smoke.cargo import (
    load_absent_pages,
    load_cargo_ability_class_expectations,
    load_cargo_character_expectations,
    load_cargo_container_drop_expectations,
    load_cargo_drop_expectations,
    load_cargo_item_expectations,
    load_cargo_skill_expectations,
    load_cargo_spell_expectations,
    load_cargo_stance_expectations,
)
from smoke.mediawiki import api_url
from smoke.render import load_expectations
from smoke.runner import run_smoke_checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088", help="Local wiki base URL")
    parser.add_argument(
        "--expectations",
        type=Path,
        default=Path("wiki-dev/fixtures/smoke.tsv"),
        help="Tab-separated title/expected text file",
    )
    parser.add_argument(
        "--cargo-items",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_items.tsv"),
        help="Tab-separated Cargo Items smoke expectations",
    )
    parser.add_argument(
        "--cargo-absent",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_absent.tsv"),
        help="Page titles that must not have Cargo Items rows",
    )
    parser.add_argument(
        "--cargo-characters",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_characters.tsv"),
        help="Tab-separated Cargo Characters smoke expectations",
    )
    parser.add_argument(
        "--cargo-spells",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_spells.tsv"),
        help="Tab-separated Cargo Spells smoke expectations",
    )
    parser.add_argument(
        "--cargo-skills",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_skills.tsv"),
        help="Tab-separated Cargo Skills smoke expectations",
    )
    parser.add_argument(
        "--cargo-stances",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_stances.tsv"),
        help="Tab-separated Cargo Stances smoke expectations",
    )
    parser.add_argument(
        "--cargo-ability-classes",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_ability_classes.tsv"),
        help="Tab-separated Cargo AbilityClasses smoke expectations",
    )
    parser.add_argument(
        "--cargo-drops",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_drops.tsv"),
        help="Tab-separated Cargo Drops smoke expectations",
    )
    parser.add_argument(
        "--cargo-container-drops",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_container_drops.tsv"),
        help="Tab-separated Cargo ContainerDrops smoke expectations",
    )
    args = parser.parse_args()

    expectations = load_expectations(args.expectations)
    cargo_item_expectations = load_cargo_item_expectations(args.cargo_items)
    cargo_character_expectations = load_cargo_character_expectations(args.cargo_characters)
    cargo_spell_expectations = load_cargo_spell_expectations(args.cargo_spells)
    cargo_skill_expectations = load_cargo_skill_expectations(args.cargo_skills)
    cargo_stance_expectations = load_cargo_stance_expectations(args.cargo_stances)
    cargo_ability_class_expectations = load_cargo_ability_class_expectations(args.cargo_ability_classes)
    cargo_drop_expectations = load_cargo_drop_expectations(args.cargo_drops)
    cargo_container_drop_expectations = load_cargo_container_drop_expectations(args.cargo_container_drops)
    cargo_absent_pages = load_absent_pages(args.cargo_absent)
    if not expectations and not cargo_item_expectations and not cargo_character_expectations:
        raise SystemExit(
            f"No smoke expectations found in {args.expectations}, {args.cargo_items}, or {args.cargo_characters}"
        )

    failures = run_smoke_checks(
        endpoint=api_url(args.base_url),
        expectations=expectations,
        cargo_item_expectations=cargo_item_expectations,
        cargo_character_expectations=cargo_character_expectations,
        cargo_spell_expectations=cargo_spell_expectations,
        cargo_skill_expectations=cargo_skill_expectations,
        cargo_stance_expectations=cargo_stance_expectations,
        cargo_ability_class_expectations=cargo_ability_class_expectations,
        cargo_drop_expectations=cargo_drop_expectations,
        cargo_container_drop_expectations=cargo_container_drop_expectations,
        cargo_absent_pages=cargo_absent_pages,
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
