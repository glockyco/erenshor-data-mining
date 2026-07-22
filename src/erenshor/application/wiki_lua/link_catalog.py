"""Build the deterministic semantic-link identity catalog for wiki Lua data."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeGuard, TypeVar

from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.domain.entities.item_kind import classify_item_kind

if TYPE_CHECKING:
    from erenshor.domain.entities.character import Character
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.quest import Quest
    from erenshor.domain.entities.skill import Skill
    from erenshor.domain.entities.spell import Spell
    from erenshor.domain.entities.stance import Stance
    from erenshor.domain.entities.zone import Zone

LuaData = dict[str, object]


@dataclass(frozen=True, slots=True)
class LinkCatalogEntry:
    """One immutable semantic identity record.

    These six primitive fields are the sole payload used in the generated
    catalog and its digest.  ``None`` is meaningful for subtype and image.
    """

    key: str
    kind: str
    subtype: str | None
    name: str
    page: str
    image: str | None

    def primitive(self) -> dict[str, object]:
        """Return the canonical six-field primitive representation."""
        return {
            "key": self.key,
            "kind": self.kind,
            "subtype": self.subtype,
            "name": self.name,
            "page": self.page,
            "image": self.image,
        }


class _LinkEntity(Protocol):
    @property
    def stable_key(self) -> str: ...

    @property
    def display_name(self) -> str | None: ...

    @property
    def wiki_page_name(self) -> str | None: ...

    @property
    def image_name(self) -> str | None: ...


_EntityT = TypeVar("_EntityT", bound=_LinkEntity)


class ItemDataRepository(Protocol):
    def get_items_for_wiki_generation(self) -> Sequence[Item]: ...

    def get_items_for_link_catalog(self) -> Sequence[Item]: ...


class CharacterDataRepository(Protocol):
    def get_characters_for_wiki_generation(self) -> Sequence[Character]: ...


class QuestDataRepository(Protocol):
    def get_quests_for_wiki_generation(self) -> Sequence[Quest]: ...


class ZoneDataRepository(Protocol):
    def get_all_zones(self) -> Sequence[Zone]: ...


class SpellDataRepository(Protocol):
    def get_spells_for_wiki_generation(self) -> Sequence[Spell]: ...


class SkillDataRepository(Protocol):
    def get_skills_for_wiki_generation(self) -> Sequence[Skill]: ...


class StanceDataRepository(Protocol):
    def get_all(self) -> Sequence[Stance]: ...


class FactionDataRepository(Protocol):
    def get_factions_for_wiki_generation(self) -> Sequence[_LinkEntity]: ...


class ClassDisplayNameService(Protocol):
    def get_all_internal_names(self) -> Sequence[str]: ...

    def get_display_name(self, class_name: str) -> str: ...


_SUPPORTED_KINDS = {"item", "ability", "character", "quest", "zone", "faction", "class"}
_PREFIXES = {
    "item": ("item:",),
    "ability": ("spell:", "skill:", "stance:"),
    "character": ("character:",),
    "quest": ("quest:",),
    "zone": ("zone:",),
    "faction": ("faction:",),
    "class": ("class:",),
}


def class_stable_key(internal_name: str) -> str:
    """Return the canonical identity key for a game-internal class name."""
    normalized_name = internal_name.strip()
    if not normalized_name:
        raise ValueError("Class identity requires a nonblank internal name")
    return f"class:{normalized_name.casefold()}"


def build_link_catalog_entries(
    *,
    items: Iterable[Item],
    characters: Iterable[Character],
    quests: Iterable[Quest],
    zones: Iterable[Zone],
    spells: Iterable[Spell],
    skills: Iterable[Skill],
    stances: Iterable[Stance],
    factions: Iterable[_LinkEntity],
    class_display: ClassDisplayNameService,
) -> tuple[LinkCatalogEntry, ...]:
    """Build and validate all seven semantic families.

    A record excluded from wiki article generation is represented by a null
    page and is intentionally skipped.  Every other malformed identity fails
    immediately rather than producing a partially usable catalog.
    """
    entries: list[LinkCatalogEntry] = []
    entries.extend(_entity_entries(items, "item", _item_subtype))
    entries.extend(_entity_entries(spells, "ability", lambda _: "spell"))
    entries.extend(_entity_entries(skills, "ability", lambda _: "skill"))
    entries.extend(_entity_entries(stances, "ability", lambda _: "stance"))
    entries.extend(_entity_entries(characters, "character", _character_subtype))
    entries.extend(_entity_entries(quests, "quest", lambda _: None))
    entries.extend(_entity_entries(zones, "zone", _zone_subtype))
    entries.extend(_entity_entries(factions, "faction", lambda _: None))

    for class_name in class_display.get_all_internal_names():
        display_name = class_display.get_display_name(class_name)
        entries.append(
            LinkCatalogEntry(
                key=class_stable_key(class_name),
                kind="class",
                subtype=None,
                name=display_name,
                page=display_name,
                image=None,
            )
        )

    _validate_entries(entries)
    return tuple(sorted(entries, key=_entry_sort_key))


def _is_nonblank_string(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip())


def _entity_entries(
    entities: Iterable[_EntityT],
    kind: str,
    subtype_fn: Callable[[_EntityT], str | None],
) -> list[LinkCatalogEntry]:
    result: list[LinkCatalogEntry] = []
    for entity in entities:
        page = entity.wiki_page_name
        if page is None:
            continue
        stable_key = entity.stable_key
        name = entity.display_name
        if not _is_nonblank_string(stable_key):
            raise ValueError(f"Blank link catalog key for {stable_key!r}")
        if not _is_nonblank_string(name):
            raise ValueError(f"Blank link catalog name for {stable_key!r}")
        if not _is_nonblank_string(page):
            raise ValueError(f"Blank link catalog page for {stable_key!r}")
        subtype = subtype_fn(entity)
        result.append(
            LinkCatalogEntry(
                key=stable_key,
                kind=kind,
                subtype=subtype,
                name=name,
                page=page,
                image=entity.image_name,
            )
        )
    return result


def _item_subtype(item: Item) -> str:
    return str(
        classify_item_kind(
            required_slot=item.required_slot,
            teach_spell=item.teach_spell_stable_key,
            teach_skill=item.teach_skill_stable_key,
            template_flag=item.template,
            click_effect=item.item_effect_on_click_stable_key,
            disposable=None if item.disposable is None else bool(item.disposable),
        )
    )


def _character_subtype(character: Character) -> str:
    if character.is_friendly:
        return "NPC"
    if character.is_unique:
        return "Boss"
    if character.is_rare and not character.is_common:
        return "Rare"
    return "Enemy"


def _zone_subtype(zone: Zone) -> str:
    return "Dungeon" if zone.is_dungeon else "Zone"


def _entry_sort_key(entry: LinkCatalogEntry) -> tuple[str, str, str, str]:
    return (entry.name.casefold(), entry.kind, entry.subtype or "", entry.key)


def _validate_entries(entries: Iterable[LinkCatalogEntry]) -> None:
    seen: set[str] = set()
    for entry in entries:
        if entry.kind not in _SUPPORTED_KINDS:
            raise ValueError(f"Unsupported link catalog kind: {entry.kind!r}")
        for field_name, value in (
            ("key", entry.key),
            ("name", entry.name),
            ("page", entry.page),
        ):
            if not _is_nonblank_string(value):
                raise ValueError(f"Blank link catalog {field_name} for {entry.key!r}")
        if entry.subtype is not None and not _is_nonblank_string(entry.subtype):
            raise ValueError(f"Blank link catalog subtype for {entry.key!r}")
        if entry.key in seen:
            raise ValueError(f"Duplicate link catalog key: {entry.key}")
        seen.add(entry.key)
        if not any(entry.key.startswith(prefix) for prefix in _PREFIXES[entry.kind]):
            raise ValueError(f"Link catalog key {entry.key!r} has wrong prefix for kind {entry.kind!r}")


def build_links_data(entries: Iterable[LinkCatalogEntry]) -> LuaData:
    """Build the ``Data/Links`` table from validated entries."""
    ordered = tuple(sorted(entries, key=_entry_sort_key))
    _validate_entries(ordered)
    primitives = [entry.primitive() for entry in ordered]
    payload = json.dumps(primitives, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    by_key = {
        key: entry.primitive()
        for key, entry in sorted(((entry.key, entry) for entry in ordered), key=lambda pair: pair[0])
    }
    by_page: dict[str, list[str]] = {}
    for entry in ordered:
        by_page.setdefault(entry.page, []).append(entry.key)
    by_page = {page: sorted(keys) for page, keys in sorted(by_page.items())}
    return {
        "schemaVersion": 1,
        "catalogSha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "byKey": by_key,
        "byPage": by_page,
        "entries": primitives,
    }


def generate_links_module(
    item_repo: ItemDataRepository,
    character_repo: CharacterDataRepository,
    quest_repo: QuestDataRepository,
    zone_repo: ZoneDataRepository,
    spell_repo: SpellDataRepository,
    skill_repo: SkillDataRepository,
    stance_repo: StanceDataRepository,
    faction_repo: FactionDataRepository,
    class_display: ClassDisplayNameService,
) -> str:
    """Generate ``Module:Erenshor/Data/Links`` Lua source."""
    entries = build_link_catalog_entries(
        items=item_repo.get_items_for_link_catalog(),
        characters=character_repo.get_characters_for_wiki_generation(),
        quests=quest_repo.get_quests_for_wiki_generation(),
        zones=zone_repo.get_all_zones(),
        spells=spell_repo.get_spells_for_wiki_generation(),
        skills=skill_repo.get_skills_for_wiki_generation(),
        stances=stance_repo.get_all(),
        factions=faction_repo.get_factions_for_wiki_generation(),
        class_display=class_display,
    )
    return module_text(build_links_data(entries))


def write_links_module(
    item_repo: ItemDataRepository,
    character_repo: CharacterDataRepository,
    quest_repo: QuestDataRepository,
    zone_repo: ZoneDataRepository,
    spell_repo: SpellDataRepository,
    skill_repo: SkillDataRepository,
    stance_repo: StanceDataRepository,
    faction_repo: FactionDataRepository,
    class_display: ClassDisplayNameService,
    output_root: Path,
) -> Path:
    """Write ``Data/Links.lua`` below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "Links.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = output_path.write_text(
        generate_links_module(
            item_repo,
            character_repo,
            quest_repo,
            zone_repo,
            spell_repo,
            skill_repo,
            stance_repo,
            faction_repo,
            class_display,
        ),
        encoding="utf-8",
    )
    return output_path
