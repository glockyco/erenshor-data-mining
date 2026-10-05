from __future__ import annotations

from erenshor.application.wiki.chat_knowledge import ChatKnowledge, KnowledgeEntry, normalize_chat_name


def _entry(
    position: int, name: str, zone: str | None, drops: tuple[str, ...] = (), keys: tuple[str, ...] = ()
) -> KnowledgeEntry:
    return KnowledgeEntry(
        position=position,
        npc_name=name,
        zone_name=zone,
        level=10,
        is_boss=False,
        prefab_path=f"NPCs/{name}",
        drops=drops,
        character_keys=keys,
    )


def test_chat_names_an_entry_unprompted_only_with_a_name_and_a_zone() -> None:
    assert _entry(0, "Holy Corpse", "Fernalla's Revival Plains").named_unprompted
    assert not _entry(1, "Bazxzoth", None).named_unprompted
    assert not _entry(2, "", "The Blight").named_unprompted


def test_chat_names_only_the_first_entry_that_drops_an_item_as_its_source() -> None:
    knowledge = ChatKnowledge(
        [
            _entry(0, "Ancient Sentinel", "The Blight", ("Blight Crystals", "Ancient Bone", "Blight Crystals")),
            _entry(1, "A Brittle Skeleton", "Port Azure", ("Ancient Bone", "Rusty Shortsword")),
        ]
    )

    assert knowledge.items_named_as_source(knowledge.entries[0]) == ("Blight Crystals", "Ancient Bone")
    assert knowledge.items_named_as_source(knowledge.entries[1]) == ("Rusty Shortsword",)


def test_entries_are_found_by_every_linked_character() -> None:
    twin = _entry(0, "Leo McLaney", "Stowaway's Step", keys=("character:leo mclaney", "character:leo mclaney:1"))
    knowledge = ChatKnowledge([twin])

    assert knowledge.entries_for_character("character:leo mclaney:1") == (twin,)
    assert knowledge.entries_for_character("character:someone else") == ()


def test_names_are_compared_as_chat_stores_them() -> None:
    assert normalize_chat_name("Summoned: Elder Dryad") == "summoned elder dryad"
    assert normalize_chat_name("Fernalla's Guardian Golem") == "fernallas guardian golem"
    assert normalize_chat_name(None) == ""
