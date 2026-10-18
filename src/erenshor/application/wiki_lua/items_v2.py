"""Versioned item facts and bounded canonical provenance for data-backed articles."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.items import ItemDataRepository, _item_kind, _item_record
from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.application.wiki_lua.views import native_reference
from erenshor.domain.value_objects.item_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    fact_to_dict,
)
from erenshor.domain.value_objects.wiki_filename import picture_file_title

if TYPE_CHECKING:
    from erenshor.domain.entities.item import Item
    from erenshor.infrastructure.content_lifecycle import ContentLifecycle, LifecyclePage

ITEMS_SCHEMA_VERSION = 2
REFERENCE_KINDS = frozenset({"item", "character", "quest", "zone", "class", "faction", "spell", "skill", "stance"})
REFERENCE_FIELDS = frozenset(
    {
        "source_stable_key",
        "source_copy_stable_key",
        "target_stable_key",
        "reference_stable_key",
        "zone_stable_key",
    }
)


def _references(facts: object, catalog: Mapping[str, Mapping[str, object]]) -> dict[str, dict[str, object]]:
    """Collect only this owner's native references without rewriting canonical facts."""
    keys: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for field, child in value.items():
                if field in REFERENCE_FIELDS and isinstance(child, str) and child.partition(":")[0] in REFERENCE_KINDS:
                    keys.add(child)
                elif isinstance(child, (dict, list, tuple)):
                    visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(facts)
    references = {key: native_reference(key, catalog, kind=key.partition(":")[0]) for key in sorted(keys)}
    for key, reference in references.items():
        if not isinstance(reference["name"], str) or not reference["name"]:
            raise ValueError(f"{key}: missing native reference name")
        if "page" in reference and (not isinstance(reference["page"], str) or not reference["page"]):
            raise ValueError(f"{key}: invalid native reference page")
    return references


@dataclass(frozen=True, slots=True)
class ItemsV2Data:
    index: dict[str, object]
    items: dict[str, dict[str, dict[str, object]]]
    provenance: dict[str, dict[str, dict[str, object]]]


class CompleteItemDataRepository(ItemDataRepository, Protocol):
    def get_item_renders(self, stable_key: str) -> dict[str | None, str]: ...


class CanonicalItemProvenanceRepository(Protocol):
    def iter_acquisitions(self) -> Iterable[ItemAcquisition]: ...

    def iter_uses(self) -> Iterable[ItemUse]: ...

    def iter_dispositions(self) -> Iterable[ItemDisposition]: ...


def item_bucket(stable_key: str) -> str:
    """Keep unrelated additions from moving an item's data dependencies."""
    return hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:2]


def _effects(item: Item) -> list[dict[str, object]]:
    effects: list[dict[str, object]] = []
    weapon_trigger = (
        "Cast"
        if item.required_slot == "Bracer"
        else "Bash"
        if item.shield
        else "Attack"
        if item.required_slot in {"Primary", "Secondary", "PrimaryOrSecondary"}
        else None
    )
    fields = (
        ("weaponProc", "weapon_proc_on_hit_stable_key", "weapon_proc_chance", weapon_trigger),
        ("wandEffect", "wand_effect_stable_key", "wand_proc_chance", "Attack"),
        ("bowEffect", "bow_effect_stable_key", "bow_proc_chance", "Attack"),
        ("clickEffect", "item_effect_on_click_stable_key", None, "Click"),
        ("skillUse", "item_skill_use_stable_key", None, "Click"),
        ("teachesSpell", "teach_spell_stable_key", None, "Learn"),
        ("teachesSkill", "teach_skill_stable_key", None, "Learn"),
        ("aura", "aura_stable_key", None, "Aura"),
        ("wornEffect", "worn_effect_stable_key", None, "Worn"),
    )
    for kind, attribute, chance_attribute, trigger in fields:
        key = getattr(item, attribute)
        if key is None:
            continue
        row: dict[str, object] = {
            "kind": kind,
            "skillKey" if kind in {"skillUse", "teachesSkill"} else "spellKey": key,
        }
        if trigger is not None:
            row["trigger"] = trigger
        if chance_attribute is not None:
            chance = getattr(item, chance_attribute)
            if chance is not None:
                row["chance"] = chance
        effects.append(row)
    return effects


