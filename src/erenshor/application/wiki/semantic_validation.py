# ruff: noqa: PLR0911
"""Pure semantic validation for generated wiki pages.

The validator intentionally accepts ordinary in-memory mappings.  Generation and
storage adapters can assemble those mappings at their boundaries, while this
module owns the contracts that make a generated corpus safe to publish.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypedDict, cast

from erenshor.application.wiki.generators.field_preservation import (
    DEFAULT_PRESERVATION_RULES,
    FieldPreservationHandler,
)
from erenshor.application.wiki.generators.page_normalizer import PageNormalizer
from erenshor.application.wiki.services.storage import PageMetadata, WikiStorage
from erenshor.application.wiki_deploy.link_audit import audit_links
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
from erenshor.infrastructure.wiki.template_parser import TemplateParser

INVARIANT_CODES = (
    "title_inventory",
    "parseability",
    "required_schema",
    "stable_identity",
    "generated_manual_ownership",
    "semantic_links",
    "manual_overrides",
    "categories",
)

# These are deliberately declarative copies of the fields emitted by the
# corresponding Jinja templates.  A field is required to be present, but an
# empty value is valid: the templates emit empty parameters for absent game
# data and Cargo relies on that stable shape.
_REQUIRED_TEMPLATE_FIELDS_RAW: Mapping[str, list[str]] = MappingProxyType(
    {
        "Item": [
            "title",
            "stablekey",
            "type",
            "vendorsource",
            "source",
            "othersource",
            "questsource",
            "relatedquest",
            "craftsource",
            "componentfor",
            "buy",
            "sell",
            "taughtspell",
            "taughtskill",
            "guaranteeddrops",
            "droprates",
        ],
        "Character": [
            "name",
            "image",
            "imagecaption",
            "type",
            "faction",
            "factionChange",
            "zones",
            "coordinates",
            "spawnchance",
            "spawntype",
            "respawn",
            "guaranteeddrops",
            "droprates",
            "level",
            "levelmodmin",
            "levelmodmax",
            "levelvariancemin",
            "levelvariancemax",
            "xpmultiplier",
            "health",
            "mana",
            "ac",
            "strength",
            "endurance",
            "dexterity",
            "agility",
            "intelligence",
            "wisdom",
            "charisma",
            "magic",
            "poison",
            "elemental",
            "void",
            "spells",
        ],
        "Ability": [
            "title",
            "image",
            "imagecaption",
            "description",
            "type",
            "line",
            "classes",
            "required_level",
            "manacost",
            "aggro",
            "is_taunt",
            "casttime",
            "cooldown",
            "duration",
            "duration_in_ticks",
            "has_unstable_duration",
            "is_instant_effect",
            "is_reap_and_renew",
            "is_sim_usable",
            "range",
            "max_level_target",
            "is_self_only",
            "is_group_effect",
            "is_applied_to_caster",
            "effects",
            "damage_type",
            "resist_modifier",
            "target_damage",
            "target_healing",
            "caster_healing",
            "shield_amount",
            "pet_to_summon",
            "status_effect",
            "add_proc",
            "add_proc_chance",
            "has_lifetap",
            "lifesteal",
            "damage_shield",
            "percent_mana_restoration",
            "bleed_damage_percent",
            "special_descriptor",
            "hp",
            "ac",
            "mana",
            "str",
            "dex",
            "end",
            "agi",
            "wis",
            "int",
            "cha",
            "mr",
            "er",
            "vr",
            "pr",
            "haste",
            "resonance",
            "movement_speed",
            "atk_roll_modifier",
            "xp_bonus",
            "is_root",
            "is_stun",
            "is_charm",
            "is_broken_on_damage",
            "is_fear",
            "inflict_on_self",
            "itemswitheffect",
            "source",
            "used_by",
        ],
        "Stance": [
            "title",
            "image",
            "description",
            "switch_message",
            "max_hp_mod",
            "damage_mod",
            "damage_taken_mod",
            "proc_rate_mod",
            "aggro_gen_mod",
            "spell_damage_mod",
            "self_damage_per_attack",
            "self_damage_per_cast",
            "lifesteal_amount",
            "resonance_amount",
            "stop_regen",
            "activated_by",
        ],
        "Zone": ["title", "image", "imagecaption", "type", "level", "maplink", "connects"],
        "ItemTooltip": [
            "kind",
            "image",
            "name",
            "slot",
            "type",
            "relic",
            "str",
            "end",
            "dex",
            "agi",
            "int",
            "wis",
            "cha",
            "res",
            "damage",
            "delay",
            "range",
            "health",
            "mana",
            "armor",
            "magic",
            "poison",
            "elemental",
            "void",
            "description",
            "arcanist",
            "duelist",
            "druid",
            "paladin",
            "reaver",
            "stormcaller",
            "proc_style",
            "proc_chance",
            "proc_spell_icon",
            "proc_spell_name",
            "proc_spell_level",
            "proc_spell_duration_ticks",
            "proc_spell_type",
            "proc_spell_line",
            "proc_target_damage",
            "proc_target_healing",
            "proc_shielding_amt",
            "proc_damage_type",
            "proc_cast_time",
            "proc_cooldown",
            "proc_spell_range",
            "proc_lifetap",
            "proc_group_effect",
            "proc_stun_target",
            "proc_charm_target",
            "proc_root_target",
            "proc_taunt_spell",
            "proc_aggro",
            "proc_status_effect_name",
            "proc_hp",
            "proc_ac",
            "proc_mana",
            "proc_str",
            "proc_dex",
            "proc_end",
            "proc_agi",
            "proc_wis",
            "proc_int",
            "proc_cha",
            "proc_mr",
            "proc_er",
            "proc_pr",
            "proc_vr",
            "proc_movement_speed",
            "proc_damage_shield",
            "proc_haste",
            "proc_percent_lifesteal",
            "proc_atk_roll_modifier",
            "proc_resonate_chance",
            "proc_add_proc_name",
            "proc_add_proc_chance",
            "proc_special_descriptor",
            "proc_xp_bonus",
        ],
        "Item/Weapon": [
            "image",
            "name",
            "type",
            "relic",
            "tier",
            "str",
            "end",
            "dex",
            "agi",
            "int",
            "wis",
            "cha",
            "res",
            "damage",
            "delay",
            "range",
            "health",
            "mana",
            "armor",
            "magic",
            "poison",
            "elemental",
            "void",
            "description",
            "arcanist",
            "duelist",
            "druid",
            "paladin",
            "reaver",
            "stormcaller",
            "proc_style",
            "proc_chance",
            "proc_spell_icon",
            "proc_spell_name",
            "proc_spell_level",
            "proc_spell_duration_ticks",
            "proc_spell_type",
            "proc_spell_line",
            "proc_target_damage",
            "proc_target_healing",
            "proc_shielding_amt",
            "proc_damage_type",
            "proc_cast_time",
            "proc_cooldown",
            "proc_spell_range",
            "proc_lifetap",
            "proc_group_effect",
            "proc_stun_target",
            "proc_charm_target",
            "proc_root_target",
            "proc_taunt_spell",
            "proc_aggro",
            "proc_status_effect_name",
            "proc_hp",
            "proc_ac",
            "proc_mana",
            "proc_str",
            "proc_dex",
            "proc_end",
            "proc_agi",
            "proc_wis",
            "proc_int",
            "proc_cha",
            "proc_mr",
            "proc_er",
            "proc_pr",
            "proc_vr",
            "proc_movement_speed",
            "proc_damage_shield",
            "proc_haste",
            "proc_percent_lifesteal",
            "proc_atk_roll_modifier",
            "proc_resonate_chance",
            "proc_add_proc_name",
            "proc_add_proc_chance",
            "proc_special_descriptor",
            "proc_xp_bonus",
        ],
        "Item/Armor": [
            "image",
            "name",
            "slot",
            "relic",
            "tier",
            "str",
            "end",
            "dex",
            "agi",
            "int",
            "wis",
            "cha",
            "res",
            "health",
            "mana",
            "armor",
            "magic",
            "poison",
            "elemental",
            "void",
            "description",
            "arcanist",
            "duelist",
            "druid",
            "paladin",
            "reaver",
            "stormcaller",
            "proc_style",
            "proc_chance",
            "proc_spell_icon",
            "proc_spell_name",
            "proc_spell_level",
            "proc_spell_duration_ticks",
            "proc_spell_type",
            "proc_spell_line",
            "proc_target_damage",
            "proc_target_healing",
            "proc_shielding_amt",
            "proc_damage_type",
            "proc_cast_time",
            "proc_cooldown",
            "proc_spell_range",
            "proc_lifetap",
            "proc_group_effect",
            "proc_stun_target",
            "proc_charm_target",
            "proc_root_target",
            "proc_taunt_spell",
            "proc_aggro",
            "proc_status_effect_name",
            "proc_hp",
            "proc_ac",
            "proc_mana",
            "proc_str",
            "proc_dex",
            "proc_end",
            "proc_agi",
            "proc_wis",
            "proc_int",
            "proc_cha",
            "proc_mr",
            "proc_er",
            "proc_pr",
            "proc_vr",
            "proc_movement_speed",
            "proc_damage_shield",
            "proc_haste",
            "proc_percent_lifesteal",
            "proc_atk_roll_modifier",
            "proc_resonate_chance",
            "proc_add_proc_name",
            "proc_add_proc_chance",
            "proc_special_descriptor",
            "proc_xp_bonus",
        ],
        "Item/Charm": [
            "image",
            "name",
            "tier",
            "strscaling",
            "endscaling",
            "dexscaling",
            "agiscaling",
            "intscaling",
            "wisscaling",
            "chascaling",
            "resistscaling",
            "mitigationscaling",
            "arcanist",
            "duelist",
            "druid",
            "paladin",
            "reaver",
            "stormcaller",
        ],
        "Item/Consumable": [
            "image",
            "name",
            "description",
            "disposable",
            "effect_spell_icon",
            "effect_spell_name",
            "effect_spell_level",
            "effect_spell_duration_ticks",
            "effect_spell_type",
            "effect_spell_line",
            "effect_target_damage",
            "effect_target_healing",
            "effect_shielding_amt",
            "effect_damage_type",
            "effect_cast_time",
            "effect_cooldown",
            "effect_spell_range",
            "effect_lifetap",
            "effect_group_effect",
            "effect_stun_target",
            "effect_charm_target",
            "effect_root_target",
            "effect_taunt_spell",
            "effect_aggro",
            "effect_status_effect_name",
            "effect_hp",
            "effect_ac",
            "effect_mana",
            "effect_str",
            "effect_dex",
            "effect_end",
            "effect_agi",
            "effect_wis",
            "effect_int",
            "effect_cha",
            "effect_mr",
            "effect_er",
            "effect_pr",
            "effect_vr",
            "effect_movement_speed",
            "effect_damage_shield",
            "effect_haste",
            "effect_percent_lifesteal",
            "effect_atk_roll_modifier",
            "effect_resonate_chance",
            "effect_add_proc_name",
            "effect_add_proc_chance",
            "effect_special_descriptor",
            "effect_xp_bonus",
        ],
        "Item/General": [
            "image",
            "name",
            "description",
            "value",
            "stack_size",
            "disposable",
            "effect_style",
            "effect_spell_icon",
            "effect_spell_name",
            "effect_spell_level",
            "effect_spell_duration_ticks",
            "effect_spell_type",
            "effect_spell_line",
            "effect_target_damage",
            "effect_target_healing",
            "effect_damage_type",
            "effect_cast_time",
            "effect_cooldown",
            "effect_spell_range",
            "effect_lifetap",
            "effect_group_effect",
            "effect_stun_target",
            "effect_charm_target",
            "effect_root_target",
            "effect_taunt_spell",
            "effect_aggro",
            "effect_status_effect_name",
            "effect_hp",
            "effect_ac",
            "effect_mana",
            "effect_str",
            "effect_dex",
            "effect_end",
            "effect_agi",
            "effect_wis",
            "effect_int",
            "effect_cha",
            "effect_mr",
            "effect_er",
            "effect_pr",
            "effect_vr",
            "effect_movement_speed",
            "effect_damage_shield",
            "effect_haste",
            "effect_percent_lifesteal",
            "effect_atk_roll_modifier",
            "effect_resonate_chance",
            "effect_add_proc_name",
            "effect_add_proc_chance",
            "effect_special_descriptor",
        ],
        "Item/Aura": [
            "image",
            "name",
            "description",
            "aura_spell_icon",
            "aura_spell_name",
            "aura_spell_level",
            "aura_spell_duration_ticks",
            "aura_spell_type",
            "aura_spell_line",
            "aura_target_damage",
            "aura_target_healing",
            "aura_shielding_amt",
            "aura_damage_type",
            "aura_cast_time",
            "aura_cooldown",
            "aura_spell_range",
            "aura_lifetap",
            "aura_group_effect",
            "aura_stun_target",
            "aura_charm_target",
            "aura_root_target",
            "aura_taunt_spell",
            "aura_aggro",
            "aura_status_effect_name",
            "aura_hp",
            "aura_ac",
            "aura_mana",
            "aura_str",
            "aura_dex",
            "aura_end",
            "aura_agi",
            "aura_wis",
            "aura_int",
            "aura_cha",
            "aura_mr",
            "aura_er",
            "aura_pr",
            "aura_vr",
            "aura_movement_speed",
            "aura_damage_shield",
            "aura_haste",
            "aura_percent_lifesteal",
            "aura_atk_roll_modifier",
            "aura_resonate_chance",
            "aura_add_proc_name",
            "aura_add_proc_chance",
            "aura_special_descriptor",
        ],
        "Item/Mold": ["image", "name", "description", "ingredients", "rewards", "station"],
        "Item/SkillBook": [
            "image",
            "name",
            "duelist_level",
            "druid_level",
            "arcanist_level",
            "paladin_level",
            "stormcaller_level",
            "reaver_level",
            "skill_type",
            "skill_desc",
            "simplayers_autolearn",
        ],
        "Item/SpellScroll": [
            "image",
            "name",
            "arcanist_level",
            "druid_level",
            "duelist_level",
            "paladin_level",
            "stormcaller_level",
            "reaver_level",
            "mana_cost",
            "spell_type",
            "spell_desc",
        ],
        "SpellTooltip": ["stablekey"],
        "SkillTooltip": ["stablekey"],
        "StanceTooltip": ["stablekey"],
    }
)

# Freeze each field sequence as well as the outer mapping.
REQUIRED_TEMPLATE_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {name: tuple(fields) for name, fields in _REQUIRED_TEMPLATE_FIELDS_RAW.items()}
)

ROOT_TEMPLATES = frozenset(("Item", "Character", "Ability", "Stance", "Zone"))
ITEM_COMPANIONS = frozenset(name for name in REQUIRED_TEMPLATE_FIELDS if name.startswith("Item/")) | {"ItemTooltip"}
ABILITY_COMPANIONS = frozenset(("SpellTooltip", "SkillTooltip", "StanceTooltip"))
SEMANTIC_LINK_TEMPLATES = frozenset(
    ("ItemLink", "AbilityLink", "CharacterLink", "QuestLink", "ZoneLink", "FactionLink", "ClassLink")
)
GENERATED_TEMPLATES = ROOT_TEMPLATES | ITEM_COMPANIONS | ABILITY_COMPANIONS | {"Zone Navbox"}

_ITEM_COMPANION_BY_SUBTYPE: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "weapon": frozenset(("ItemTooltip", "Item/Weapon")),
        "armor": frozenset(("ItemTooltip", "Item/Armor")),
        "charm": frozenset(("Item/Charm",)),
        "aura": frozenset(("Item/Aura",)),
        "spellscroll": frozenset(("Item/SpellScroll",)),
        "skillbook": frozenset(("Item/SkillBook",)),
        "consumable": frozenset(("Item/Consumable",)),
        "mold": frozenset(("Item/Mold",)),
        "general": frozenset(("Item/General",)),
    }
)


@dataclass(frozen=True, slots=True)
class WikiPageExpectation:
    """Explicit per-page facts supplied by an integration boundary.

    ``metadata`` is the normal source of stable keys.  ``ownership`` may
    optionally provide stable catalog keys (or generated-family names for
    synthetic pages), and ``schema_kind`` is an override for synthetic pages
    and the two table-only overview families; normal entity pages infer both
    from the catalog entries named by ``metadata.stable_keys``.
    """

    title: str
    metadata: PageMetadata | None = None
    fetched_content: str | None = None
    expected_categories: tuple[str, ...] | None = None
    ownership: tuple[str, ...] = ()
    schema_kind: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "expected_categories", None if self.expected_categories is None else tuple(self.expected_categories)
        )
        object.__setattr__(self, "ownership", tuple(self.ownership))


def derive_corpus_expectations(storage: WikiStorage, page_titles: Collection[str]) -> dict[str, WikiPageExpectation]:
    """Build metadata, fetched-content, and singleton-overview facts for a stored corpus."""
    expectations: dict[str, WikiPageExpectation] = {}
    for title in page_titles:
        metadata = storage.get_metadata_by_title(title)
        if metadata is None:
            raise ValueError(f"Generated wiki metadata missing for {title!r}")
        schema_kind = f"{title.casefold()}_overview" if title in {"Armor", "Weapons"} else None
        ownership = (schema_kind,) if schema_kind is not None else ()
        expectations[title] = WikiPageExpectation(
            title=title,
            metadata=metadata,
            fetched_content=storage.read_fetched_by_title(title),
            ownership=ownership,
            schema_kind=schema_kind,
        )
    return expectations


@dataclass(frozen=True, slots=True)
class PageContract:
    """Derived ownership/schema facts, useful to integration callers."""

    page: str
    schema_kind: str
    stable_keys: tuple[str, ...]
    generated_templates: tuple[str, ...]
    ownership: tuple[str, ...] = ()


class SemanticManifestEntry(TypedDict):
    title: str
    stable_keys: list[str]
    schema: str
    generated_templates: list[str]
    categories: list[str]
    semantic_links: list[str]


class SemanticManifest(TypedDict):
    version: int
    pages: list[SemanticManifestEntry]


@dataclass(frozen=True, slots=True)
class SemanticFinding:
    """One blocking semantic invariant violation."""

    code: str
    page: str
    detail: str


class SemanticValidationError(ValueError):
    """Raised by :meth:`SemanticValidationReport.raise_for_errors`."""

    def __init__(self, report: SemanticValidationReport) -> None:
        self.report = report
        super().__init__(report.format_errors())


@dataclass(frozen=True, slots=True)
class SemanticValidationReport:
    """Deterministic validation results."""

    findings: tuple[SemanticFinding, ...] = ()

    @property
    def has_errors(self) -> bool:
        return bool(self.findings)

    def format_errors(self) -> str:
        return "\n".join(f"[{f.code}] {f.page}: {f.detail}" for f in self.findings)

    def raise_for_errors(self) -> SemanticValidationReport:
        if self.has_errors:
            raise SemanticValidationError(self)
        return self


@dataclass(frozen=True, slots=True)
class GeneratedManualOwnershipEntry:
    """Ownership classification for one selected generated-corpus page.

    ``generated`` means the page has a generated template family (or one of
    the generated overview schemas).  ``manual`` means no generated family is
    present.  ``invalid`` is reserved for pages with semantic-validation
    findings and is never folded into the manual count.
    """

    page: str
    ownership: str
    schema_kind: str
    stable_keys: tuple[str, ...]
    generated_templates: tuple[str, ...]
    owned_templates: tuple[str, ...]
    findings: tuple[SemanticFinding, ...] = ()

    def __post_init__(self) -> None:
        if self.ownership not in {"generated", "manual", "invalid"}:
            raise ValueError(f"Unknown page ownership: {self.ownership!r}")
        object.__setattr__(self, "stable_keys", tuple(self.stable_keys))
        object.__setattr__(self, "generated_templates", tuple(self.generated_templates))
        object.__setattr__(self, "owned_templates", tuple(self.owned_templates))
        object.__setattr__(self, "findings", tuple(self.findings))

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible page record."""
        return {
            "page": self.page,
            "ownership": self.ownership,
            "schema": self.schema_kind,
            "stable_keys": list(self.stable_keys),
            "generated_templates": list(self.generated_templates),
            "owned_templates": list(self.owned_templates),
            "findings": [
                {"code": finding.code, "page": finding.page, "detail": finding.detail} for finding in self.findings
            ],
        }


