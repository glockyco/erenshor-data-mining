"""Unit tests for the image commands."""

import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from erenshor.application.wiki.lifecycle import ContentLifecycle
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.cli.commands import images
from erenshor.cli.commands.images import _deployment_list_for_stable_keys
from erenshor.cli.context import CLIContext

runner = CliRunner()


def test_deployment_list_selects_only_requested_stable_keys() -> None:
    registry = MagicMock()
    fit = MagicMock(image_name="Fit of Brilliance")
    other = MagicMock(image_name="Other Spell")
    registry.get_image_metadata.side_effect = {
        "spell:none - fit of resonance": fit,
        "spell:other": other,
    }.get

    selected = _deployment_list_for_stable_keys(registry, ["spell:none - fit of resonance"])

    assert selected == {"Fit of Brilliance": fit}
    registry.get_image_metadata.assert_called_once_with("spell:none - fit of resonance")


def test_deployment_list_rejects_unknown_stable_keys() -> None:
    registry = MagicMock()
    registry.get_image_metadata.return_value = None

    with pytest.raises(ValueError, match=r"Unknown image stable key.*spell:missing"):
        _deployment_list_for_stable_keys(registry, ["spell:missing"])


def test_manifest_writes_only_without_dry_run(cli_context: CLIContext, monkeypatch: pytest.MonkeyPatch) -> None:
    variant = cli_context.config.variants["main"]
    with closing(sqlite3.connect(variant.database)) as clean, clean:
        clean.execute(
            "INSERT INTO characters (stable_key, object_name, display_name, image_name, is_prefab, resources_path,"
            " encounter_tier, level_scales_with_player)"
            " VALUES ('character:faith', 'Faith', 'Faith', 'Faith', 1, 'npcs/Faith', 'boss', 0)"
        )
        clean.execute("INSERT INTO code_facts_meta (game_build_id) VALUES ('24405256')")
    WikiStorage(Path(variant.wiki)).save_generated_by_title(
        "Faith", ["character:faith"], "{{Character\n|name=Faith\n|stablekey=character:faith\n|imagefile=Faith.png\n}}\n"
    )
    monkeypatch.setattr(
        images, "load_content_lifecycle", lambda _path: ContentLifecycle(pages={}, renames={}, splits={})
    )
    client = MagicMock()
    client.get_uploaded_files.return_value = frozenset()
    monkeypatch.setattr(images, "create_readonly_mediawiki_client", lambda _ctx: client)
    output = Path(variant.unity_project).parent / "images" / "model-captures" / "manifest.json"

    dry = runner.invoke(images.app, ["manifest"], obj=replace(cli_context, dry_run=True))

    assert dry.exit_code == 0, dry.output
    assert "Faith.png" in dry.output
    assert not output.exists()

    written = runner.invoke(images.app, ["manifest"], obj=cli_context)

    assert written.exit_code == 0, written.output
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["game_build"] == "24405256"
    assert [(entry["file"], entry["source"]["resources_path"]) for entry in manifest["entries"]] == [
        ("Faith.png", "npcs/Faith")
    ]
