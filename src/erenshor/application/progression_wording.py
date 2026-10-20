"""Player wording shared by progression readers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.domain.value_objects.progression import ProgressionNeed, ProgressionNode, ProgressionWay

WORDING = {
    "event:": "Scripted event",
    "release:health_phase_timer:": "Becomes vulnerable after a health phase timer",
    "release:spawn_health_phase_timer:": "Becomes vulnerable after a spawn health phase timer",
    "release:combat_empty_wards:": "Becomes vulnerable in combat when no wards remain",
    "mechanic:new_character_start": "New character start",
    "mechanic:alternate_start": "Alternate start",
    "mechanic:common_world_item": "Common world items",
    "mechanic:special_world_drop": "World drops",
    "ui:planningtableui": "Planning table",
    "ui:replenishtmoghide": "Cosmetic slot",
    "barrier": "{name}",
    "account_state:reliquary_claimed:false": "Reliquary not claimed by this account",
    "account_state:reliquary_claimed:true": "Reliquary claimed by this account",
    "world_state:weather:raining:": "Rain in {name}",
    "weather:natural_rain": "Wait for natural rain",
    "faction_standing:positive": "Positive standing with {name}",
    "faction_standing:non_negative": "Standing of zero or more with {name}",
}

# What the player does with a need on the way to the node that needs it. The map
# labels each of its lines with the action of the line's need. A "relation|kind"
# entry applies when the need is a node of that kind.
ACTIONS = {
    "after": "finish",
    "barrier": "get past",
    "cast": "cast",
    "casts": "use",
    "class": "play as",
    "contained in": "open",
    "converted from": "use",
    "created by": "use",
    "defeat": "defeat",
    "defeated": "defeat",
    "drops": "defeat",
    "enter": "enter",
    "entered from": "come from",
    "equipped": "wear",
    "event": "visit",
    "fished in": "fish in",
    "found in": "search",
    "from": "use",
    "from|class": "play as",
    "gives": "ask",
    "hear": "listen to",
    "held": "carry",
    "in zone": "go to",
    "key": "open with",
    "material": "craft from",
    "mined in": "mine in",
    "mold": "craft with",
    "natural weather": "wait",
    "planning slot": "place",
    "quest active": "keep active",
    "quest done": "finish",
    "quest not done": "keep undone",
    "read": "read",
    "release": "defeat",
    "release|item": "give",
    "release|world_state": "bring",
    "required item": "give",
    "reward": "finish",
    "room furnished": "furnish",
    "sells": "buy from",
    "standing": "gain",
    "started": "start",
    "state": "need",
    "summoned by": "wait for",
    "summoned with": "summon with",
    "talk to": "talk to",
    "teaches": "learn from",
    "turn in to": "give to",
    "zone line": "travel from",
}

# How the route titles a chapter or a part that ends with a node of each kind.
LEADS = {
    "barrier": "Get past {name}",
    "character": "Find {name}",
    "faction_standing": "Gain {name}",
    "item": "Get {name}",
    "quest": "Finish {name}",
    "world_state": "Bring {name}",
    "zone": "Unlock {name}",
}


class ProgressionWordingError(ValueError):
    """A typed progression key has no player wording."""


def condition_text(key: str) -> str:
    """Word a supported condition family and reject unknown keys."""
    if key == "weather:natural_rain":
        return WORDING[key]
    for prefix in (
        "event:",
        "release:health_phase_timer:",
        "release:spawn_health_phase_timer:",
        "release:combat_empty_wards:",
    ):
        if key.startswith(prefix) and key.removeprefix(prefix):
            return WORDING[prefix]
    raise ProgressionWordingError(f"Cannot word progression condition: {key!r}")


def standing_text(key: str, names: Mapping[str, str]) -> str:
    """Word a faction standing by the name of its faction."""
    faction, required = _standing(key)
    template = WORDING.get("faction_standing:" + required)
    name = names.get("faction:" + faction)
    if template is None or not name:
        raise ProgressionWordingError(f"Cannot word progression faction standing: {key!r}")
    return template.format(name=name)


def node_text(node: ProgressionNode, names: Mapping[str, str]) -> str:
    """Word a noncatalog node without substituting a raw stable key."""
    key = node.stable_key
    if key in WORDING:
        return WORDING[key]
    if node.kind == "barrier" and node.name != key:
        return WORDING["barrier"].format(name=node.name)
    if node.kind == "world_state" and key.startswith("world_state:weather:raining:"):
        zone = key.removeprefix("world_state:weather:raining:")
        if zone in names:
            return WORDING["world_state:weather:raining:"].format(name=names[zone])
    if node.kind == "faction_standing":
        return standing_text(key, names)
    if node.kind == "mechanism" and key.startswith("ui:"):
        wording_key = _mechanism(key)
        if wording_key in WORDING:
            return WORDING[wording_key]
    raise ProgressionWordingError(f"Cannot word progression {node.kind}: {key!r}")


def _standing(key: str) -> tuple[str, str]:
    faction, _, required = key.removeprefix("faction_standing:").rpartition(":")
    return faction, required


def _mechanism(key: str) -> str:
    """Name the family of a mechanism key, such as ui:planningtableui for one planning table."""
    if key.startswith("ui:"):
        parts = key.rsplit(":", 2)
        return "ui:" + parts[-2] if len(parts) == 3 else key
    return key


# Main clauses that name one need. {node} is the node that the way leads to,
# {need} the need, {place} the zone where a character need is found, {keywords}
# what to say to it, and {count} how many of it to defeat. The first relation of
# a table that a way holds leads its sentence.
_ITEM_CLAUSES = {
    "reward": "finish {need} for {node}",
    "drops": "defeat {need}{place} for {node}",
    "sells": "buy {node} from {need}{place}",
    "gives": "get {node} from {need}{place}",
    "found in": "pick up {node} in {need}",
    "fished in": "fish {node} in {need}",
    "mined in": "mine {node} in {need}",
    "contained in": "open {need} for {node}",
    "created by": "use {need} to create {node}",
}
_COMPLETIONS = {
    "talk to": "talk to {need}{place}{keywords}",
    "read": "read {need}",
    "enter": "enter {need}",
    "defeat": "defeat {count}{need}{place}",
    "defeated": "defeat {count}{need}{place}",
    "hear": "listen to {need}{place}",
}
_OPENINGS = {
    "talk to": "talk to {need}{place}{keywords}",
    "read": "read {need}",
    "enter": "enter {need}",
}
_BARRIER_CLAUSES = {
    "key": "open {node} with {need}",
    "held": "carry {need} to get past {node}",
}
_SPELL_CLAUSES = {"casts": "use {need} to cast {node}"}
# A way whose source is a mechanism.
_FROM_MECHANISM = {
    "mechanic:common_world_item": "pick up {node} where it lies in the world",
    "mechanic:special_world_drop": "pick up {node} as a world drop",
    "mechanic:new_character_start": "start a new character in {node}",
    "mechanic:alternate_start": "choose the alternate start to begin in {node}",
    "ui:planningtableui": "get {node} at the planning table",
    "ui:replenishtmoghide": "get {node} from the cosmetic slot",
}
# What a mechanism is called in a sentence about the mechanism itself.
_MECHANISM_NOUNS = {"ui:planningtableui": "the planning table", "ui:replenishtmoghide": "the cosmetic slot"}
# An account state as a condition, the goal of a way that reaches it, and how an account starts.
_ACCOUNT_STATES = {
    "account_state:reliquary_claimed:true": "once this account has claimed the Reliquary",
    "account_state:reliquary_claimed:false": "while this account has not claimed the Reliquary",
}
_ACCOUNT_GOALS = {"account_state:reliquary_claimed:true": "claim the Reliquary on this account"}
_ACCOUNT_STARTS = {"account_state:reliquary_claimed:false": "every account starts without a claimed Reliquary"}
_STANDING_LEVELS = {"positive": "above zero", "non_negative": "to zero or more"}
_STANDING_CONDITIONS = {"positive": "is positive", "non_negative": "is zero or more"}
_RAIN = "world_state:weather:raining:"
# Conditions that list their needs: the phrase and the word that joins the needs.
_LIST_CONDITIONS = {
    "barrier": ("past {needs}", "and"),
    "quest done": ("after {needs}", "and"),
    "quest not done": ("before you finish {needs}", "or"),
    "equipped": ("while you wear {needs}", "and"),
    "summoned by": ("when {needs} summons it", "or"),
    "in zone": ("in {needs}", "and"),
}
# Conditions follow the main clause in this order. Defeats include the
# characters whose death releases another.
_CONDITION_ORDER = (
    "barrier",
    "quest done",
    "quest not done",
    "quest active",
    "held",
    "equipped",
    "room furnished",
    "summoned by",
    "defeated",
    "release",
    "state",
    "standing",
    "in zone",
)

Needs = dict[str, list["ProgressionNeed"]]


def _ref(key: str | None) -> str:
    if key is None:
        raise ProgressionWordingError("A sentence names a need without a node")
    if "{" in key or "}" in key:
        raise ProgressionWordingError(f"Stable key holds a brace: {key!r}")
    return "{" + key + "}"


def _join(parts: Sequence[str], conjunction: str = "and") -> str:
    if len(parts) < 3:
        return f" {conjunction} ".join(parts)
    return ", ".join(parts[:-1]) + f" {conjunction} " + parts[-1]


def _count(value: float | None) -> str:
    if value is None or value <= 1:
        return ""
    return f"{value:g} "


def _keywords(need: ProgressionNeed) -> str:
    """What to say to a character, each spoken word once."""
    if not need.keywords:
        return ""
    words: list[str] = []
    for spoken in need.keywords.split(","):
        word = spoken.strip()
        if word and word.lower() not in {seen.lower() for seen in words}:
            words.append(word)
    return " and say " + _join([f'"{word}"' for word in words], "or")


def _grouped(needs: Sequence[ProgressionNeed]) -> Needs:
    taken: Needs = defaultdict(list)
    for need in needs:
        taken[need.relation].append(need)
    return taken


class ProgressionSentences:
    """Word each way of the requirement graph as one imperative sentence.

    A node appears as its stable key in braces. A renderer replaces it with the
    node's label, so that the sentence links what it names.
    """

    def __init__(
        self,
        nodes: Mapping[str, ProgressionNode],
        ways: Mapping[str, Sequence[ProgressionWay]],
        names: Mapping[str, str],
    ) -> None:
        self._nodes = nodes
        self._ways = ways
        self._names = names
        self._rooms = frozenset(
            need.slot
            for node_ways in ways.values()
            for way in node_ways
            for need in way.needs
            if need.relation == "room furnished" and need.slot
        )
        # Each furnished room has its own copy of a character, such as a vendor, under one name.
        self._copies: dict[tuple[str, str], list[str]] = defaultdict(list)
        for key, node in sorted(nodes.items()):
            self._copies[node.kind, node.name].append(key)
        self._writers = {
            "item": self._item,
            "quest": self._quest,
            "quest_start": self._quest_start,
            "zone": self._zone,
            "barrier": self._barrier,
            "character": self._character,
            "world_state": self._world_state,
            "faction_standing": self._faction_standing,
            "account_state": self._account_state,
            "spell": self._spell,
            "mechanism": self._mechanism,
        }

    def sentences(self, key: str) -> tuple[str, ...]:
        """Return the sentence of each way of a node, in the order of its ways."""
        node = self._node(key)
        ways = self._ways.get(key, ())
        copies = self._copies[node.kind, node.name] if node.kind == "character" else [key]
        rooms = self._room_sets([(copy, way) for copy in copies for way in self._ways.get(copy, ())])
        sentences = []
        for way in ways:
            try:
                sentences.append(self._sentence(node, way, rooms[key, way.way_key]))
            except ProgressionWordingError as error:
                raise ProgressionWordingError(f"{key} way {way.way_key}: {error}") from error
        return tuple(sentences)

    def reward_of(self, key: str) -> str | None:
        """The quest of an item whose first way is that quest's reward and what the reward implies."""
        node = self._node(key)
        way = self._first_way(key)
        if node.kind != "item" or way is None:
            return None
        needs = self._unimplied(node, way.needs)
        if len(needs) == 1 and needs[0].relation == "reward":
            return needs[0].need_stable_key
        return None

    # Lookups

    def _node(self, key: str) -> ProgressionNode:
        node = self._nodes.get(key)
        if node is None:
            raise ProgressionWordingError(f"Unknown progression node: {key!r}")
        return node

    def _first_way(self, key: str) -> ProgressionWay | None:
        first = self._node(key).first_way_key
        return next((way for way in self._ways.get(key, ()) if way.way_key == first), None)

    def _kind(self, need: ProgressionNeed) -> str | None:
        return self._node(need.need_stable_key).kind if need.need_stable_key else None

    def _place(self, key: str) -> str:
        """Where a character is found: the zone of its first way."""
        if self._node(key).kind != "character":
            return ""
        way = self._first_way(key)
        zone = next((need.need_stable_key for need in way.needs if need.relation == "in zone"), None) if way else None
        return f" in {_ref(zone)}" if zone else ""

    def _room_sets(self, ways: Sequence[tuple[str, ProgressionWay]]) -> dict[tuple[str, str], frozenset[str]]:
        """The furnished rooms of each way of each node, merged across ways that read alike apart from the room.

        Each room has its own copy of a furnished vendor, so ways compare the names of their needs, and
        the copies of one character share their rooms.
        """
        groups: dict[tuple[tuple[object, ...], ...], list[tuple[str, ProgressionWay]]] = defaultdict(list)
        for owner, way in ways:
            groups[tuple(sorted((self._shape(need) for need in way.needs), key=repr))].append((owner, way))
        rooms: dict[tuple[str, str], frozenset[str]] = {}
        for group in groups.values():
            slots = frozenset(
                need.slot for _, way in group for need in way.needs if need.relation == "room furnished" and need.slot
            )
            rooms.update(((owner, way.way_key), slots) for owner, way in group)
        return rooms

    def _shape(self, need: ProgressionNeed) -> tuple[object, ...]:
        """How a need reads: the name of its node instead of its key, and no room."""
        return (
            need.relation,
            self._node(need.need_stable_key).name if need.need_stable_key else need.condition_key,
            need.quantity,
            None if need.relation == "room furnished" else need.slot,
            need.keywords,
            need.advisory,
            need.unconfirmed,
            need.required_level,
        )

    def _unimplied(self, node: ProgressionNode, needs: Sequence[ProgressionNeed]) -> list[ProgressionNeed]:
        """Leave out the needs that another need of the way implies."""
        kept = list(needs)
        reward = next((need.need_stable_key for need in kept if need.relation == "reward"), None)
        if reward is not None:
            # A reward comes with the quest, so the quest is undone until then and takes its turn-in items.
            turned_in = {
                need.need_stable_key
                for way in self._ways.get(reward, ())
                for need in way.needs
                if need.relation == "required item"
            }
            kept = [
                need
                for need in kept
                if not (need.relation == "quest not done" and need.need_stable_key == reward)
                and not (need.relation == "held" and need.need_stable_key in turned_in)
            ]
        if node.kind == "quest_start":
            # A quest starts only while it is undone.
            quest = node.stable_key.removeprefix("quest_start:")
            kept = [need for need in kept if not (need.relation == "quest not done" and need.need_stable_key == quest)]
        return kept

    # Sentences

    def _sentence(self, node: ProgressionNode, way: ProgressionWay, rooms: frozenset[str]) -> str:
        needs = self._unimplied(node, way.needs)
        if not needs:
            text = _ACCOUNT_STARTS.get(node.stable_key, "nothing is needed")
        else:
            writer = self._writers.get(node.kind)
            if writer is None:
                raise ProgressionWordingError(f"Cannot word a way of a {node.kind}")
            taken = _grouped(needs)
            text = writer(node, taken) + self._conditions(taken, rooms)
            if any(need.unconfirmed for need in needs):
                text += " (not confirmed in play)"
        return text[:1].upper() + text[1:] + "."

    @staticmethod
    def _take(taken: Needs, relation: str) -> list[ProgressionNeed]:
        return taken.pop(relation, [])

    @staticmethod
    def _one(taken: Needs, relation: str) -> ProgressionNeed | None:
        needs = taken.pop(relation, [])
        if len(needs) > 1:
            raise ProgressionWordingError(f"Cannot word {len(needs)} needs of relation {relation!r} in one way")
        return needs[0] if needs else None

    def _need(self, taken: Needs, relation: str) -> ProgressionNeed:
        need = self._one(taken, relation)
        if need is None:
            raise ProgressionWordingError(f"Cannot word a way without {relation!r} from {sorted(taken)}")
        return need

    def _lead(self, clauses: Mapping[str, str], node: str, taken: Needs, known: str | None = None) -> str:
        """The clause of the first relation in `clauses` that the way holds."""
        relation = next((relation for relation in clauses if relation in taken), None)
        if relation is None:
            raise ProgressionWordingError(f"Cannot word a main clause from {sorted(taken)}")
        need = self._need(taken, relation)
        key = need.need_stable_key
        return clauses[relation].format(
            node=node,
            need=_ref(key),
            place="" if key is None or key == known else self._place(key),
            keywords=_keywords(need),
            count=f"all {need.quantity:g} " if need.quantity and need.quantity > 1 else "",
        )

    def _items(self, needs: Sequence[ProgressionNeed]) -> str:
        """Items with their counts. Several slots of one item read as one count."""
        counts: dict[str | None, float] = {}
        for need in needs:
            counts[need.need_stable_key] = counts.get(need.need_stable_key, 0) + (need.quantity or 1)
        return _join([_count(count) + _ref(key) for key, count in counts.items()])

    def _defeats(self, needs: Sequence[ProgressionNeed]) -> str:
        """Characters to defeat. Copies that share a name read as one name with their count."""
        counts: dict[str, dict[str, float]] = defaultdict(dict)
        for need in needs:
            key = str(need.need_stable_key)
            copies = counts[self._node(key).name]
            copies[key] = max(copies.get(key, 0), need.quantity or 1)
        parts = []
        for copies in counts.values():
            total = sum(copies.values())
            prefix = "" if total == 1 else "both " if total == 2 else f"all {total:g} "
            parts.append(prefix + _ref(next(iter(copies))))
        return _join(parts)

    def _item(self, node: ProgressionNode, taken: Needs) -> str:
        item = _ref(node.stable_key)
        if "mold" in taken or "material" in taken:
            mold = self._one(taken, "mold")
            materials = self._take(taken, "material")
            text = f"craft {item}" + (f" with {_ref(mold.need_stable_key)}" if mold else "")
            return text + (f" from {self._items(materials)}" if materials else "")
        if "from" in taken:
            return self._from(self._need(taken, "from"), item)
        if "converted from" in taken:
            source = self._need(taken, "converted from")
            zone = self._one(taken, "in zone")
            where = f" in {_ref(zone.need_stable_key)}" if zone else ""
            return f"get {item} from {_ref(source.need_stable_key)}{where}"
        return self._lead(_ITEM_CLAUSES, item, taken)

    def _from(self, need: ProgressionNeed, node: str) -> str:
        source = str(need.need_stable_key)
        if self._kind(need) == "class":
            return f"start a new {_ref(source)} character with {node}"
        pattern = _FROM_MECHANISM.get(_mechanism(source))
        if pattern is None:
            raise ProgressionWordingError(f"Cannot word a way from {source!r}")
        return pattern.format(node=node)

    def _completion(self, quest: str, taken: Needs, known: str | None) -> str:
        """What finishes a quest. A character that its start already placed is not placed again."""
        if "turn in to" in taken:
            receiver = self._need(taken, "turn in to").need_stable_key
            items = self._take(taken, "required item")
            given = self._items(items) if items else "what it asks for"
            place = "" if receiver == known else self._place(str(receiver))
            return f"give {given} to {_ref(receiver)}{place}"
        if "event" in taken:
            zone = self._need(taken, "event").need_stable_key
            return f"trigger the scripted event in {_ref(zone)}" if zone else "trigger its scripted event"
        if "after" in taken:
            text = f"finish {_ref(self._need(taken, 'after').need_stable_key)}"
            return text + (f" while {_ref(quest)} is active" if self._one(taken, "quest active") else "")
        return self._lead(_COMPLETIONS, _ref(quest), taken, known)

    def _quest(self, node: ProgressionNode, taken: Needs) -> str:
        quest = _ref(node.stable_key)
        if "state" in taken:
            return f"{quest} counts as done {self._state(self._need(taken, 'state'))}"
        start = self._one(taken, "started")
        if start is None:
            return f"{self._completion(node.stable_key, taken, None)} to finish {quest}"
        start_key = str(start.need_stable_key)
        way = self._first_way(start_key)
        if way is None:
            raise ProgressionWordingError(f"The start {start_key!r} has no first way")
        begun = _grouped(self._unimplied(self._node(start_key), way.needs))
        if "after" in begun:
            after = self._need(begun, "after").need_stable_key
            # The start already waits for that quest, so the quest's own wait for it is not said again.
            done = [need for need in self._take(taken, "quest done") if need.need_stable_key != after]
            if done:
                taken["quest done"] = done
            conditions = self._conditions(begun, frozenset())
            completion = self._completion(node.stable_key, taken, None)
            return f"after {_ref(after)}{conditions}, {completion} to finish {quest}"
        known = next((need.need_stable_key for need in begun.get("talk to", []) + begun.get("turn in to", [])), None)
        opening = self._opening(begun)
        conditions = self._conditions(begun, frozenset())
        completion = self._completion(node.stable_key, taken, known)
        return f"{opening} to start {quest}{conditions}, then {completion} to finish it"

    def _opening(self, taken: Needs) -> str:
        """What starts a quest."""
        if "turn in to" in taken:
            giver = str(self._need(taken, "turn in to").need_stable_key)
            items = self._take(taken, "required item")
            return f"give {self._items(items)} to {_ref(giver)}{self._place(giver)}"
        if "event" in taken:
            self._need(taken, "event")
            return "trigger its scripted event"
        return self._lead(_OPENINGS, "", taken)

    def _quest_start(self, node: ProgressionNode, taken: Needs) -> str:
        quest = _ref(node.stable_key.removeprefix("quest_start:"))
        if "after" in taken:
            return f"finish {_ref(self._need(taken, 'after').need_stable_key)} to start {quest}"
        return f"{self._opening(taken)} to start {quest}"

    def _zone(self, node: ProgressionNode, taken: Needs) -> str:
        zone = _ref(node.stable_key)
        if "planning slot" in taken:
            rune = _ref(self._need(taken, "planning slot").need_stable_key)
            line = self._one(taken, "zone line")
            where = f" in {_ref(line.need_stable_key)}" if line else ""
            return f"place {rune} on the planning table{where} to travel to {zone}"
        if "cast" in taken:
            spell = _ref(self._need(taken, "cast").need_stable_key)
            place = self._one(taken, "in zone")
            where = f" in {_ref(place.need_stable_key)}" if place else ""
            return f"cast {spell}{where} to travel to {zone}"
        if "from" in taken:
            return self._from(self._need(taken, "from"), zone)
        source = _ref(self._need(taken, "zone line").need_stable_key)
        barriers = self._take(taken, "barrier")
        through = f" through {_join([_ref(gate.need_stable_key) for gate in barriers])}" if barriers else ""
        return f"travel from {source} to {zone}{through}"

    def _barrier(self, node: ProgressionNode, taken: Needs) -> str:
        """A key or a carried item leads, and quests or defeats that it waits for follow as conditions."""
        barrier = _ref(node.stable_key)
        if "key" in taken or "held" in taken:
            return self._lead(_BARRIER_CLAUSES, barrier, taken)
        if "quest done" in taken:
            quests = _join([_ref(need.need_stable_key) for need in self._take(taken, "quest done")])
            return f"finish {quests} to get past {barrier}"
        return f"defeat {self._defeats(self._take(taken, 'defeated'))} to get past {barrier}"

    def _character(self, node: ProgressionNode, taken: Needs) -> str:
        character = _ref(node.stable_key)
        zone = self._one(taken, "in zone")
        where = f" in {_ref(zone.need_stable_key)}" if zone else ""
        if "summoned with" in taken:
            return f"summon {character} with {_ref(self._need(taken, 'summoned with').need_stable_key)}{where}"
        if "cast" in taken:
            spell = self._need(taken, "cast")
            minimum = spell.required_level
            level = f" at level {minimum} or higher" if minimum is not None and minimum > 1 else ""
            return f"cast {_ref(spell.need_stable_key)}{where}{level} to find {character}"
        if "talk to" in taken:
            speaker = self._need(taken, "talk to")
            words = f"talk to {_ref(speaker.need_stable_key)}{self._place(str(speaker.need_stable_key))}"
            return f"{words}{_keywords(speaker)} to find {character}{where}"
        if "entered from" in taken:
            return (
                f"find {character}{where} when you come from {_ref(self._need(taken, 'entered from').need_stable_key)}"
            )
        return f"find {character}{where}"

    def _world_state(self, node: ProgressionNode, taken: Needs) -> str:
        if not node.stable_key.startswith(_RAIN):
            raise ProgressionWordingError(f"Cannot word world state {node.stable_key!r}")
        zone = self._one(taken, "in zone")
        place = _ref(zone.need_stable_key if zone else node.stable_key.removeprefix(_RAIN))
        if "cast" in taken:
            return f"cast {_ref(self._need(taken, 'cast').need_stable_key)} in {place} to make it rain there"
        self._need(taken, "natural weather")
        return f"wait for rain in {place}"

    def _faction(self, key: str) -> tuple[str, str]:
        faction, required = _standing(key)
        name = self._names.get("faction:" + faction)
        if not name or required not in _STANDING_LEVELS:
            raise ProgressionWordingError(f"Cannot word progression faction standing: {key!r}")
        return name, required

    def _faction_standing(self, node: ProgressionNode, taken: Needs) -> str:
        name, required = self._faction(node.stable_key)
        item = _ref(self._need(taken, "equipped").need_stable_key)
        return f"wear {item} to raise your standing with {name} {_STANDING_LEVELS[required]}"

    def _account_state(self, node: ProgressionNode, taken: Needs) -> str:
        goal = _ACCOUNT_GOALS.get(node.stable_key)
        if goal is None:
            raise ProgressionWordingError(f"Cannot word how to reach account state {node.stable_key!r}")
        if "quest done" in taken:
            return f"finish {_join([_ref(need.need_stable_key) for need in self._take(taken, 'quest done')])} to {goal}"
        return f"defeat {self._defeats(self._take(taken, 'defeated'))} to {goal}"

    def _spell(self, node: ProgressionNode, taken: Needs) -> str:
        spell = _ref(node.stable_key)
        if "teaches" in taken:
            scroll = self._need(taken, "teaches")
            role = self._one(taken, "class")
            text = f"learn {spell} from {_ref(scroll.need_stable_key)}"
            text += f" as a {_ref(role.need_stable_key)}" if role else ""
            level = scroll.required_level
            return text + (f" of level {level} or higher" if level is not None and level > 1 else "")
        return self._lead(_SPELL_CLAUSES, spell, taken)

    def _mechanism(self, node: ProgressionNode, taken: Needs) -> str:
        noun = _MECHANISM_NOUNS.get(_mechanism(node.stable_key))
        if noun is None:
            raise ProgressionWordingError(f"Cannot word a way of mechanism {node.stable_key!r}")
        return f"use {noun} in {_ref(self._need(taken, 'in zone').need_stable_key)}"

    # Conditions

    def _conditions(self, taken: Needs, rooms: frozenset[str]) -> str:
        """Word every need that the main clause left, in a fixed order."""
        defeats = self._take(taken, "defeated") + self._take(taken, "defeat")
        releases: list[ProgressionNeed] = []
        for need in self._take(taken, "release"):
            (defeats if self._kind(need) == "character" else releases).append(need)
        if defeats:
            taken["defeated"] = defeats
        if releases:
            taken["release"] = releases
        unknown = sorted(set(taken) - set(_CONDITION_ORDER))
        if unknown:
            raise ProgressionWordingError(f"Cannot word {unknown} as a condition")
        level = max((need.required_level or 0 for needs in taken.values() for need in needs), default=0)
        phrases: list[str] = []
        for relation in _CONDITION_ORDER:
            for phrase in self._condition(relation, self._take(taken, relation), rooms):
                if phrase not in phrases:
                    phrases.append(phrase)
        if level > 1:
            phrases.append(f"at level {level} or higher")
        return "".join(", " + phrase for phrase in phrases)

    def _condition(self, relation: str, needs: Sequence[ProgressionNeed], rooms: frozenset[str]) -> list[str]:
        if not needs:
            return []
        if relation in _LIST_CONDITIONS:
            pattern, conjunction = _LIST_CONDITIONS[relation]
            return [pattern.format(needs=_join([_ref(need.need_stable_key) for need in needs], conjunction))]
        if relation == "quest active":
            quests = [_ref(str(need.need_stable_key).removeprefix("quest_start:")) for need in needs]
            return [f"while {_join(quests)} is active"]
        if relation == "held":
            return [f"while you carry {self._items(needs)}"]
        if relation == "defeated":
            return [f"after you defeat {self._defeats(needs)}"]
        writer = {
            "room furnished": lambda need: self._furnished(need, rooms),
            "release": self._release,
            "state": self._state,
            "standing": self._standing_condition,
        }[relation]
        return [writer(need) for need in needs]

    def _furnished(self, need: ProgressionNeed, rooms: frozenset[str]) -> str:
        furniture = _ref(need.need_stable_key)
        if rooms == self._rooms:
            return f"with {furniture} furnished in any room of your Reliquary"
        return f"with {furniture} furnished in room {_join(sorted(rooms), 'or')} of your Reliquary"

    def _release(self, need: ProgressionNeed) -> str:
        key = need.need_stable_key
        kind = self._kind(need)
        if kind == "item":
            return f"after you hand in {_count(need.quantity)}{_ref(key)}"
        if kind == "world_state" and str(key).startswith(_RAIN):
            return f"while it rains in {_ref(str(key).removeprefix(_RAIN))}"
        if key is None and need.condition_key:
            text = condition_text(need.condition_key)
            return "which " + text[:1].lower() + text[1:]
        raise ProgressionWordingError(f"Cannot word a release by {key or need.condition_key!r}")

    def _state(self, need: ProgressionNeed) -> str:
        state = _ACCOUNT_STATES.get(str(need.need_stable_key))
        if state is None:
            raise ProgressionWordingError(f"Cannot word account state {need.need_stable_key!r}")
        return state

    def _standing_condition(self, need: ProgressionNeed) -> str:
        name, required = self._faction(str(need.need_stable_key))
        return f"while your standing with {name} {_STANDING_CONDITIONS[required]}"
