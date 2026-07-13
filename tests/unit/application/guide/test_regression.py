"""Regression tests comparing v3 pipeline output against v2 golden baseline.

Loads the golden baseline (v2 format) and the current pipeline output (v3
format), normalizes the structural differences, and asserts behavioral
equivalence: same quests, same steps, same sources, same or better levels.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN_PATH = Path("quest_guides/quest-guide.golden.json")
CURRENT_PATH = Path("quest_guides/quest-guide.json")

APPROVED_REMOVED_QUESTS = {"AmethiKeys", "ClearingTheBonePits"}
SCRIPTED_QUESTS_WITHOUT_STRUCTURED_STEPS = {
    "BELLWAIN",
    "ENDINGTHECORRUPTIONOFTHEGODS",
    "JAWSSEEN",
    "KilkayQuestline1",
    "SHIVER-MEETALL",
    "SolunasCelestialBlade2",
}
APPROVED_REMOVED_REQUIRED_ITEMS = {("THELOSTSOUL3", "Treasure Hunter's Pin")}


def _load_json(path: Path) -> dict:
    if not path.exists():
        pytest.skip(f"{path} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _index_quests(data: dict) -> dict[str, dict]:
    return {
        q["db_name"]: q
        for q in data["quests"]
        if not q.get("guide_only") and not str(q.get("db_name", "")).startswith("guide.")
    }


def _v2_sources_for_item(ri: dict) -> list[tuple[str, str | None, str | None]]:
    """Extract (type, name, zone) tuples from v2's 7 separate source lists."""
    sources = []
    for ds in ri.get("drop_sources", []):
        sources.append(("drop", ds.get("character_name"), ds.get("zone_name")))
    for vs in ri.get("vendor_sources", []):
        sources.append(("vendor", vs.get("character_name"), vs.get("zone_name")))
    # Zone-level sources: deduplicate by zone (v2 stores per-node)
    seen_zones: set[str] = set()
    for fs in ri.get("fishing_sources", []):
        key = f"fishing:{fs.get('zone_name')}"
        if key not in seen_zones:
            seen_zones.add(key)
            sources.append(("fishing", None, fs.get("zone_name")))
    for ms in ri.get("mining_sources", []):
        key = f"mining:{ms.get('zone_name')}"
        if key not in seen_zones:
            seen_zones.add(key)
            sources.append(("mining", None, ms.get("zone_name")))
    for bs in ri.get("bag_sources", []):
        key = f"pickup:{bs.get('zone_name')}"
        if key not in seen_zones:
            seen_zones.add(key)
            sources.append(("pickup", None, bs.get("zone_name")))
    for cs in ri.get("crafting_sources", []):
        sources.append(("crafting", cs.get("recipe_item_name"), None))
    for qr in ri.get("quest_reward_sources", []):
        sources.append(("quest_reward", qr.get("quest_name"), None))
    return sources


def _v3_sources_for_item(ri: dict) -> list[tuple[str, str | None, str | None]]:
    """Extract (type, name, zone) tuples from v3's unified source list."""
    return [(s["type"], s.get("name"), s.get("zone")) for s in ri.get("sources", [])]


@pytest.fixture(scope="module")
def golden():
    return _load_json(GOLDEN_PATH)


@pytest.fixture(scope="module")
def current():
    return _load_json(CURRENT_PATH)


@pytest.fixture(scope="module")
def require_v5(current):
    if current.get("_version", 2) < 5:
        pytest.skip("Current output is pre-v5; v5 tests will pass after pipeline rewrite")


class TestStructuralParity:
    """Verify the v5 output preserves game quests and structural data."""

    def test_expected_quest_delta(self, golden, current):
        golden_names = set(_index_quests(golden))
        current_names = set(_index_quests(current))
        assert golden_names - current_names == APPROVED_REMOVED_QUESTS
        assert len(current_names - golden_names) == 22
        assert len(current_names) == 196

    def test_zone_lookup_does_not_shrink(self, golden, current):
        assert set(golden["_zone_lookup"]).issubset(set(current["_zone_lookup"]))

    def test_character_spawn_coverage_does_not_shrink(self, golden, current):
        assert len(current["_character_spawns"]) >= len(golden["_character_spawns"])

    def test_zone_line_coverage_does_not_shrink(self, golden, current):
        assert len(current["_zone_lines"]) >= len(golden["_zone_lines"])

    def test_chain_group_coverage_allows_current_regrouping(self, golden, current):
        assert len(current["_chain_groups"]) >= len(golden["_chain_groups"]) - 1

    def test_version_bumped(self, current, require_v5):
        assert current["_version"] == 5


