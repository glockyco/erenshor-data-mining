"""Unit tests for field-coverage manifest seeding and writing."""

from __future__ import annotations

import json
from pathlib import Path

from erenshor.application.export_surface.runner import seed_entries, write_manifest


def test_seed_entries_from_unclassified(tmp_path: Path) -> None:
    """Unclassified findings become placeholder entries with empty status."""
    findings = [
        {
            "script_type": "Item",
            "field_name": "RareItem",
            "kind": "unclassified",
            "expected": None,
            "actual": "System.Boolean",
        },
        {
            "script_type": "Item",
            "field_name": "Icon",
            "kind": "unclassified",
            "expected": None,
            "actual": "UnityEngine.Sprite",
        },
        {
            "script_type": "Spell",
            "field_name": "Damage",
            "kind": "unclassified",
            "expected": None,
            "actual": "System.Int32",
        },
    ]
    fields = seed_entries(findings)

    assert fields["Item"]["RareItem"] == {"type": "System.Boolean", "status": "", "by": None, "reason": None}
    assert fields["Item"]["Icon"] == {"type": "UnityEngine.Sprite", "status": "", "by": None, "reason": None}
    assert fields["Spell"]["Damage"] == {"type": "System.Int32", "status": "", "by": None, "reason": None}


def test_seed_entries_ignores_non_unclassified() -> None:
    """Only unclassified findings produce seed entries (stale/retype are not new fields)."""
    findings = [
        {"script_type": "Item", "field_name": "Gone", "kind": "stale", "expected": "System.Int32", "actual": None},
        {
            "script_type": "Item",
            "field_name": "New",
            "kind": "unclassified",
            "expected": None,
            "actual": "System.Boolean",
        },
    ]
    fields = seed_entries(findings)
    assert "Gone" not in fields.get("Item", {})
    assert fields["Item"]["New"] == {"type": "System.Boolean", "status": "", "by": None, "reason": None}


def test_write_manifest_sorted_compact(tmp_path: Path) -> None:
    """Manifest is sorted by type then field, one entry per line."""
    fields = {
        "Spell": {
            "Zeta": {"type": "System.Int32", "status": "ignored", "by": None, "reason": "test"},
            "Alpha": {"type": "System.Boolean", "status": "captured", "by": "SpellListener", "reason": None},
        },
        "Item": {
            "Beta": {"type": "System.String", "status": "ignored", "by": None, "reason": "test"},
        },
    }
    out = tmp_path / "m.json"
    write_manifest(out, "123", ["Spell", "Item"], fields)

    data = json.loads(out.read_text())
    # Types sorted alphabetically.
    assert data["types"] == ["Item", "Spell"]
    # Fields sorted alphabetically within each type.
    assert list(data["fields"]["Item"].keys()) == ["Beta"]
    assert list(data["fields"]["Spell"].keys()) == ["Alpha", "Zeta"]
    # One field entry per line (compact format).
    text = out.read_text()
    assert text.count('"Beta"') == 1


def test_write_manifest_round_trip(tmp_path: Path) -> None:
    """Written manifest can be loaded by the C# tool (valid JSON structure)."""
    fields = {
        "Item": {
            "RareItem": {"type": "System.Boolean", "status": "captured", "by": "ItemListener", "reason": None},
        },
    }
    out = tmp_path / "m.json"
    write_manifest(out, "999", ["Item"], fields)

    data = json.loads(out.read_text())
    assert data["tracks_build"] == "999"
    assert data["types"] == ["Item"]
    assert data["fields"]["Item"]["RareItem"]["status"] == "captured"
    assert data["fields"]["Item"]["RareItem"]["by"] == "ItemListener"
