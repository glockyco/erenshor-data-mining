"""Plain sentences for the ways of the requirement graph."""

from __future__ import annotations

import pytest

from erenshor.application.progression_wording import ProgressionSentences, ProgressionWordingError
from erenshor.domain.value_objects.progression import ProgressionNeed, ProgressionNode, ProgressionWay

ROOMS = ("L1", "L2", "R1", "R2")


def need(
    relation: str,
    key: str | None = None,
    *,
    quantity: float | None = None,
    slot: str | None = None,
    keywords: str | None = None,
    condition: str | None = None,
    level: int | None = None,
) -> ProgressionNeed:
    return ProgressionNeed(relation, key, quantity, slot, keywords, condition, False, False, level)


NODES = {
    "zone:desert": ("zone", "Desert"),
    "zone:port": ("zone", "Port"),
    "zone:home": ("zone", "Home"),
    "character:boss": ("character", "Boss"),
    "character:giver": ("character", "Giver"),
    "character:smith": ("character", "Smith"),
    "character:ward:1": ("character", "Ward"),
    "character:ward:2": ("character", "Ward"),
    "character:vendor:L1": ("character", "Vendor"),
    "character:vendor:L2": ("character", "Vendor"),
    "character:vendor:R1": ("character", "Vendor"),
    "character:vendor:R2": ("character", "Vendor"),
    "item:key": ("item", "Key"),
    "item:stone": ("item", "Stone"),
    "item:ring": ("item", "Ring"),
    "item:bread": ("item", "Bread"),
    "item:furniture": ("item", "Vendor Set"),
    "item:prize": ("item", "Prize"),
    "quest:ring": ("quest", "Ring Quest"),
    "quest:later": ("quest", "Later Quest"),
    "quest:first": ("quest", "First Quest"),
    "quest:chain": ("quest", "Chain Quest"),
    "quest_start:quest:ring": ("quest_start", "Start of Ring Quest"),
    "quest_start:quest:chain": ("quest_start", "Start of Chain Quest"),
    "world_state:weather:raining:zone:desert": ("world_state", "Rain in Desert"),
    "spell:storm": ("spell", "Storm"),
    "barrier:gate": ("barrier", "Gate"),
}


def graph(
    ways: dict[str, list[list[ProgressionNeed]]], extra: dict[str, tuple[str, str]] | None = None
) -> ProgressionSentences:
    """Every node with the given ways. A node's first way is its first listed way."""
    located = {key: [[need("in zone", "zone:port")]] for key, (kind, _) in NODES.items() if kind == "character"}
    located["character:boss"] = [[need("in zone", "zone:desert")]]
    merged = {**located, **ways}
    nodes = {
        key: ProgressionNode(key, kind, name, True, 1, "w0" if merged.get(key) else None)
        for key, (kind, name) in {**NODES, **(extra or {})}.items()
    }
    return ProgressionSentences(
        nodes,
        {
            key: tuple(ProgressionWay(f"w{index}", tuple(needs)) for index, needs in enumerate(entries))
            for key, entries in merged.items()
        },
        {"faction:elders": "The Elders"},
    )


def test_a_drop_names_the_dropper_its_zone_and_the_rain_that_releases_it():
    sentences = graph(
        {"item:key": [[need("drops", "character:boss"), need("release", "world_state:weather:raining:zone:desert")]]}
    )

    assert sentences.sentences("item:key") == (
        "Defeat {character:boss} in {zone:desert} for {item:key}, while it rains in {zone:desert}.",
    )


def test_a_quest_names_its_start_and_places_each_character_once():
    sentences = graph(
        {
            "quest_start:quest:ring": [[need("talk to", "character:giver", keywords="ring, Ring")]],
            "quest:ring": [
                [
                    need("started", "quest_start:quest:ring"),
                    need("required item", "item:stone", quantity=1, slot="1"),
                    need("required item", "item:stone", quantity=1, slot="2"),
                    need("turn in to", "character:smith"),
                ],
                [
                    need("started", "quest_start:quest:ring"),
                    need("required item", "item:stone"),
                    need("turn in to", "character:giver"),
                ],
            ],
        }
    )

    other, same = sentences.sentences("quest:ring")
    assert other == (
        'Talk to {character:giver} in {zone:port} and say "ring" to start {quest:ring}, '
        "then give 2 {item:stone} to {character:smith} in {zone:port} to finish it."
    )
    assert same.endswith("then give {item:stone} to {character:giver} to finish it.")