class TestPerQuestParity:
    """Verify each quest preserves its core data."""

    def test_structured_steps_do_not_disappear(self, golden, current):
        g_idx = _index_quests(golden)
        c_idx = _index_quests(current)
        for db_name in sorted(g_idx.keys() & c_idx.keys()):
            if db_name in SCRIPTED_QUESTS_WITHOUT_STRUCTURED_STEPS:
                continue
            assert not g_idx[db_name].get("steps") or c_idx[db_name].get("steps"), (
                f"{db_name}: structured steps disappeared"
            )

    def test_required_items_remain_actionable(self, golden, current):
        """Shared v2 requirements remain requirements or explicit acquisition/step targets."""
        g_idx = _index_quests(golden)
        c_idx = _index_quests(current)
        for db_name in sorted(g_idx.keys() & c_idx.keys()):
            g_quest = g_idx[db_name]
            c_quest = c_idx[db_name]
            c_items = {ri["item_name"] for ri in c_quest.get("required_items", [])}
            c_targets = {source["source_name"] for source in c_quest.get("acquisition", [])}
            c_targets.update(step["target_name"] for step in c_quest.get("steps", []))
            for required in g_quest.get("required_items", []):
                item_name = required["item_name"]
                if (db_name, item_name) in APPROVED_REMOVED_REQUIRED_ITEMS:
                    continue
                assert item_name in c_items or item_name in c_targets, (
                    f"{db_name}: required item {item_name} is no longer actionable"
                )

    def test_obtainability_sources_preserved(self, golden, current, require_v5):
        """v3 sources cover v2 sources minus map-hidden characters."""
        g_idx = _index_quests(golden)
        c_idx = _index_quests(current)
        total_missing = 0
        for db_name in sorted(g_idx.keys() & c_idx.keys()):
            g_quest = g_idx[db_name]
            c_quest = c_idx[db_name]
            for g_ri in g_quest.get("required_items", []):
                item_name = g_ri["item_name"]
                c_ri = next(
                    (ri for ri in c_quest.get("required_items", []) if ri["item_name"] == item_name),
                    None,
                )
                if c_ri is None:
                    continue
                v2_sources = set(_v2_sources_for_item(g_ri))
                v3_sources = set(_v3_sources_for_item(c_ri))
                total_missing += len(v2_sources - v3_sources)
        assert total_missing < 30, (
            f"Too many sources lost: {total_missing} (expected < 30 from map visibility filtering)"
        )

    def test_reward_fields_do_not_disappear(self, golden, current):
        g_idx = _index_quests(golden)
        c_idx = _index_quests(current)
        for db_name in sorted(g_idx.keys() & c_idx.keys()):
            g_rewards = g_idx[db_name].get("rewards", {})
            c_rewards = c_idx[db_name].get("rewards", {})
            for field in ("xp", "gold", "item_name"):
                if g_rewards.get(field) is not None:
                    assert c_rewards.get(field) is not None, f"{db_name}: lost reward field {field}"

    def test_chain_links_preserved(self, golden, current):
        g_idx = _index_quests(golden)
        c_idx = _index_quests(current)
        for db_name in sorted(g_idx.keys() & c_idx.keys()):
            g_links = {(link["quest_stable_key"], link["relationship"]) for link in g_idx[db_name].get("chain", [])}
            c_links = {(link["quest_stable_key"], link["relationship"]) for link in c_idx[db_name].get("chain", [])}
            assert g_links.issubset(c_links), f"{db_name}: chain link disappeared"


class TestLevelEstimates:
    """Verify level estimates are same or better in v3."""

    def test_quest_level_coverage_not_worse(self, golden, current):
        """v3 should have same or more quests with level estimates."""
        g_count = sum(1 for q in golden["quests"] if q.get("level_estimate"))
        c_count = sum(1 for q in current["quests"] if q.get("level_estimate"))
        assert c_count >= g_count, f"Level coverage dropped: {c_count} < {g_count}"

    def test_step_level_coverage_not_worse(self, golden, current):
        """v3 should have same or more steps with level estimates."""
        g_count = sum(1 for q in golden["quests"] for s in q.get("steps", []) if s.get("level_estimate"))
        c_count = sum(1 for q in current["quests"] for s in q.get("steps", []) if s.get("level_estimate"))
        assert c_count >= g_count, f"Step level coverage dropped: {c_count} < {g_count}"


class TestPrerequisites:
    """Verify structured prerequisites replace opaque strings."""

    def test_prerequisites_are_structured(self, current, require_v5):
        """All prerequisites in v3 should be dicts with quest_key, not strings."""
        for q in current["quests"]:
            for prereq in q.get("prerequisites", []):
                assert isinstance(prereq, dict), f"{q['db_name']}: prerequisite is string, not structured"
                assert "quest_key" in prereq, f"{q['db_name']}: prerequisite missing quest_key"
                assert "quest_name" in prereq, f"{q['db_name']}: prerequisite missing quest_name"


class TestSourceLevels:
    """Verify sources carry inline levels."""

    def test_drop_sources_have_levels(self, current, require_v5):
        """Drop sources should carry enemy level inline."""
        drops_with_level = 0
        drops_total = 0
        for q in current["quests"]:
            for ri in q.get("required_items", []):
                for s in ri.get("sources", []):
                    if s["type"] == "drop":
                        drops_total += 1
                        if s.get("level") is not None:
                            drops_with_level += 1
        if drops_total > 0:
            # Most drops should have levels (enemies with level > 0)
            ratio = drops_with_level / drops_total
            assert ratio > 0.8, f"Only {drops_with_level}/{drops_total} drop sources have levels"

    def test_zone_sources_have_levels(self, current, require_v5):
        """Mining/fishing/pickup sources should carry zone median level."""
        zone_types = {"mining", "fishing", "pickup"}
        with_level = 0
        total = 0
        for q in current["quests"]:
            for ri in q.get("required_items", []):
                for s in ri.get("sources", []):
                    if s["type"] in zone_types:
                        total += 1
                        if s.get("level") is not None:
                            with_level += 1
        if total > 0:
            ratio = with_level / total
            assert ratio > 0.8, f"Only {with_level}/{total} zone sources have levels"