@dataclass(frozen=True, slots=True)
class GeneratedManualOwnershipReport:
    """Deterministic generated/manual ownership results for selected pages."""

    entries: tuple[GeneratedManualOwnershipEntry, ...] = ()

    def __post_init__(self) -> None:
        entries = tuple(sorted(self.entries, key=lambda entry: (entry.page.casefold(), entry.page)))
        if len({entry.page for entry in entries}) != len(entries):
            raise ValueError("Ownership report contains duplicate page entries")
        object.__setattr__(self, "entries", entries)

    @property
    def total_pages(self) -> int:
        return len(self.entries)

    @property
    def generated_pages(self) -> int:
        return sum(entry.ownership == "generated" for entry in self.entries)

    @property
    def manual_pages(self) -> int:
        return sum(entry.ownership == "manual" for entry in self.entries)

    @property
    def invalid_pages(self) -> int:
        return sum(entry.ownership == "invalid" for entry in self.entries)

    @property
    def findings(self) -> tuple[SemanticFinding, ...]:
        return tuple(finding for entry in self.entries for finding in entry.findings)

    @property
    def has_errors(self) -> bool:
        return bool(self.findings)

    def to_dict(self) -> dict[str, object]:
        """Return stable counts and complete per-page ownership records."""
        return {
            "version": 1,
            "counts": {
                "total": self.total_pages,
                "generated": self.generated_pages,
                "manual": self.manual_pages,
                "invalid": self.invalid_pages,
            },
            "pages": [entry.to_dict() for entry in self.entries],
        }


