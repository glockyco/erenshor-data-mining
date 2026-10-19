"""Generate the quest panel without collapsing its exported resource variants."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Protocol

from erenshor.application.wiki_lua.views import DataView, ViewDataError, ViewField, native_reference, view_module_text

QUESTS = DataView(
    module="Quests",
    description="Quest panels. Variant rows and their child rows retain the resource identity. "
    "Acquisition and completion routes without a variant apply to the canonical quest, not an inferred resource. "
    "Routes are alternatives. Prerequisites belong only to their route, and it needs all of them. "
    "Required items within a variant are all required. "
    "Variant rows require variant, experience, gold, repeatable and every behavior flag. "
    "Required rows require variant, item and quantity. Faction rows require variant, faction and amount. "
    "Completes rows require variant and quest. "
    "Routes require method and, except scripted events, source and sourceKind. Item rewards require quantity.",
    entity="quest",
    fields=(
        ViewField("type", "text", "variant, acquisition, completion, required, faction, or completes."),
        ViewField("variant", "text", "Exported resource identity. Absent on canonical quest routes.", optional=True),
        ViewField("method", "text", "Exported acquisition or completion mechanism.", optional=True),
        ViewField("source", "reference", "The native source identity.", optional=True),
        ViewField("sourceKind", "text", "The semantic kind of the source.", optional=True),
        ViewField("sourceCopy", "text", "The exported character copy that supplies this route.", optional=True),
        ViewField("sourceVariant", "text", "The preceding quest resource that assigns this quest.", optional=True),
        ViewField("dialogIndex", "integer", "The dialog entry of the source copy.", optional=True),
        ViewField("keywords", "text", "The exported dialog keywords, separated by commas.", optional=True),
        ViewField("prerequisites", "references", "Quests whose completion this route alone needs.", optional=True),
        ViewField(
            "notOwnedItem",
            "reference",
            "This dialog returns before assignment/completion when the item is carried.",
            optional=True,
        ),
        ViewField(
            "blockedByQuest",
            "reference",
            "Completing this nonrepeatable dialog assignment blocks this route.",
            optional=True,
        ),
        ViewField(
            "requiredItem",
            "reference",
            "A scripted event of this route acts only while the item is carried.",
            optional=True,
        ),
        ViewField(
            "furniture",
            "reference",
            "Furniture that must be placed in the source's room for this route.",
            optional=True,
        ),
        ViewField("room", "text", "Exported Reliquary room slot of the furniture condition.", optional=True),
        ViewField("note", "text", "Exported condition or scripted-source explanation.", optional=True),
        ViewField(
            "item",
            "reference",
            "Required item, reachable TradeWindow reward, or this completion dialog's GiveItem.",
            optional=True,
        ),
        ViewField("quantity", "integer", "Required quantity or executed item reward quantity.", optional=True),
        ViewField("requiredSlot", "integer", "Exported required-item slot within the quest resource.", optional=True),
        ViewField("mechanic", "text", "Canonical acquisition mechanic identity.", optional=True),
        ViewField(
            "acquisitionKey", "text", "Canonical item acquisition identity for this reward route.", optional=True
        ),
        ViewField(
            "experience",
            "integer",
            "Reachable TradeWindow experience reward. FinishQuest alone grants none.",
            optional=True,
        ),
        ViewField(
            "gold", "integer", "Reachable TradeWindow gold reward. FinishQuest alone grants none.", optional=True
        ),
        ViewField(
            "rewardMethod",
            "text",
            "item_turnin when a reachable TradeWindow route executes the resource rewards.",
            optional=True,
        ),
        ViewField("repeatable", "boolean", "QuestAvailable allows another completion after the first.", optional=True),
        ViewField(
            "oncePerSpawn", "boolean", "Item turn-in closes after completion for this spawn instance.", optional=True
        ),
        ViewField(
            "partialAssigns",
            "boolean",
            "A reachable partial turn-in starts this quest.",
            optional=True,
        ),
        ViewField("killsHolder", "boolean", "Item turn-in kills its holder.", optional=True),
        ViewField(
            "dropsInvulnerability", "boolean", "Item turn-in removes its holder's invulnerability.", optional=True
        ),
        ViewField("nextQuest", "reference", "Quest assigned by completion of this resource.", optional=True),
        ViewField(
            "unlocksItem", "reference", "Item that completion makes available to configured vendors.", optional=True
        ),
        ViewField("faction", "reference", "Faction affected by this resource.", optional=True),
        ViewField("amount", "integer", "Signed faction change for this resource.", optional=True),
        ViewField("quest", "reference", "Other active quest completed by this resource.", optional=True),
    ),
)

_REQUIRED = {
    "variant": (
        "variant",
        "experience",
        "gold",
        "repeatable",
        "oncePerSpawn",
        "partialAssigns",
        "killsHolder",
        "dropsInvulnerability",
    ),
    "required": ("variant", "item", "quantity"),
    "faction": ("variant", "faction", "amount"),
    "completes": ("variant", "quest"),
    "acquisition": ("method",),
    "completion": ("method",),
}
_METHODS = {
    "acquisition": {"dialog", "item_read", "zone_entry", "quest_chain", "partial_turnin", "scripted"},
    "completion": {"item_turnin", "talk", "read", "zone", "chain", "death", "shout", "scripted"},
}

_REFERENCE_KINDS = {
    "prerequisites": "quest",
    "notOwnedItem": "item",
    "blockedByQuest": "quest",
    "requiredItem": "item",
    "furniture": "item",
    "item": "item",
    "nextQuest": "quest",
    "unlocksItem": "item",
    "faction": "faction",
    "quest": "quest",
}


def _quest_reference(
    field: str, value: object, row: Mapping[str, object], catalog: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    if not isinstance(value, str):
        raise ViewDataError(f"Quest field {field!r} requires a native stable key, not {value!r}")
    kind = row.get("sourceKind") if field == "source" else _REFERENCE_KINDS[field]
    if not isinstance(kind, str):
        raise ViewDataError("Quest source reference requires its native sourceKind")
    return native_reference(value, catalog, kind=kind)


def quest_module_text(
    rows_by_quest: dict[str, list[dict[str, object]]],
    known_keys: Collection[str],
    *,
    native_catalog: Mapping[str, Mapping[str, object]],
) -> str:
    """Validate the shared declaration and each discriminated quest row shape."""
    reference_fields = {field.name for field in QUESTS.fields if field.type == "reference"}
    reference_lists = {field.name for field in QUESTS.fields if field.type == "references"}

    def project(field: str, value: object, row: Mapping[str, object]) -> object:
        if value is None:
            return value
        if field in reference_fields:
            return _quest_reference(field, value, row, native_catalog)
        if field in reference_lists:
            if not isinstance(value, list):
                raise ViewDataError(f"Quest field {field!r} requires a list of native stable keys, not {value!r}")
            return [_quest_reference(field, item, row, native_catalog) for item in value]
        return value

    projected = {
        quest: [{field: project(field, value, row) for field, value in row.items()} for row in rows]
        for quest, rows in rows_by_quest.items()
    }
    content = view_module_text(QUESTS, projected, known_keys, reference_catalog=native_catalog)
    for quest, rows in rows_by_quest.items():
        variants = [row["variant"] for row in rows if row["type"] == "variant" and "variant" in row]
        for index, row in enumerate(rows, start=1):
            where = f"{QUESTS.title}: row {index} of {quest}"
            row_type = str(row["type"])
            if row_type not in _REQUIRED:
                raise ViewDataError(f"{where}: field 'type' has unknown row kind {row_type!r}")
            required = _REQUIRED[row_type]
            if row_type in _METHODS:
                method = row.get("method")
                if method is not None and method not in _METHODS[row_type]:
                    raise ViewDataError(f"{where}: field 'method' has unknown {row_type} method {method!r}")
                if method != "scripted":
                    required += ("source", "sourceKind")
            if row_type in {"variant", "completion"} and "item" in row:
                required += ("quantity",)
            if "furniture" in row or "room" in row:
                required += ("furniture", "room")
            for field in required:
                if row.get(field) is None:
                    raise ViewDataError(f"{where}: field {field!r} is missing for {row_type}")
            if "variant" in row and variants.count(row["variant"]) != 1:
                raise ViewDataError(f"{where}: field 'variant' must identify exactly one variant row")
    return content


class QuestPanelRepository(Protocol):
    """Variant-preserving quest relationships needed by the panel."""

    def get_quest_panel_rows(self) -> dict[str, list[dict[str, object]]]: ...


def write_quests_module(
    repo: QuestPanelRepository,
    known_keys: Collection[str],
    output_root: Path,
    *,
    native_catalog: Mapping[str, Mapping[str, object]],
) -> Path:
    """Write the declared and native-identity-validated ``Data/Quests.lua`` view."""
    content = quest_module_text(repo.get_quest_panel_rows(), known_keys, native_catalog=native_catalog)
    output_path = output_root / "Erenshor" / "Data" / "Quests.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
