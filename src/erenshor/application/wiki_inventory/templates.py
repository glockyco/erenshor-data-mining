"""Template ownership classification for the clean wiki cutover."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from erenshor.application.wiki_inventory.api import EmbeddedInSummary


class OwnershipClass(StrEnum):
    """Ownership classes used in `wiki/ownership.yml`."""

    REPO_OWNED_TEMPLATE = "repo_owned_template"
    REPO_OWNED_MODULE = "repo_owned_module"
    GENERATED_DATA_MODULE = "generated_data_module"
    HUMAN_OWNED_ARTICLE = "human_owned_article"
    LEGACY_TEMPLATE = "legacy_template"
    HELPER_TEMPLATE = "helper_template"
    DOCUMENTATION_TEMPLATE = "documentation_template"
    LICENSE_TEMPLATE = "license_template"
    NAVBOX_TEMPLATE = "navbox_template"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TemplateInventoryEntry:
    """Ownership and usage information for one production template."""

    title: str
    ownership: OwnershipClass
    cutover_blocking: bool = False
    transclusion_count: int = 0
    transclusion_continued: bool = False
    examples: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class TemplateInventory:
    """Classified production template inventory."""

    entries: tuple[TemplateInventoryEntry, ...]
    generated_at: str | None = None


class InventoryClient(Protocol):
    def list_templates(self) -> list[str]: ...

    def embeddedin_summary(self, title: str) -> EmbeddedInSummary: ...


CUTOVER_PUBLIC_CONTRACTS = frozenset(
    {
        "Template:Item",
        "Template:Character",
        "Template:Quest",
        "Template:Ability",
        "Template:Zone",
        "Template:ItemLink",
        "Template:AbilityLink",
        "Template:QuestLink",
        "Template:MapLink",
    }
)

LEGACY_ENTITY_TEMPLATES = frozenset(
    {
        "Template:Armor",
        "Template:Auras",
        "Template:Book",
        "Template:Consumable",
        "Template:Dungeon",
        "Template:Enemy",
        "Template:Enemy Stats",
        "Template:Faction",
        "Template:Lore-book",
        "Template:Mold",
        "Template:Node",
        "Template:Off-hand",
        "Template:Pet",
        "Template:Stance",
        "Template:Weapon",
    }
)

HELPER_TEMPLATES = frozenset(
    {
        "Template:-",
        "Template:=",
        "Template:About",
        "Template:Cite web",
        "Template:Classes",
        "Template:Clear",
        "Template:Cols",
        "Template:Dialogue",
        "Template:Disambiguation",
        "Template:Documentation",
        "Template:For",
        "Template:Further",
        "Template:Game",
        "Template:Gear/EmptySlot",
        "Template:Gear/Grid",
        "Template:Gear/Guide",
        "Template:Gear/ProficiencyTable",
        "Template:Gear/Slot",
        "Template:Hatnote",
        "Template:Main",
        "Template:MessageBox",
        "Template:Namespace",
        "Template:Quote",
        "Template:See also",
        "Template:Space",
        "Template:SparkleIcon",
        "Template:Spoiler",
        "Template:Stub",
        "Template:T",
        "Template:Testing",
        "Template:Tl",
        "Template:Tocleft",
        "Template:Tocright",
        "Template:Topic",
        "Template:Trim",
        "Template:Update",
    }
)


def template_inventory_from_api(client: InventoryClient) -> TemplateInventory:
    """Read and classify production templates from MediaWiki."""
    entries: list[TemplateInventoryEntry] = []
    for title in client.list_templates():
        if title in CUTOVER_PUBLIC_CONTRACTS:
            summary = client.embeddedin_summary(title)
            entries.append(_entry_with_summary(classify_template(title), summary))
        else:
            entries.append(classify_template(title))
    return TemplateInventory(entries=tuple(sorted(entries, key=lambda entry: entry.title)))


def classify_template(
    title: str,
    *,
    transclusion_count: int = 0,
    continued: bool = False,
    examples: tuple[str, ...] = (),
) -> TemplateInventoryEntry:
    """Classify one template into the migration ownership model."""
    ownership = OwnershipClass.UNKNOWN
    cutover_blocking = False
    notes = ""

    if title.endswith("/doc"):
        ownership = OwnershipClass.DOCUMENTATION_TEMPLATE
    elif title.startswith("Template:License"):
        ownership = OwnershipClass.LICENSE_TEMPLATE
    elif "Navbox" in title:
        ownership = OwnershipClass.NAVBOX_TEMPLATE
    elif title in CUTOVER_PUBLIC_CONTRACTS:
        ownership = OwnershipClass.REPO_OWNED_TEMPLATE
        cutover_blocking = True
        notes = "root public compatibility template for the Lua cutover"
    elif title.startswith("Template:Item/") or title in LEGACY_ENTITY_TEMPLATES:
        ownership = OwnershipClass.LEGACY_TEMPLATE
        notes = "superseded by Lua-backed public templates after cutover"
    elif title in HELPER_TEMPLATES:
        ownership = OwnershipClass.HELPER_TEMPLATE

    return TemplateInventoryEntry(
        title=title,
        ownership=ownership,
        cutover_blocking=cutover_blocking,
        transclusion_count=transclusion_count,
        transclusion_continued=continued,
        examples=examples,
        notes=notes,
    )


def render_ownership_manifest(inventory: TemplateInventory) -> str:
    """Render deterministic YAML for `wiki/ownership.yml`."""
    lines = [
        "# Generated by `erenshor wiki inventory-templates`.",
        "# Review unknown entries before production cutover.",
        f"generated_at: {_yaml_scalar(inventory.generated_at)}",
        "templates:",
    ]
    for entry in inventory.entries:
        lines.extend(_entry_lines(entry))
    return "\n".join(lines) + "\n"


def _entry_with_summary(entry: TemplateInventoryEntry, summary: EmbeddedInSummary) -> TemplateInventoryEntry:
    return TemplateInventoryEntry(
        title=entry.title,
        ownership=entry.ownership,
        cutover_blocking=entry.cutover_blocking,
        transclusion_count=summary.total,
        transclusion_continued=summary.continued,
        examples=tuple(summary.examples),
        notes=entry.notes,
    )


def _entry_lines(entry: TemplateInventoryEntry) -> list[str]:
    lines = [
        f"  - title: {_yaml_scalar(entry.title)}",
        f"    ownership: {entry.ownership.value}",
        f"    cutover_blocking: {_yaml_bool(entry.cutover_blocking)}",
        f"    transclusion_count: {entry.transclusion_count}",
        f"    transclusion_continued: {_yaml_bool(entry.transclusion_continued)}",
    ]
    if entry.examples:
        lines.append("    examples:")
        lines.extend(f"      - {_yaml_scalar(example)}" for example in entry.examples)
    else:
        lines.append("    examples: []")
    if entry.notes:
        lines.append(f"    notes: {_yaml_scalar(entry.notes)}")
    return lines


def _yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _yaml_scalar(value: str | None) -> str:
    if value is None:
        return "null"
    if _is_plain_yaml_scalar(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _is_plain_yaml_scalar(value: str) -> bool:
    if not value:
        return False
    return all(char.isalnum() or char in ":/-_ .`" for char in value)