def build_generated_manual_ownership_report(
    contracts: Collection[PageContract],
    *,
    validation_report: SemanticValidationReport | None = None,
) -> GeneratedManualOwnershipReport:
    """Classify selected pages from existing contracts and validation findings.

    This boundary deliberately consumes :class:`PageContract` values produced
    by semantic validation.  It does not read files, parse templates, or infer
    ownership a second time.  Any finding for a selected page makes that page
    ``invalid`` so validation failures cannot inflate the manual count.
    """
    findings_by_page: dict[str, list[SemanticFinding]] = {}
    if validation_report is not None:
        for finding in validation_report.findings:
            findings_by_page.setdefault(finding.page, []).append(finding)

    entries: list[GeneratedManualOwnershipEntry] = []
    seen_pages: set[str] = set()
    for contract in contracts:
        if contract.page in seen_pages:
            raise ValueError(f"Ownership report contains duplicate page {contract.page!r}")
        seen_pages.add(contract.page)
        page_findings = tuple(
            sorted(
                findings_by_page.get(contract.page, ()),
                key=lambda finding: (finding.page.casefold(), finding.page, finding.code, finding.detail),
            )
        )
        generated = bool(contract.generated_templates or contract.ownership)
        if contract.schema_kind in {"armor_overview", "weapons_overview"}:
            generated = True
        entries.append(
            GeneratedManualOwnershipEntry(
                page=contract.page,
                ownership="invalid" if page_findings else ("generated" if generated else "manual"),
                schema_kind=contract.schema_kind,
                stable_keys=contract.stable_keys,
                generated_templates=contract.generated_templates,
                owned_templates=contract.ownership,
                findings=page_findings,
            )
        )
    unknown_finding_pages = set(findings_by_page) - seen_pages
    if unknown_finding_pages:
        pages = ", ".join(sorted(unknown_finding_pages, key=lambda page: (page.casefold(), page)))
        raise ValueError(f"Validation report contains findings for unselected pages: {pages}")
    return GeneratedManualOwnershipReport(tuple(entries))