def build_items_v2_data(
    item_repo: CompleteItemDataRepository,
    provenance_repo: CanonicalItemProvenanceRepository,
    *,
    build: Mapping[str, str],
    native_catalog: Mapping[str, Mapping[str, object]],
    class_display_names: Mapping[str, str] | None = None,
    lifecycle: ContentLifecycle | None = None,
) -> ItemsV2Data:
    """Serialize canonical facts without selecting, grouping or wording sources.

    Each identity loads one entity bucket and one provenance bucket. Legacy
    Items pages retain their own schema and readers during the rollback window.
    """
    if not build.get("gameBuildId") or not build.get("publishedAt"):
        raise ValueError("ItemsV2 requires the source game build and publication identity")
    by_key: dict[str, str] = {}
    items: defaultdict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    provenance: defaultdict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    article_items = sorted(item_repo.get_items_for_wiki_generation(), key=lambda value: value.stable_key)
    read_quests = {
        item.stable_key: [
            {"target_stable_key": quest}
            for quest in (item.assign_quest_on_read_stable_key, item.complete_on_read_stable_key)
            if quest is not None
        ]
        for item in article_items
    }
    acquisitions_by_item: defaultdict[str, list[ItemAcquisition]] = defaultdict(list)
    uses_by_item: defaultdict[str, list[ItemUse]] = defaultdict(list)
    fact_keys: set[str] = set()
    referenced_outcomes: set[str] = set()
    for use in provenance_repo.iter_uses():
        if use.use_key in fact_keys:
            raise ValueError(f"{use.item_stable_key}: duplicate canonical fact identity")
        fact_keys.add(use.use_key)
        uses_by_item[use.item_stable_key].append(use)
        if use.outcome_key is not None:
            referenced_outcomes.add(use.outcome_key)
    outcome_item_by_key: dict[str, str] = {}
    for acquisition in provenance_repo.iter_acquisitions():
        if acquisition.acquisition_key in fact_keys:
            raise ValueError(f"{acquisition.item_stable_key}: duplicate canonical fact identity")
        fact_keys.add(acquisition.acquisition_key)
        acquisitions_by_item[acquisition.item_stable_key].append(acquisition)
        if acquisition.acquisition_key in referenced_outcomes:
            outcome_item_by_key[acquisition.acquisition_key] = acquisition.item_stable_key
    missing_outcomes = referenced_outcomes - outcome_item_by_key.keys()
    if missing_outcomes:
        raise ValueError(f"Missing canonical acquisition outcomes: {', '.join(sorted(missing_outcomes))}")
    dispositions: dict[str, ItemDisposition] = {}
    for disposition in provenance_repo.iter_dispositions():
        key = disposition.item_stable_key
        if key in dispositions:
            raise ValueError(f"{key}: duplicate canonical disposition identity")
        dispositions[key] = disposition
    provenance_by_key: dict[str, str] = {}
    for key in sorted(
        set(acquisitions_by_item) | set(uses_by_item) | set(dispositions) | {item.stable_key for item in article_items}
    ):
        item_disposition = dispositions.get(key)
        if item_disposition is None:
            raise ValueError(f"{key}: missing canonical disposition")
        bucket = item_bucket(key)
        provenance[bucket][key] = {
            "acquisitions": [
                fact_to_dict(value)
                for value in sorted(acquisitions_by_item[key], key=lambda value: value.acquisition_key)
            ],
            "uses": [fact_to_dict(value) for value in sorted(uses_by_item[key], key=lambda value: value.use_key)],
            "disposition": fact_to_dict(item_disposition),
        }
        record = provenance[bucket][key]
        outcome_references = [
            {"target_stable_key": key}
            for value in acquisitions_by_item[key]
            if value.acquisition_key in referenced_outcomes
        ]
        record["references"] = _references(
            [record["acquisitions"], record["uses"], outcome_references, read_quests.get(key, [])], native_catalog
        )
        provenance_by_key[key] = bucket
    lifecycle_pages: dict[str, LifecyclePage] = {}
    if lifecycle is not None:
        for page in lifecycle.pages.values():
            if page.stable_key is not None and page.stable_key.startswith("item:"):
                if page.stable_key in lifecycle_pages and lifecycle_pages[page.stable_key] != page:
                    raise ValueError(f"{page.stable_key}: conflicting reviewed lifecycle notices")
                lifecycle_pages[page.stable_key] = page
    for item in article_items:
        if not item.wiki_page_name:
            continue
        key = item.stable_key
        if key in by_key:
            raise ValueError(f"Duplicate ItemsV2 identity: {key}")
        if item.item_db_index is None:
            raise ValueError(f"{key}: missing item_db_index")
        disposition = dispositions[key]
        lifecycle_record = fact_to_dict(disposition)
        notice = lifecycle_pages.get(key)
        if notice is not None:
            if notice.state != disposition.disposition:
                raise ValueError(f"{key}: reviewed notice disagrees with canonical disposition")
            notice_record: dict[str, object] = {
                field: value
                for field, value in (("update", notice.update), ("date", notice.date), ("url", notice.patch_notes_url))
                if value is not None
            }
            if notice.chat:
                notice_record["chat"] = True
            lifecycle_record["notice"] = notice_record
        bucket = item_bucket(key)
        row = _item_record(
            item,
            item_repo.get_item_stats(key),
            item_repo.get_item_classes(key),
            item_repo.get_crafting_recipe(key),
            class_display_names,
            [
                (use.target_stable_key, use.mechanic or "")
                for use in uses_by_item[key]
                if use.kind == "zone_restriction" and use.target_stable_key is not None
            ],
        )
        row.update(
            stableKey=key,
            kind=str(_item_kind(item)),
            itemDbIndex=item.item_db_index,
            provenanceShard=bucket,
            build=dict(build),
            lifecycle=lifecycle_record,
            aliases=list(disposition.former_pages),
            screenshot=picture_file_title("screenshot", item.image_name, item.display_name, item.item_name),
            renders=[
                {"title": title, **({"body": body} if body is not None else {})}
                for body, title in sorted(item_repo.get_item_renders(key).items(), key=lambda pair: pair[1])
            ],
            effects=_effects(item),
        )
        for lua_name, attribute in (
            ("fuelLevel", "fuel_level"),
            ("mining", "mining"),
            ("cosmeticEffect", "cosmetic_effect"),
        ):
            value = getattr(item, attribute)
            if value is not None:
                row[lua_name] = value
        for lua_name, attribute in (("furnitureSet", "furniture_set"), ("auctionable", "is_auctionable")):
            value = getattr(item, attribute)
            if value is not None:
                row[lua_name] = bool(value)
        items[bucket][key] = row
        by_key[key] = bucket
    return ItemsV2Data(
        index={
            "schemaVersion": ITEMS_SCHEMA_VERSION,
            "provenanceSchemaVersion": PROVENANCE_SCHEMA_VERSION,
            "build": dict(build),
            "byKey": by_key,
            "provenanceByKey": provenance_by_key,
            "outcomeItemByKey": dict(sorted(outcome_item_by_key.items())),
        },
        items=dict(items),
        provenance=dict(provenance),
    )


