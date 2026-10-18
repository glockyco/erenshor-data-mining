"""Read persisted requirements without deriving game mechanics in consumers."""

from __future__ import annotations

from collections import defaultdict, deque

from erenshor.domain.value_objects.progression import (
    PROGRESSION_SCHEMA_VERSION,
    ProgressionNeed,
    ProgressionNode,
    ProgressionWay,
)
from erenshor.infrastructure.database.connection import DatabaseConnection, DatabaseConnectionError
from erenshor.infrastructure.database.repository import RepositoryError


class ProgressionRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self.db = db
        self._nodes: dict[str, ProgressionNode] = {}
        self._ways: dict[str, tuple[ProgressionWay, ...]] = {}
        self._loaded = False
        try:
            with db.connect() as connection:
                rows = connection.execute("SELECT contract_version, game_build_id FROM progression_meta").fetchall()
            if len(rows) != 1:
                raise ValueError("expected exactly one metadata row")
            version, build = rows[0]
            if type(version) is not int or version != PROGRESSION_SCHEMA_VERSION:
                raise ValueError(f"unsupported contract version {version!r}, expected {PROGRESSION_SCHEMA_VERSION}")
            if not isinstance(build, str) or not build:
                raise ValueError("missing game build id")
            self.game_build_id = build
        except (DatabaseConnectionError, ValueError) as error:
            raise RepositoryError(f"Unsupported progression schema: {error}") from error

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            with self.db.connect() as connection:
                names = {
                    row[0]: row[1]
                    for table in ("zones", "quests", "items", "characters")
                    for row in connection.execute(f"SELECT stable_key, display_name FROM {table}")
                }
                names.update(
                    ("class:" + row[0].lower(), row[1] or row[0])
                    for row in connection.execute("SELECT class_name, display_name FROM classes")
                )
                names.update(
                    (row[0], "Door in " + row[1])
                    for row in connection.execute(
                        "SELECT d.stable_key,z.display_name FROM doors d JOIN zones z ON z.scene_name=d.scene"
                    )
                )
                nodes = {}
                for row in connection.execute("SELECT * FROM progression_nodes ORDER BY stable_key"):
                    key = row["stable_key"]
                    name = names.get(key) or key
                    if row["kind"] == "quest_start":
                        name = "Start of " + (names.get(key.removeprefix("quest_start:")) or key)
                    elif key.startswith("world_state:weather:raining:"):
                        zone = key.removeprefix("world_state:weather:raining:")
                        name = "Rain in " + (names.get(zone) or zone)
                    elif key == "mechanic:new_character_start":
                        name = "New character start"
                    elif key == "mechanic:alternate_start":
                        name = "Alternate start"
                    nodes[key] = ProgressionNode(
                        key, row["kind"], name, bool(row["is_milestone"]), row["tier"], row["first_way_key"]
                    )
                needs: dict[tuple[str, str], list[ProgressionNeed]] = defaultdict(list)
                for row in connection.execute(
                    "SELECT * FROM progression_needs ORDER BY node_stable_key, way_key, need_index"
                ):
                    needs[row["node_stable_key"], row["way_key"]].append(
                        ProgressionNeed(
                            row["relation"],
                            row["need_stable_key"],
                            row["quantity"],
                            row["slot"],
                            row["keywords"],
                            row["condition_key"],
                            bool(row["advisory"]),
                            bool(row["unconfirmed"]),
                        )
                    )
                ways: dict[str, list[ProgressionWay]] = defaultdict(list)
                for row in connection.execute("SELECT * FROM progression_ways ORDER BY node_stable_key, way_key"):
                    ways[row["node_stable_key"]].append(
                        ProgressionWay(row["way_key"], tuple(needs[row["node_stable_key"], row["way_key"]]))
                    )
            self._nodes = nodes
            self._ways = {key: tuple(value) for key, value in ways.items()}
            self._loaded = True
        except DatabaseConnectionError as error:
            raise RepositoryError(f"Cannot read progression graph: {error}") from error

    def get_node(self, key: str) -> ProgressionNode | None:
        self._load()
        return self._nodes.get(key)

    def get_ways(self, key: str) -> tuple[ProgressionWay, ...]:
        self._load()
        return self._ways.get(key, ())

    def _target(self, need: ProgressionNeed) -> ProgressionNode | None:
        if need.need_stable_key is None or need.relation == "quest not done":
            return None
        target = self._nodes.get(need.need_stable_key)
        if target is None:
            raise RepositoryError(f"Progression need resolves to no node: {need.need_stable_key}")
        return target

    def first_way_milestones(self, key: str) -> tuple[ProgressionNode, ...]:
        self._load()
        root = self._nodes.get(key)
        if root is None or root.tier is None:
            return ()
        seen: set[str] = set()
        active: set[str] = set()
        milestones = []

        def visit(node: ProgressionNode) -> None:
            if node.stable_key in active:
                raise RepositoryError(f"Cyclic progression first way: {node.stable_key}")
            if node.stable_key in seen:
                return
            active.add(node.stable_key)
            first = next(
                (way for way in self._ways.get(node.stable_key, ()) if way.way_key == node.first_way_key), None
            )
            if first is None:
                raise RepositoryError(f"Missing progression first way: {node.stable_key} {node.first_way_key}")
            initial_zone = (
                node.kind == "zone" and node.tier == 0 and any(need.relation == "from" for need in first.needs)
            )
            if node.is_milestone or initial_zone:
                milestones.append(node)
            for need in first.needs:
                target = self._target(need)
                if target is not None:
                    if target.tier is None:
                        raise RepositoryError(f"Unreachable progression first-way need: {target.stable_key}")
                    visit(target)
            active.remove(node.stable_key)
            seen.add(node.stable_key)

        visit(root)
        return tuple(sorted(milestones, key=lambda node: (node.tier or 0, node.stable_key)))

    def unreachable_chain(self, key: str) -> tuple[ProgressionNode, ...]:
        self._load()
        root = self._nodes.get(key)
        if root is None or root.tier is not None:
            return ()
        pending: deque[tuple[ProgressionNode, ...]] = deque([(root,)])
        seen = {key}
        cycle: tuple[ProgressionNode, ...] = ()
        while pending:
            chain = pending.popleft()
            node = chain[-1]
            ways = self._ways.get(node.stable_key, ())
            if not ways:
                return chain
            for way in ways:
                for need in way.needs:
                    target = self._target(need)
                    if target is None or target.tier is not None:
                        continue
                    if target.stable_key in {entry.stable_key for entry in chain}:
                        cycle = (*chain, target)
                    elif target.stable_key not in seen:
                        seen.add(target.stable_key)
                        pending.append((*chain, target))
        if cycle:
            return cycle
        raise RepositoryError(f"Unreachable progression node has no unresolved need: {key}")

    def gaps(self) -> tuple[ProgressionNode, ...]:
        self._load()
        return tuple(node for key, node in sorted(self._nodes.items()) if not self._ways.get(key) or node.tier is None)