@dataclass(frozen=True, slots=True)
class _ParsedPage:
    title: str
    content: str
    templates: tuple[Any, ...]
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Catalog:
    by_key: Mapping[str, LinkCatalogEntry]


class _Findings:
    def __init__(self) -> None:
        self.items: list[SemanticFinding] = []

    def add(self, code: str, page: str, detail: str) -> None:
        self.items.append(SemanticFinding(code, page, detail))

    def report(self) -> SemanticValidationReport:
        return SemanticValidationReport(
            tuple(sorted(self.items, key=lambda f: (f.page.casefold(), f.page, f.code, f.detail)))
        )


def _title_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ").strip()).casefold()


def _name(template: Any) -> str:
    return str(template.name).strip()


def _canonical_template_name(value: str) -> str:
    return value.casefold().replace(" ", "")


def _as_entry(value: LinkCatalogEntry | Mapping[str, object]) -> LinkCatalogEntry:
    if isinstance(value, LinkCatalogEntry):
        return value
    return LinkCatalogEntry(
        key=str(value["key"]),
        kind=str(value["kind"]),
        subtype=None if value.get("subtype") is None else str(value["subtype"]),
        name=str(value["name"]),
        page=str(value["page"]),
        image=None if value.get("image") is None else str(value["image"]),
    )


def _catalog(entries: Sequence[LinkCatalogEntry | Mapping[str, object]]) -> _Catalog:
    values = tuple(_as_entry(entry) for entry in entries)
    by_key: dict[str, LinkCatalogEntry] = {}
    for entry in values:
        if entry.key in by_key:
            # Keep validation pure; the duplicate is reported as identity data
            # rather than allowing a later record to silently win.
            continue
        by_key[entry.key] = entry
    return _Catalog(MappingProxyType(by_key))


def _metadata_for(
    title: str,
    value: WikiPageExpectation | PageMetadata | Mapping[str, object] | None,
) -> WikiPageExpectation:
    if isinstance(value, WikiPageExpectation):
        return value
    if isinstance(value, PageMetadata):
        return WikiPageExpectation(title=title, metadata=value)
    if isinstance(value, Mapping):
        raw_meta = value.get("metadata")
        metadata = raw_meta if isinstance(raw_meta, PageMetadata) else None
        categories = value.get("expected_categories")
        ownership = value.get("ownership", ())
        schema_kind = value.get("schema_kind")
        fetched = value.get("fetched_content")
        return WikiPageExpectation(
            title=str(value.get("title", title)),
            metadata=metadata,
            fetched_content=None if fetched is None else str(fetched),
            expected_categories=None
            if categories is None
            else tuple(str(v) for v in cast("Iterable[object]", categories)),
            ownership=tuple(str(v) for v in cast("Iterable[object]", ownership)),
            schema_kind=None if schema_kind is None else str(schema_kind),
        )
    return WikiPageExpectation(title=title)


def _top_level_templates(content: str) -> tuple[Any, ...]:
    parser = TemplateParser()
    code = parser.parse(content)
    return tuple(code.filter_templates(recursive=True))


def _parse_page(title: str, content: str) -> _ParsedPage:
    templates = _top_level_templates(content)
    return _ParsedPage(title, content, templates, tuple(_name(template) for template in templates))


def _balanced_delimiters(content: str) -> str | None:
    pairs = {"{{": "}}", "[[": "]]"}
    closing = set(pairs.values())
    stack: list[str] = []
    index = 0
    while index < len(content):
        token = content[index : index + 2]
        if token in pairs:
            stack.append(token)
            index += 2
            continue
        if token in closing:
            if not stack or pairs[stack[-1]] != token:
                return f"unexpected closing delimiter {token!r} at offset {index}"
            stack.pop()
            index += 2
            continue
        index += 1
    if stack:
        return f"unclosed delimiter {stack[-1]!r}"
    return None


def _params(parser: TemplateParser, template: Any) -> dict[str, str]:
    return parser.get_params(template)


def _missing_fields(parser: TemplateParser, template: Any, template_name: str) -> tuple[str, ...]:
    params = _params(parser, template)
    required = REQUIRED_TEMPLATE_FIELDS.get(template_name)
    if required is None:
        return ()
    return tuple(field for field in required if field not in params)


def _keyed_value(parser: TemplateParser, template: Any) -> str | None:
    value = parser.get_param(template, "stablekey")
    return value if value is not None and value.strip() else None


def _stable_keys(expectation: WikiPageExpectation) -> tuple[str, ...]:
    if expectation.metadata is None:
        return ()
    return tuple(expectation.metadata.stable_keys)


