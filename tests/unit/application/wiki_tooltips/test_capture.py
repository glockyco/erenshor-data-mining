from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from erenshor.application.wiki_tooltips.capture import _batch, capture, decode_batch, reconcile


def make_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
            CREATE TABLE items (id, resource_name, stable_key, is_wiki_generated, required_slot,
                teach_spell_stable_key, teach_skill_stable_key, template, item_effect_on_click_stable_key,
                disposable, cosmetic_effect);
            CREATE TABLE spells (id, resource_name, stable_key, is_wiki_generated);
            CREATE TABLE skills (id, resource_name, stable_key, is_wiki_generated, stance_to_use_stable_key);
            CREATE TABLE stances (resource_name, stable_key, is_wiki_generated);
            CREATE TABLE code_facts_meta (game_build_id);
            INSERT INTO code_facts_meta VALUES ('100');
            INSERT INTO items VALUES ('11', 'FigResource', 'item:fig', 0, 'General', NULL, NULL, 0, NULL, 0, NULL);
            INSERT INTO spells VALUES ('22', 'SparkResource', 'spell:spark', 1);
            INSERT INTO skills VALUES ('33', 'GuardResource', 'skill:guard', 1, 'stance:guard');
            INSERT INTO stances VALUES ('GuardStance', 'stance:guard', 1), ('UnusedStance', 'stance:unused', 0);
        """)


def observations():
    return [
        {"kind": "item", "index": 0, "id": "11", "resource": "FigResource", "quantity": 1},
        {"kind": "spell", "index": 0, "id": "22", "resource": "SparkResource"},
        {"kind": "skill", "index": 0, "id": "33", "resource": "GuardResource", "stance_resource": "GuardStance"},
    ]


def test_capture_joins_runtime_ids_and_records_exclusions(tmp_path):
    path = tmp_path / "game.sqlite"
    make_database(path)
    entries = observations()
    excluded = reconcile(path, entries)
    assert [entry["stable_key"] for entry in entries] == ["item:fig", "spell:spark", "skill:guard"]
    assert entries[-1]["stance_key"] == "stance:guard"
    assert [row["stable_key"] for row in excluded] == ["item:fig", "stance:unused"]
    assert excluded[-1]["reason"] == "no activating skill"


@pytest.mark.parametrize(("kind", "key"), [("item", "item:fig"), ("spell", "spell:spark")])
def test_capture_fails_missing_runtime_identity(tmp_path, kind, key):
    path = tmp_path / "game.sqlite"
    make_database(path)
    entries = [entry for entry in observations() if entry["kind"] != kind]
    with pytest.raises(ValueError, match=f"Incomplete {key}"):
        reconcile(path, entries)


def test_capture_fails_duplicate_item_quality(tmp_path):
    path = tmp_path / "game.sqlite"
    make_database(path)
    entries = observations()
    with pytest.raises(ValueError, match="Duplicate runtime item identity: item:fig"):
        reconcile(path, [*entries, entries[0].copy()])


def test_capture_preserves_distinct_windows_and_exact_text():
    entries = decode_batch(
        "spell\t0\tMQ==\tQQ==\nDesc\t1\tFFFFFFFF\tFFFFFFFF\t0\tWAoK\n"
        "details\tMQ==\t0\t1\nSpellDetailsDesc\t0\tFFFFFFFF\tFFFFFFFF\t1\tWQ==\n"
    )
    assert entries[0]["fields"]["Desc"]["text"] == "X\n\n"
    assert entries[0]["details"]["fields"]["SpellDetailsDesc"] == {
        "active": False,
        "color": "FFFFFFFF",
        "face_color": "FFFFFFFF",
        "italic": True,
        "text": "Y",
    }
    assert entries[0]["details"]["level_scaled_mana"] is True


def test_truncated_eval_reply_is_not_evidence():
    client = AsyncMock()
    client.eval.return_value = {"hasValue": True, "truncated": True, "value": "spell"}
    with pytest.raises(ValueError, match="Incomplete HotRepl reply"):
        asyncio.run(_batch(client, "spells", 0, 1))


def test_capture_rejects_wrong_build_before_connecting(tmp_path):
    path = tmp_path / "game.sqlite"
    output = tmp_path / "game.json"
    make_database(path)
    with pytest.raises(ValueError, match="Installed build 200 does not match clean database build 100"):
        asyncio.run(capture(path, "200", output))
    assert not output.exists()