def test_a_reward_names_only_its_quest_and_folds_into_it():
    sentences = graph(
        {
            "quest:ring": [[need("required item", "item:stone"), need("turn in to", "character:smith")]],
            "item:ring": [
                [need("reward", "quest:ring"), need("held", "item:stone"), need("quest not done", "quest:ring")],
            ],
            "item:prize": [[need("reward", "quest:ring"), need("held", "item:bread")]],
        }
    )

    assert sentences.sentences("item:ring") == ("Finish {quest:ring} for {item:ring}.",)
    assert sentences.reward_of("item:ring") == "quest:ring"
    # A held item that the quest does not take is a condition of its own.
    assert sentences.sentences("item:prize") == ("Finish {quest:ring} for {item:prize}, while you carry {item:bread}.",)
    assert sentences.reward_of("item:prize") is None


def test_a_quest_to_leave_undone_reads_as_a_condition():
    sentences = graph({"item:key": [[need("gives", "character:giver"), need("quest not done", "quest:later")]]})

    assert sentences.sentences("item:key") == (
        "Get {item:key} from {character:giver} in {zone:port}, before you finish {quest:later}.",
    )


def test_furnished_rooms_merge_into_any_room_only_when_every_room_is_listed():
    every_room = [
        [
            need("sells", f"character:vendor:{room}"),
            need("room furnished", "item:furniture", slot=room),
            need("quest done", "quest:first"),
        ]
        for room in ROOMS
    ]
    sentences = graph({"item:bread": every_room, "item:prize": every_room[:2]})

    assert set(sentences.sentences("item:bread")) == {
        "Buy {item:bread} from {character:vendor:L1} in {zone:port}, after {quest:first}, "
        "with {item:furniture} furnished in any room of your Reliquary.",
        "Buy {item:bread} from {character:vendor:L2} in {zone:port}, after {quest:first}, "
        "with {item:furniture} furnished in any room of your Reliquary.",
        "Buy {item:bread} from {character:vendor:R1} in {zone:port}, after {quest:first}, "
        "with {item:furniture} furnished in any room of your Reliquary.",
        "Buy {item:bread} from {character:vendor:R2} in {zone:port}, after {quest:first}, "
        "with {item:furniture} furnished in any room of your Reliquary.",
    }
    assert all(
        sentence.endswith("with {item:furniture} furnished in room L1 or L2 of your Reliquary.")
        for sentence in sentences.sentences("item:prize")
    )


def test_copies_that_share_a_name_read_as_one_name_with_their_count():
    sentences = graph(
        {
            "item:key": [
                [
                    need("drops", "character:boss"),
                    need("release", "character:ward:1"),
                    need("defeated", "character:ward:2"),
                ]
            ],
            "barrier:gate": [[need("defeated", "character:ward:1", quantity=3)]],
        }
    )

    # Both wards read as one name, so either copy may stand for it.
    assert sentences.sentences("item:key")[0].endswith("after you defeat both {character:ward:2}.")
    assert sentences.sentences("barrier:gate") == ("Defeat all 3 {character:ward:1} to get past {barrier:gate}.",)


def test_a_start_after_a_quest_does_not_repeat_that_quest():
    sentences = graph(
        {
            "quest_start:quest:chain": [[need("after", "quest:first")]],
            "quest:chain": [
                [
                    need("started", "quest_start:quest:chain"),
                    need("quest done", "quest:first"),
                    need("talk to", "character:giver"),
                ]
            ],
        }
    )

    assert sentences.sentences("quest:chain") == (
        "After {quest:first}, talk to {character:giver} in {zone:port} to finish {quest:chain}.",
    )


def test_levels_above_one_are_named():
    sentences = graph(
        {
            "spell:storm": [[need("teaches", "item:stone", level=8)], [need("teaches", "item:stone", level=1)]],
        }
    )

    assert sentences.sentences("spell:storm") == (
        "Learn {spell:storm} from {item:stone} of level 8 or higher.",
        "Learn {spell:storm} from {item:stone}.",
    )


def test_a_way_without_needs_needs_nothing():
    assert graph({"item:key": [[]]}).sentences("item:key") == ("Nothing is needed.",)


@pytest.mark.parametrize(
    ("ways", "message"),
    [
        ({"item:key": [[need("bargain", "character:giver")]]}, "item:key way w0"),
        ({"item:key": [[need("drops", "character:boss"), need("bargain", "character:giver")]]}, "bargain"),
    ],
)
def test_a_relation_without_wording_fails(ways, message):
    with pytest.raises(ProgressionWordingError, match=message):
        graph(ways).sentences("item:key")


def test_a_world_state_other_than_rain_fails():
    fog = "world_state:fog:zone:desert"
    sentences = graph({fog: [[need("in zone", "zone:desert")]]}, {fog: ("world_state", "Fog in Desert")})

    with pytest.raises(ProgressionWordingError, match="Cannot word world state"):
        sentences.sentences(fog)


def test_a_stable_key_with_a_brace_fails():
    odd = "item:{odd}"
    sentences = graph({odd: [[need("drops", "character:boss")]]}, {odd: ("item", "Odd")})

    with pytest.raises(ProgressionWordingError, match="brace"):
        sentences.sentences(odd)