def _schema_from_names(
    names: Sequence[str], explicit: str | None, expected_keys: Sequence[str], catalog: _Catalog
) -> str:
    if explicit:
        return explicit.casefold().replace(" ", "_")
    families = {
        family
        for family, root in (
            ("item", "Item"),
            ("character", "Character"),
            ("ability", "Ability"),
            ("stance", "Stance"),
            ("zone", "Zone"),
        )
        if root in names
    }
    if len(families) > 1:
        return "multi"
    if families:
        return next(iter(families))
    if "{|" in names:  # reserved for callers that pass a synthetic marker
        return "overview"
    kinds = {catalog.by_key[key].kind for key in expected_keys if key in catalog.by_key}
    if len(kinds) > 1:
        return "multi"
    if kinds == {"item"}:
        return "item"
    if kinds == {"character"}:
        return "character"
    if kinds == {"ability"}:
        return "ability"
    if kinds == {"zone"}:
        return "zone"
    return "overview" if not expected_keys else "entity"


def derive_page_contract(
    page: str,
    content: str,
    metadata: PageMetadata | None = None,
    catalog_entries: Sequence[LinkCatalogEntry | Mapping[str, object]] = (),
    *,
    schema_kind: str | None = None,
) -> PageContract:
    """Derive page schema and generated families without integration dispatch."""
    catalog = _catalog(catalog_entries)
    keys = _stable_keys(WikiPageExpectation(page, metadata))
    parsed = _parse_page(page, content)
    schema = _schema_from_names(parsed.names, schema_kind, keys, catalog)
    generated = tuple(
        sorted({name for name in parsed.names if name in GENERATED_TEMPLATES}, key=lambda n: (n.casefold(), n))
    )
    expectation = WikiPageExpectation(page, metadata, schema_kind=schema_kind)
    allowed = _expected_templates(expectation, parsed, catalog, schema)
    ownership = tuple(sorted(allowed or set(generated), key=lambda n: (n.casefold(), n)))
    return PageContract(page, schema, keys, generated, ownership)


def _expected_templates(
    expectation: WikiPageExpectation,
    parsed: _ParsedPage,
    catalog: _Catalog,
    schema: str,
) -> set[str]:
    values: set[str] = set()
    if expectation.ownership:
        values = {value.casefold() for value in expectation.ownership}
        if any(value in catalog.by_key for value in expectation.ownership):
            keys = [value for value in expectation.ownership if value in catalog.by_key]
        else:
            keys = []
    else:
        keys = list(_stable_keys(expectation))
    allowed: set[str] = set()
    for key in keys:
        entry = catalog.by_key.get(key)
        if entry is None:
            continue
        if entry.kind == "item":
            allowed.add("Item")
            allowed.update(_ITEM_COMPANION_BY_SUBTYPE.get((entry.subtype or "general").casefold(), ITEM_COMPANIONS))
        elif entry.kind == "ability":
            if key.startswith("stance:"):
                allowed.update(("Stance", "StanceTooltip"))
            else:
                allowed.update(("Ability", "SpellTooltip" if key.startswith("spell:") else "SkillTooltip"))
        elif entry.kind == "character":
            allowed.add("Character")
        elif entry.kind == "zone":
            allowed.update(("Zone", "Zone Navbox"))
        elif entry.kind == "class":
            pass
    if expectation.ownership and not keys:
        for value in values:
            if value == "item":
                allowed.update({"Item", *ITEM_COMPANIONS})
            elif value == "ability":
                allowed.update({"Ability", *ABILITY_COMPANIONS})
            elif value == "stance":
                allowed.update({"Stance", "StanceTooltip"})
            elif value == "character":
                allowed.add("Character")
            elif value == "zone":
                allowed.update(("Zone", "Zone Navbox"))
            elif value in {"overview", "wikitable"}:
                continue
            else:
                allowed.update({name for name in GENERATED_TEMPLATES if name.casefold() == value})
    if schema == "stance":
        allowed.update(("Stance", "StanceTooltip"))
    if schema in {"armor_overview", "weapons_overview", "overview"}:
        return set()
    return allowed


def _expected_item_companion(key: str | None, catalog: _Catalog) -> set[str]:
    if key is None:
        return set(ITEM_COMPANIONS)
    entry = catalog.by_key.get(key)
    if entry is None or entry.kind != "item":
        return set(ITEM_COMPANIONS)
    return set(_ITEM_COMPANION_BY_SUBTYPE.get((entry.subtype or "general").casefold(), ITEM_COMPANIONS))


def _entry_identity(
    findings: _Findings, page: str, key: str, expected_kind: str, catalog: _Catalog
) -> LinkCatalogEntry | None:
    entry = catalog.by_key.get(key)
    if entry is None:
        findings.add("stable_identity", page, f"metadata stable key {key!r} is absent from the link catalog")
        return None
    if entry.kind != expected_kind:
        findings.add(
            "stable_identity", page, f"stable key {key!r} has catalog kind {entry.kind!r}, expected {expected_kind!r}"
        )
    if _title_key(entry.page) != _title_key(page):
        findings.add("stable_identity", page, f"stable key {key!r} points to page {entry.page!r}, not {page!r}")
    return entry