def generate_items_v2_modules(
    item_repo: CompleteItemDataRepository,
    provenance_repo: CanonicalItemProvenanceRepository,
    *,
    build: Mapping[str, str],
    native_catalog: Mapping[str, Mapping[str, object]],
    class_display_names: Mapping[str, str] | None = None,
    lifecycle: ContentLifecycle | None = None,
    max_page_bytes: int | None = None,
) -> dict[str, str]:
    """Serialize items and split provenance by the size of the published text."""
    data = build_items_v2_data(
        item_repo,
        provenance_repo,
        build=build,
        native_catalog=native_catalog,
        class_display_names=class_display_names,
        lifecycle=lifecycle,
    )
    if max_page_bytes is not None and max_page_bytes <= 0:
        raise ValueError("Item provenance page budget must be positive")
    modules: dict[str, str] = {}
    routes: dict[str, str] = {}
    pending = sorted(data.provenance.items(), reverse=True)
    while pending:
        bucket, records = pending.pop()
        content = module_text(records)
        size = len(content.encode("utf-8"))
        if max_page_bytes is not None and size > max_page_bytes:
            if len(records) == 1 or len(bucket) == 64:
                raise ValueError(
                    f"Item provenance owner cannot fit page budget: {sorted(records)} "
                    f"({size} bytes, limit {max_page_bytes})"
                )
            children: defaultdict[str, dict[str, dict[str, object]]] = defaultdict(dict)
            for key, record in sorted(records.items()):
                child = hashlib.sha256(key.encode("utf-8")).hexdigest()[: len(bucket) + 1]
                children[child][key] = record
            pending.extend(sorted(children.items(), reverse=True))
            continue
        modules[f"ItemProvenanceV1/{bucket}.lua"] = content
        routes.update(dict.fromkeys(records, bucket))
    data.index["provenanceByKey"] = dict(sorted(routes.items()))
    for bucket in sorted(data.items):
        for key, record in data.items[bucket].items():
            record["provenanceShard"] = routes[key]
        modules[f"ItemsV2/{bucket}.lua"] = module_text(data.items[bucket])
    modules["ItemsV2.lua"] = module_text(data.index)
    return dict(sorted(modules.items(), key=lambda pair: (pair[0].startswith("ItemProvenanceV1/"), pair[0])))


def write_items_v2_modules(
    item_repo: CompleteItemDataRepository,
    provenance_repo: CanonicalItemProvenanceRepository,
    output_root: Path,
    *,
    build: Mapping[str, str],
    native_catalog: Mapping[str, Mapping[str, object]],
    class_display_names: Mapping[str, str] | None = None,
    lifecycle: ContentLifecycle | None = None,
    max_page_bytes: int,
) -> list[Path]:
    """Write versioned entity and relation pages to the generation staging tree."""
    modules = generate_items_v2_modules(
        item_repo,
        provenance_repo,
        build=build,
        native_catalog=native_catalog,
        class_display_names=class_display_names,
        lifecycle=lifecycle,
        max_page_bytes=max_page_bytes,
    )
    paths: list[Path] = []
    for relative, content in modules.items():
        path = output_root / "Erenshor" / "Data" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths
