"""Cargo row smoke expectations for the local MediaWiki harness."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class CargoExpectation(NamedTuple):
    """Expected row values in a local Cargo table."""

    page: str
    fields: dict[str, str]


CargoItemExpectation = CargoExpectation
CargoCharacterExpectation = CargoExpectation

CARGO_ITEM_FIELDS = (
    "Page",
    "StableKey",
    "Name",
    "Type",
    "Slot",
    "WeaponType",
    "ItemLevel",
    "Damage",
    "Delay",
    "Armor",
    "HP",
    "Mana",
    "Str",
    "End",
    "Dex",
    "Agi",
    "Intellect",
    "Wis",
    "Cha",
    "Res",
    "MR",
    "PR",
    "ER",
    "VR",
    "BuyValue",
    "SellValue",
    "Image",
    "Classes",
    "TeachesSpellKey",
    "TeachesSkillKey",
    "WeaponProcKey",
    "WeaponProcChance",
    "WandEffectKey",
    "WandProcChance",
    "BowEffectKey",
    "BowProcChance",
    "WornEffectKey",
    "ClickEffectKey",
    "SkillUseKey",
    "AuraKey",
    "Relic",
    "HasProc",
    "HasWornEffect",
)

CARGO_CHARACTER_FIELDS = (
    "Page",
    "StableKey",
    "Name",
    "Type",
    "Zones",
    "Level",
    "FactionKey",
    "HasDrops",
    "HasSpells",
    "MapSelector",
)

CARGO_SPELL_FIELDS = (
    "Page",
    "StableKey",
    "Name",
    "Image",
    "Type",
    "Line",
    "RequiredLevel",
    "ManaCost",
    "CastTimeSeconds",
    "CooldownSeconds",
    "DurationSeconds",
    "CastRange",
    "DamageType",
    "TargetDamage",
    "TargetHealing",
    "CasterHealing",
    "ShieldingAmt",
    "Aggro",
    "SimUsable",
    "SelfOnly",
    "GroupEffect",
    "CrowdControl",
    "GrantInvisibility",
    "CannotInterrupt",
    "Jolt",
    "NoResonate",
    "StatusEffectKey",
    "AddProcKey",
    "PetToSummonKey",
)

CARGO_SKILL_FIELDS = (
    "Page",
    "StableKey",
    "Name",
    "Image",
    "Type",
    "CooldownSeconds",
    "CastRange",
    "SkillPower",
    "PercentDmg",
    "DamageType",
    "Require2H",
    "RequireDualWield",
    "RequireBow",
    "RequireShield",
    "RequireBehind",
    "StanceToUseKey",
    "EffectToApplyKey",
    "CastOnTargetKey",
    "SpawnOnUseKey",
)

CARGO_STANCE_FIELDS = (
    "Page",
    "StableKey",
    "Name",
    "Image",
    "MaxHpMod",
    "DamageMod",
    "ProcRateMod",
    "DamageTakenMod",
    "SelfDamagePerAttack",
    "AggroGenMod",
    "SpellDamageMod",
    "SelfDamagePerCast",
    "LifestealAmount",
    "ResonanceAmount",
    "StopRegen",
)

CARGO_ABILITY_CLASS_FIELDS = (
    "Page",
    "AbilityKey",
    "Class",
    "RequiredLevel",
)
# AbilityClasses is a child table: a page holds one row per (ability, class), so its
# row identity is the ability key plus the Class, not the key alone.
ABILITY_CLASS_KEY = ("AbilityKey", "Class")
# AbilityClasses stores no Page column; the cargoquery API needs the implicit
# _pageName aliased (any underscore-prefixed field must be aliased on wiki.gg).
CARGO_ABILITY_CLASS_QUERY_FIELDS = ("_pageName=Page", "AbilityKey", "Class", "RequiredLevel")

CARGO_DROP_FIELDS = (
    "Page",
    "CharacterKey",
    "ItemKey",
    "DropProbability",
    "IsGuaranteed",
)
# Drops is a child table written on character pages: one row per (character, item),
# so its row identity is the dropping character plus the dropped item (both StableKeys).
# The character column is CharacterKey, not Character: CHARACTER is a reserved SQL word
# the Cargo fork silently rejects (the whole declare no-ops, the table is never created).
DROP_KEY = ("CharacterKey", "ItemKey")
# Drops stores no Page column; alias the implicit _pageName for the cargoquery API.
CARGO_DROP_QUERY_FIELDS = ("_pageName=Page", "CharacterKey", "ItemKey", "DropProbability", "IsGuaranteed")

CARGO_CONTAINER_DROP_FIELDS = (
    "Page",
    "SourceItemKey",
    "DroppedItemKey",
    "DropProbability",
    "IsGuaranteed",
)
# ContainerDrops is a child table written on the source item's page: one row per
# (source item, produced item), both StableKeys.
CONTAINER_DROP_KEY = ("SourceItemKey", "DroppedItemKey")
CARGO_CONTAINER_DROP_QUERY_FIELDS = (
    "_pageName=Page",
    "SourceItemKey",
    "DroppedItemKey",
    "DropProbability",
    "IsGuaranteed",
)

CARGO_OBTAINED_FROM_FIELDS = (
    "Page",
    "ItemKey",
    "SourceType",
    "SourceKey",
    "SourceText",
    "Probability",
    "IsGuaranteed",
    "Quantity",
    "SourceCondition",
    "Origin",
)
# ObtainedFrom is a child table written on the obtained item's page: one row per
# item/source, with SourceCondition included when a source has distinct variants
# such as fishing day versus night.
OBTAINED_FROM_KEY = ("ItemKey", "SourceType", "SourceKey", "SourceCondition")
# ObtainedFrom stores no Page column; alias the implicit _pageName for cargoquery.
CARGO_OBTAINED_FROM_QUERY_FIELDS = (
    "_pageName=Page",
    "ItemKey",
    "SourceType",
    "SourceKey",
    "SourceText",
    "Probability",
    "IsGuaranteed",
    "Quantity",
    "SourceCondition",
    "Origin",
)

CARGO_USED_IN_FIELDS = (
    "Page",
    "ItemKey",
    "UseType",
    "TargetKey",
    "Quantity",
    "Slot",
)
USED_IN_KEY = ("ItemKey", "UseType", "TargetKey")
CARGO_USED_IN_QUERY_FIELDS = (
    "_pageName=Page",
    "ItemKey",
    "UseType",
    "TargetKey",
    "Quantity",
    "Slot",
)


def load_cargo_expectations(
    path: Path,
    fields: tuple[str, ...],
    key_fields: tuple[str, ...] = ("StableKey",),
) -> list[CargoExpectation]:
    """Load expected Cargo rows from a tab-separated file.

    ``key_fields`` are the row-identity columns within a page (default the single
    ``StableKey``; child tables such as AbilityClasses pass a composite).
    """
    if not path.exists():
        return []
    expectations: list[CargoExpectation] = []
    seen_rows: set[tuple[str, ...]] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        # splitlines() already drops the newline; do NOT strip the row itself, or
        # trailing empty tab-separated fields (legitimate empty columns) are lost.
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        values = raw_line.split("\t")
        if len(values) != len(fields):
            raise ValueError(f"{path}: expected {len(fields)} tab-separated fields, got {len(values)}")
        row = dict(zip(fields, values, strict=True))
        page = row.pop("Page")
        row_key = (page, *(row[name] for name in key_fields))
        if row_key in seen_rows:
            raise ValueError(f"{path}: duplicate expected Cargo row {' / '.join(row_key)}")
        seen_rows.add(row_key)
        expectations.append(CargoExpectation(page=page, fields=row))
    return expectations


def load_cargo_item_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo Items rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_ITEM_FIELDS)


def load_cargo_character_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo Characters rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_CHARACTER_FIELDS)


def load_cargo_spell_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo Spells rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_SPELL_FIELDS)


def load_cargo_skill_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo Skills rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_SKILL_FIELDS)


def load_cargo_stance_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo Stances rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_STANCE_FIELDS)


def load_cargo_ability_class_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo AbilityClasses rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_ABILITY_CLASS_FIELDS, ABILITY_CLASS_KEY)


def load_cargo_drop_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo Drops rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_DROP_FIELDS, DROP_KEY)


def load_cargo_container_drop_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo ContainerDrops rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_CONTAINER_DROP_FIELDS, CONTAINER_DROP_KEY)


def load_cargo_used_in_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo UsedIn rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_USED_IN_FIELDS, USED_IN_KEY)


def load_cargo_obtained_from_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo ObtainedFrom rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_OBTAINED_FROM_FIELDS, OBTAINED_FROM_KEY)


def load_absent_pages(path: Path) -> set[str]:
    """Load page names that must not have Cargo rows."""
    if not path.exists():
        return set()
    return {
        line
        for raw_line in path.read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    }


def check_cargo_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    table_label: str,
    absent_pages: set[str] | None = None,
    key_fields: tuple[str, ...] = ("StableKey",),
) -> list[str]:
    rows_by_key: dict[tuple[str, ...], dict[str, str]] = {}
    rows_by_page: dict[str, list[dict[str, str]]] = {}
    duplicate_keys: set[tuple[str, ...]] = set()
    for row in rows:
        page = row.get("Page", "")
        key = (page, *(row.get(name, "") for name in key_fields))
        rows_by_page.setdefault(page, []).append(row)
        if key in rows_by_key:
            duplicate_keys.add(key)
            continue
        rows_by_key[key] = row
    failures: list[str] = []
    absent_pages = absent_pages or set()
    expected_keys = {(expected.page, *(expected.fields[name] for name in key_fields)) for expected in expectations}
    expected_pages = {expected.page for expected in expectations}
    for expected in expectations:
        key = (expected.page, *(expected.fields[name] for name in key_fields))
        row = rows_by_key.get(key)
        if row is None:
            failures.append(f"Cargo {table_label} missing row for {expected.page}")
            continue
        for field, expected_value in expected.fields.items():
            actual_value = row.get(field, "")
            if actual_value != expected_value:
                failures.append(
                    f"Cargo {table_label} row {expected.page} {field}: expected {expected_value}, got {actual_value}"
                )
    for key in sorted(duplicate_keys):
        if key[0] in expected_pages:
            failures.append(f"Cargo {table_label} duplicate row for {' / '.join(key)}")
    for key in sorted(rows_by_key):
        if key[0] in expected_pages and key not in expected_keys:
            failures.append(f"Cargo {table_label} unexpected row for {' / '.join(key)}")
    for page in sorted(page for page in absent_pages if page in rows_by_page):
        failures.append(f"Cargo {table_label} unexpected row for {page}")
    return failures


def check_cargo_item_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "Items", absent_pages)


def check_cargo_character_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "Characters", absent_pages)


def check_cargo_spell_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "Spells", absent_pages)


def check_cargo_skill_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "Skills", absent_pages)


def check_cargo_stance_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "Stances", absent_pages)


def check_cargo_ability_class_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "AbilityClasses", absent_pages, ABILITY_CLASS_KEY)


def check_cargo_drop_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "Drops", absent_pages, DROP_KEY)


def check_cargo_container_drop_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "ContainerDrops", absent_pages, CONTAINER_DROP_KEY)


def check_cargo_obtained_from_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "ObtainedFrom", absent_pages, OBTAINED_FROM_KEY)


def check_cargo_used_in_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "UsedIn", absent_pages, USED_IN_KEY)