def _validate_structure(
    findings: _Findings,
    parsed: _ParsedPage,
    expectation: WikiPageExpectation,
    catalog: _Catalog,
    schema: str,
) -> None:
    parser = TemplateParser()
    names = parsed.names
    templates = parsed.templates

    if schema == "multi":
        keys = _stable_keys(expectation)
        owned_families = {
            "item"
            if key.startswith("item:")
            else "character"
            if key.startswith("character:")
            else "stance"
            if key.startswith("stance:")
            else "ability"
            if key.startswith(("spell:", "skill:"))
            else "zone"
            if key.startswith("zone:")
            else ""
            for key in keys
        }
        for family, root in (
            ("item", "Item"),
            ("character", "Character"),
            ("ability", "Ability"),
            ("stance", "Stance"),
            ("zone", "Zone"),
        ):
            if root in names and (not keys or family in owned_families):
                _validate_structure(findings, parsed, expectation, catalog, family)
        return

    family_templates = {
        "item": ROOT_TEMPLATES & {"Item"} | ITEM_COMPANIONS,
        "ability": {"Ability", *ABILITY_COMPANIONS},
        "stance": {"Stance", "StanceTooltip"},
        "character": {"Character"},
        "zone": {"Zone", "Zone Navbox"},
    }.get(schema)
    expected_keys = _stable_keys(expectation)
    owned_indices: set[int] | None = None
    if expected_keys:
        owned_indices = set()
        if schema == "item":
            item_keys = {key for key in expected_keys if key.startswith("item:")}
            for index, (template, name) in enumerate(zip(templates, names, strict=True)):
                if name == "Item" and _keyed_value(parser, template) in item_keys:
                    owned_indices.add(index)
                    next_index = next(
                        (
                            i
                            for i in range(index + 1, len(names))
                            if names[i] in ITEM_COMPANIONS or names[i] in ROOT_TEMPLATES
                        ),
                        None,
                    )
                    if next_index is not None and names[next_index] in ITEM_COMPANIONS:
                        owned_indices.add(next_index)
        elif schema == "ability":
            ability_keys = {key for key in expected_keys if key.startswith(("spell:", "skill:"))}
            for index, name in enumerate(names):
                if name != "Ability":
                    continue
                next_index = next(
                    (
                        i
                        for i in range(index + 1, len(names))
                        if names[i] in ABILITY_COMPANIONS or names[i] in ROOT_TEMPLATES
                    ),
                    None,
                )
                if next_index is not None and _keyed_value(parser, templates[next_index]) in ability_keys:
                    owned_indices.update((index, next_index))
        elif schema == "stance":
            stance_keys = {key for key in expected_keys if key.startswith("stance:")}
            for index, name in enumerate(names):
                if name != "Stance":
                    continue
                next_index = next(
                    (
                        i
                        for i in range(index + 1, len(names))
                        if names[i] in ABILITY_COMPANIONS or names[i] in ROOT_TEMPLATES
                    ),
                    None,
                )
                if next_index is not None and _keyed_value(parser, templates[next_index]) in stance_keys:
                    owned_indices.update((index, next_index))
        elif schema == "character":
            character_count = sum(key.startswith("character:") for key in expected_keys)
            owned_indices.update(i for i, name in enumerate(names) if name == "Character")
            owned_indices = set(sorted(owned_indices)[:character_count])

    for index, (template, name) in enumerate(zip(templates, names, strict=True)):
        if family_templates is not None and name not in family_templates:
            continue
        if owned_indices is not None and index not in owned_indices:
            continue
        fields = _missing_fields(parser, template, name)
        if fields:
            findings.add("required_schema", parsed.title, f"{name} is missing required parameters: {', '.join(fields)}")

    if schema in {"armor_overview", "weapons_overview", "overview"}:
        if "{|" not in parsed.content or "|}" not in parsed.content:
            findings.add("required_schema", parsed.title, "overview page must contain a complete wikitable")
        if _stable_keys(expectation):
            findings.add("stable_identity", parsed.title, "overview pages must not have stable metadata keys")
        return

    if schema == "item":
        expected_item_keys = [key for key in expected_keys if key.startswith("item:")]
        item_root_indices = [
            i
            for i, (template, name) in enumerate(zip(templates, names, strict=True))
            if name == "Item" and (not expected_item_keys or _keyed_value(parser, template) in expected_item_keys)
        ]
        if expected_item_keys and len(item_root_indices) != len(expected_item_keys):
            findings.add(
                "required_schema",
                parsed.title,
                f"expected {len(expected_item_keys)} Item roots, found {len(item_root_indices)}",
            )
        observed_item_keys: list[str] = []
        for index in item_root_indices:
            key = _keyed_value(parser, templates[index])
            if key is not None:
                observed_item_keys.append(key)
            if key is None:
                findings.add("required_schema", parsed.title, "Item root is missing a nonblank stablekey")
            elif key not in catalog.by_key:
                findings.add("stable_identity", parsed.title, f"Item stablekey {key!r} is absent from the link catalog")
            else:
                _entry_identity(findings, parsed.title, key, "item", catalog)
            next_index = next(
                (i for i in range(index + 1, len(names)) if names[i] in ITEM_COMPANIONS or names[i] in ROOT_TEMPLATES),
                None,
            )
            if next_index is None or names[next_index] not in ITEM_COMPANIONS:
                findings.add(
                    "required_schema", parsed.title, "Item root is not followed by a subtype/ItemTooltip companion"
                )
                continue
            allowed = _expected_item_companion(key, catalog)
            if names[next_index] not in allowed:
                findings.add(
                    "required_schema",
                    parsed.title,
                    f"Item companion {names[next_index]!r} does not match stable key {key!r}",
                )
        if expected_item_keys and set(observed_item_keys) != set(expected_item_keys):
            findings.add(
                "stable_identity",
                parsed.title,
                f"Item stable keys {sorted(observed_item_keys)!r} "
                f"do not match metadata keys {sorted(expected_item_keys)!r}",
            )

    elif schema == "ability":
        expected_ability_keys = [key for key in expected_keys if key.startswith(("spell:", "skill:"))]
        ability_root_indices: list[int] = []
        for index, name in enumerate(names):
            if name != "Ability":
                continue
            next_index = next(
                (
                    i
                    for i in range(index + 1, len(names))
                    if names[i] in ABILITY_COMPANIONS or names[i] in ROOT_TEMPLATES
                ),
                None,
            )
            companion_key = None if next_index is None else _keyed_value(parser, templates[next_index])
            if not expected_ability_keys or companion_key in expected_ability_keys:
                ability_root_indices.append(index)
        if expected_ability_keys and len(ability_root_indices) != len(expected_ability_keys):
            findings.add(
                "required_schema",
                parsed.title,
                f"expected {len(expected_ability_keys)} Ability roots, found {len(ability_root_indices)}",
            )
        observed_ability_keys: list[str] = []
        for index in ability_root_indices:
            next_index = next(
                (
                    i
                    for i in range(index + 1, len(names))
                    if names[i] in ABILITY_COMPANIONS or names[i] in ROOT_TEMPLATES
                ),
                None,
            )
            if next_index is None or names[next_index] not in ABILITY_COMPANIONS:
                findings.add(
                    "required_schema",
                    parsed.title,
                    "Ability root must be immediately followed by a keyed tooltip companion",
                )
                continue
            companion_key = _keyed_value(parser, templates[next_index])
            if companion_key is None:
                findings.add(
                    "required_schema", parsed.title, f"{names[next_index]} companion is missing a nonblank stablekey"
                )
            else:
                observed_ability_keys.append(companion_key)
                if companion_key.startswith("spell:") or companion_key.startswith("skill:"):
                    _entry_identity(findings, parsed.title, companion_key, "ability", catalog)
                else:
                    findings.add(
                        "stable_identity",
                        parsed.title,
                        f"ability companion key {companion_key!r} has no spell:/skill: prefix",
                    )
        if expected_ability_keys and set(observed_ability_keys) != set(expected_ability_keys):
            findings.add(
                "stable_identity",
                parsed.title,
                f"Ability tooltip keys {sorted(observed_ability_keys)!r} "
                f"do not match metadata keys {sorted(expected_ability_keys)!r}",
            )

    elif schema == "stance":
        stance_root_indices: list[int] = []
        stance_key_set = {key for key in expected_keys if key.startswith("stance:")}
        for index, name in enumerate(names):
            if name != "Stance":
                continue
            next_index = next(
                (
                    i
                    for i in range(index + 1, len(names))
                    if names[i] in ABILITY_COMPANIONS or names[i] in ROOT_TEMPLATES
                ),
                None,
            )
            companion_key = None if next_index is None else _keyed_value(parser, templates[next_index])
            if not stance_key_set or companion_key in stance_key_set:
                stance_root_indices.append(index)
        if len(stance_root_indices) != 1:
            findings.add(
                "required_schema",
                parsed.title,
                f"expected one Stance root, found {len(stance_root_indices)}",
            )
        observed_stance_keys: list[str] = []
        for index in stance_root_indices:
            next_index = next(
                (
                    i
                    for i in range(index + 1, len(names))
                    if names[i] in ABILITY_COMPANIONS or names[i] in ROOT_TEMPLATES
                ),
                None,
            )
            if next_index is None or names[next_index] != "StanceTooltip":
                findings.add(
                    "required_schema", parsed.title, "Stance root must be immediately followed by StanceTooltip"
                )
                continue
            key = _keyed_value(parser, templates[next_index])
            if key is None:
                findings.add("required_schema", parsed.title, "StanceTooltip is missing a nonblank stablekey")
            else:
                observed_stance_keys.append(key)
                _entry_identity(findings, parsed.title, key, "ability", catalog)
                if not key.startswith("stance:"):
                    findings.add("stable_identity", parsed.title, f"StanceTooltip key {key!r} is not a stance identity")
        expected_stance_keys = [key for key in expected_keys if key.startswith("stance:")]
        if expected_stance_keys and set(observed_stance_keys) != set(expected_stance_keys):
            findings.add(
                "stable_identity",
                parsed.title,
                f"Stance tooltip keys {sorted(observed_stance_keys)!r} "
                f"do not match metadata keys {sorted(expected_stance_keys)!r}",
            )

    elif schema == "character":
        character_roots = [template for template, name in zip(templates, names, strict=True) if name == "Character"]
        character_keys = [key for key in expected_keys if key.startswith("character:")]
        owned_roots = character_roots[: len(character_keys)] if character_keys else character_roots
        if character_keys and len(owned_roots) != len(character_keys):
            findings.add(
                "required_schema",
                parsed.title,
                f"expected {len(character_keys)} Character roots, found {len(owned_roots)}",
            )
        for key in character_keys:
            _entry_identity(findings, parsed.title, key, "character", catalog)

    elif schema == "zone":
        zone_root_count = names.count("Zone")
        if zone_root_count < 1:
            findings.add("required_schema", parsed.title, "zone page requires a Zone template")
        if names.count("Zone Navbox") != 1:
            findings.add("required_schema", parsed.title, "zone page requires exactly one Zone Navbox")
        for key in expected_keys:
            if key.startswith("zone:"):
                _entry_identity(findings, parsed.title, key, "zone", catalog)


