from __future__ import annotations

import sqlite3

import pytest

from erenshor.application.processor.progression import Need, ProgressionBuilder, canonical_way, way_key
from erenshor.application.processor.writer import _DDL


def test_equal_tier_navigation_cycle_keeps_a_start_rooted_first_way():
    connection = sqlite3.connect(":memory:")
    connection.executescript(_DDL)
    graph = ProgressionBuilder(connection)
    for key in ("zone:start", "zone:a", "zone:b"):
        graph.node(key, "zone")
    graph.add("zone:start", (), "start")
    graph.add("zone:a", [Need("zone line", "zone:start")], "entrance")
    graph.add("zone:a", [Need("zone line", "zone:b")], "cycle-return")
    graph.add("zone:b", [Need("zone line", "zone:a")], "cycle-entry")
    graph.mark_milestones()
    graph.order()
    assert graph.tiers == {"zone:start": 0, "zone:a": 0, "zone:b": 0}
    assert graph.depths == {"zone:start": 0, "zone:a": 1, "zone:b": 2}
    assert graph.first["zone:a"] == way_key(canonical_way([Need("zone line", "zone:start")]))
    graph.check_first_ways()
    graph.first["zone:a"] = way_key(canonical_way([Need("zone line", "zone:b")]))
    with pytest.raises(ValueError, match="first-way depth"):
        graph.check_first_ways()
    connection.close()


def test_joint_needs_use_highest_tier_before_explanation_depth():
    connection = sqlite3.connect(":memory:")
    connection.executescript(_DDL)
    graph = ProgressionBuilder(connection)
    for key in ("start", "a", "b", "joint"):
        graph.node(key, "quest" if key != "start" else "class")
    graph.add("start", (), "start")
    graph.add("a", [Need("from", "start")], "a")
    graph.add("b", [Need("after", "a")], "b")
    graph.add("joint", [Need("after", "a"), Need("after", "b")], "joint")
    graph.mark_milestones()
    graph.order()
    assert graph.tiers["joint"] == 3
    assert graph.depths["joint"] == 3
    graph.check_tiers()
    graph.check_first_ways()
    connection.close()


def test_falling_dependency_tier_cannot_leave_a_stale_parent_depth():
    connection = sqlite3.connect(":memory:")
    connection.executescript(_DDL)
    graph = ProgressionBuilder(connection)
    for key in ("start", "a", "joint", "z0", "z1", "z2", "z3"):
        graph.node(key, "zone")
    for key in ("gate1", "gate2"):
        graph.node(key, "quest")
    graph.add("start", (), "start")
    graph.add("gate1", [Need("after", "start")], "gate1")
    graph.add("gate2", [Need("after", "gate1")], "gate2")
    graph.add("a", [Need("in zone", "gate1")], "short-later-tier")
    graph.add("z3", [Need("in zone", "start")], "long0")
    graph.add("z2", [Need("in zone", "z3")], "long1")
    graph.add("z1", [Need("in zone", "z2")], "long2")
    graph.add("z0", [Need("in zone", "z1")], "long3")
    graph.add("a", [Need("in zone", "z0")], "long-earliest-tier")
    graph.add("joint", [Need("in zone", "a"), Need("in zone", "gate2")], "joint")
    graph.mark_milestones()
    graph.order()
    assert graph.tiers["a"] == 0
    assert graph.depths["a"] == 5
    assert graph.tiers["joint"] == 2
    assert graph.depths["joint"] == 6
    graph.check_first_ways()
    connection.close()