def _validate_identity_metadata(
    findings: _Findings, page: str, expectation: WikiPageExpectation, catalog: _Catalog, schema: str
) -> None:
    metadata = expectation.metadata
    if metadata is None:
        return
    if _title_key(metadata.page_title) != _title_key(page):
        findings.add("title_inventory", page, f"metadata page_title {metadata.page_title!r} does not match mapping key")
    seen: set[str] = set()
    for key in metadata.stable_keys:
        if not key or not key.strip():
            findings.add("stable_identity", page, "metadata contains a blank stable key")
        elif key in seen:
            findings.add("stable_identity", page, f"metadata repeats stable key {key!r}")
        seen.add(key)
    if schema in {"armor_overview", "weapons_overview", "overview"} and metadata.stable_keys:
        findings.add("stable_identity", page, "overview metadata stable_keys must be empty")


def _validate_ownership(
    findings: _Findings, parsed: _ParsedPage, expectation: WikiPageExpectation, catalog: _Catalog, schema: str
) -> None:
    allowed = _expected_templates(expectation, parsed, catalog, schema)
    if schema in {"armor_overview", "weapons_overview", "overview"}:
        for name in parsed.names:
            if name in GENERATED_TEMPLATES and name not in SEMANTIC_LINK_TEMPLATES:
                findings.add(
                    "generated_manual_ownership",
                    parsed.title,
                    f"overview contains generated entity template {name!r}; only the table is generated",
                )
        return
    if not allowed:
        # Synthetic pages without metadata can still be validated structurally;
        # infer ownership from the roots actually present rather than requiring
        # integrations to duplicate dispatch logic.
        allowed = {name for name in parsed.names if name in GENERATED_TEMPLATES}
    fetched_counts: Counter[str] = Counter()
    if expectation.fetched_content is not None:
        balance_error = _balanced_delimiters(expectation.fetched_content)
        if balance_error is not None:
            findings.add("parseability", parsed.title, f"fetched content: {balance_error}")
            return
        try:
            fetched_counts.update(_name(template) for template in _top_level_templates(expectation.fetched_content))
        except Exception as exc:
            findings.add("parseability", parsed.title, f"fetched content is not parseable: {exc}")
            return
    generated_counts: Counter[str] = Counter()
    for name in parsed.names:
        if name not in GENERATED_TEMPLATES or name in allowed:
            continue
        generated_counts[name] += 1
        if generated_counts[name] > fetched_counts[name]:
            findings.add(
                "generated_manual_ownership",
                parsed.title,
                f"generated template family {name!r} is not owned by this page's catalog identities",
            )


def _merge_parts(value: str) -> tuple[str, ...]:
    if "<br>" in value:
        return tuple(part.strip() for part in value.split("<br>") if part.strip())
    if "," in value and "{{!}}" not in value:
        return tuple(part.strip() for part in value.split(",") if part.strip())
    return (value.strip(),) if value.strip() else ()


def _validate_manual_overrides(findings: _Findings, parsed: _ParsedPage, fetched: str | None) -> None:
    if fetched is None:
        return
    parser = TemplateParser()
    balance_error = _balanced_delimiters(fetched)
    if balance_error is not None:
        findings.add("manual_overrides", parsed.title, f"fetched content: {balance_error}")
        return
    try:
        old_templates = _top_level_templates(fetched)
    except Exception as exc:
        findings.add("manual_overrides", parsed.title, f"fetched content is not parseable: {exc}")
        return
    by_name: dict[str, list[Any]] = {}
    for template in old_templates:
        by_name.setdefault(_canonical_template_name(_name(template)), []).append(template)
    offsets: dict[str, int] = {}
    for template, name in zip(parsed.templates, parsed.names, strict=True):
        rules = DEFAULT_PRESERVATION_RULES.get(name)
        if not rules:
            continue
        key = _canonical_template_name(name)
        index = offsets.get(key, 0)
        offsets[key] = index + 1
        old_list = by_name.get(key, [])
        if index >= len(old_list):
            continue
        old_fields = parser.get_params(old_list[index])
        new_fields = parser.get_params(template)
        expected = FieldPreservationHandler().apply_preservation(name, old_fields, new_fields)
        for field, rule in rules.items():
            if rule not in {"preserve", "prefer_manual", "merge"}:
                continue
            actual = new_fields.get(field, "")
            if rule == "merge":
                old_parts = set(_merge_parts(old_fields.get(field, "")))
                actual_parts = set(_merge_parts(actual))
                if old_parts.issubset(actual_parts):
                    continue
            if actual != expected.get(field, ""):
                findings.add(
                    "manual_overrides",
                    parsed.title,
                    f"{name}.{field} violates {rule}: expected {expected.get(field, '')!r}, got {actual!r}",
                )


def _category_tag(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("[[Category:") and stripped[-2:] == "]]":
        return stripped
    if stripped.startswith("Category:"):
        return f"[[{stripped}]]"
    return f"[[Category:{stripped}]]"


def _extract_categories(content: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\[\[Category:[^\]]+\]\]", content))


def _validate_categories(findings: _Findings, page: str, content: str, expected: tuple[str, ...] | None) -> None:
    categories = _extract_categories(content)
    keys = [_title_key(value) for value in categories]
    if len(keys) != len(set(keys)):
        findings.add("categories", page, "category tags must not be duplicated")
    legacy = set(PageNormalizer.LEGACY_CATEGORIES)
    for category in categories:
        if category in legacy:
            findings.add("categories", page, f"legacy category is forbidden: {category}")
    if tuple(categories) != tuple(sorted(categories)):
        findings.add("categories", page, "category tags must be sorted alphabetically")
    if categories:
        lines = content.rstrip("\n").splitlines()
        first_category = next((i for i, line in enumerate(lines) if "[[Category:" in line), len(lines))
        if any("[[Category:" not in line for line in lines[first_category:]):
            findings.add("categories", page, "category tags must be contiguous at the bottom of the page")
        elif any("[[Category:" in line for line in lines[:first_category]):
            findings.add("categories", page, "category tags must occur only at the bottom of the page")
        elif any(line.strip() for line in lines[first_category + len(categories) :]):
            findings.add("categories", page, "non-category content follows the category block")
    if expected is not None:
        actual = {_title_key(value) for value in categories}
        wanted = {_title_key(_category_tag(value)) for value in expected}
        if actual != wanted:
            findings.add(
                "categories",
                page,
                f"category set differs from expectation: expected {sorted(wanted)!r}, got {sorted(actual)!r}",
            )


def build_semantic_manifest(
    generated_pages: Mapping[str, str],
    *,
    expectations: Mapping[str, WikiPageExpectation | PageMetadata | Mapping[str, object]],
    catalog_entries: Sequence[LinkCatalogEntry | Mapping[str, object]],
) -> SemanticManifest:
    """Build a deterministic, presentation-independent manifest for a generated corpus."""
    catalog = _catalog(catalog_entries)
    entries: list[SemanticManifestEntry] = []
    for title in sorted(generated_pages, key=lambda value: (value.casefold(), value)):
        if title not in expectations:
            raise ValueError(f"Semantic manifest expectation missing for {title!r}")
        content = generated_pages[title]
        expectation = _metadata_for(title, expectations[title])
        parsed = _parse_page(title, content)
        stable_keys = _stable_keys(expectation)
        schema = _schema_from_names(parsed.names, expectation.schema_kind, stable_keys, catalog)
        generated_templates = sorted(
            {name for name in parsed.names if name in GENERATED_TEMPLATES},
            key=lambda value: (value.casefold(), value),
        )
        entries.append(
            {
                "title": title,
                "stable_keys": list(stable_keys),
                "schema": schema,
                "generated_templates": generated_templates,
                "categories": sorted(
                    (category[2:-2] for category in _extract_categories(content)),
                    key=lambda value: (value.casefold(), value),
                ),
                "semantic_links": _semantic_link_inventory(content),
            }
        )
    return {"version": 1, "pages": entries}


def _semantic_link_inventory(content: str) -> list[str]:
    parser = TemplateParser()
    code = parser.parse(content)
    links: list[str] = []
    for template in code.filter_templates(recursive=True):
        name = _name(template)
        if name not in SEMANTIC_LINK_TEMPLATES:
            continue
        params = _params(parser, template)
        for parameter in ("stablekey", "link", "1"):
            value = params.get(parameter, "").strip()
            if value:
                links.append(f"{name}:{parameter}:{value}")
                break
    return sorted(links, key=lambda value: (value.casefold(), value))


def validate_wiki_pages(
    generated_pages: Mapping[str, str],
    *,
    expectations: Mapping[str, WikiPageExpectation | PageMetadata | Mapping[str, object]] | None = None,
    catalog_entries: Sequence[LinkCatalogEntry | Mapping[str, object]] = (),
    planned_titles: Collection[str] | None = None,
    known_generated_titles: Collection[str] | None = None,
    variant: str = "",
) -> SemanticValidationReport:
    """Validate a complete generated corpus without filesystem or network I/O."""
    findings = _Findings()
    catalog = _catalog(catalog_entries)
    expectation_map = expectations or {}
    pages: dict[str, str] = {}
    canonical_pages: dict[str, str] = {}
    for raw_title, content in generated_pages.items():
        if not isinstance(raw_title, str):
            findings.add("title_inventory", repr(raw_title), "generated page title must be text")
            continue
        title = raw_title
        if not title.strip():
            findings.add("title_inventory", title, "generated page title must be nonblank")
            continue
        if not isinstance(content, str):
            findings.add("parseability", title, "generated page content must be text")
            continue
        key = _title_key(title)
        if key in canonical_pages:
            findings.add("title_inventory", title, f"canonical title duplicates {canonical_pages[key]!r}")
        else:
            canonical_pages[key] = title
        pages[title] = content
    page_keys = set(pages)
    expectation_keys = set(expectation_map)
    if expectation_map and expectation_keys != page_keys:
        for missing in sorted(page_keys - expectation_keys, key=lambda value: (value.casefold(), value)):
            findings.add("title_inventory", missing, "page has no matching metadata/expectation key")
        for extra in sorted(expectation_keys - page_keys, key=lambda value: (value.casefold(), value)):
            findings.add("title_inventory", extra, "metadata/expectation key has no generated page")
    parsed_pages: list[tuple[_ParsedPage, WikiPageExpectation, str]] = []
    for page in sorted(pages, key=lambda value: (value.casefold(), value)):
        content = pages[page]
        expectation = _metadata_for(page, expectation_map.get(page))
        if expectation.title != page:
            findings.add("title_inventory", page, f"expectation title {expectation.title!r} does not match mapping key")
        balance_error = _balanced_delimiters(content)
        if balance_error:
            findings.add("parseability", page, balance_error)
        try:
            parsed = _parse_page(page, content)
        except Exception as exc:
            findings.add("parseability", page, str(exc))
            continue
        stable_keys = _stable_keys(expectation)
        schema = _schema_from_names(parsed.names, expectation.schema_kind, stable_keys, catalog)
        parsed_pages.append((parsed, expectation, schema))
        _validate_identity_metadata(findings, page, expectation, catalog, schema)
        _validate_structure(findings, parsed, expectation, catalog, schema)
        _validate_ownership(findings, parsed, expectation, catalog, schema)
        _validate_manual_overrides(findings, parsed, expectation.fetched_content)
        _validate_categories(findings, page, content, expectation.expected_categories)
    if catalog_entries:
        planned = tuple(planned_titles) if planned_titles is not None else tuple(pages)
        known = tuple(known_generated_titles) if known_generated_titles is not None else tuple(pages)
        audit = audit_links(
            generated_pages=pages,
            catalog_entries=tuple(catalog_entries),
            planned_titles=planned,
            known_generated_titles=known,
            variant=variant,
        )
        for finding in audit.findings:
            if finding.severity == "error":
                findings.add("semantic_links", finding.source_page, f"{finding.code}: {finding.message}")
    return findings.report()


__all__ = [
    "GENERATED_TEMPLATES",
    "INVARIANT_CODES",
    "ITEM_COMPANIONS",
    "REQUIRED_TEMPLATE_FIELDS",
    "GeneratedManualOwnershipEntry",
    "GeneratedManualOwnershipReport",
    "PageContract",
    "SemanticFinding",
    "SemanticManifest",
    "SemanticManifestEntry",
    "SemanticValidationError",
    "SemanticValidationReport",
    "WikiPageExpectation",
    "build_generated_manual_ownership_report",
    "build_semantic_manifest",
    "derive_corpus_expectations",
    "derive_page_contract",
    "validate_wiki_pages",
]
