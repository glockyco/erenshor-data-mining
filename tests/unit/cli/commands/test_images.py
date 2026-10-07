"""Unit tests for the image commands."""

import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from erenshor.application.wiki.lifecycle import ContentLifecycle
from erenshor.cli.commands import images
from erenshor.cli.context import CLIContext

runner = CliRunner()


def test_manifest_writes_only_without_dry_run(cli_context: CLIContext, monkeypatch: pytest.MonkeyPatch) -> None:
    variant = cli_context.config.variants["main"]
    with closing(sqlite3.connect(variant.database)) as clean, clean:
        clean.execute(
            "INSERT INTO characters (stable_key, object_name, display_name, image_name, is_prefab, resources_path,"
            " encounter_tier, level_scales_with_player)"
            " VALUES ('character:faith', 'Faith', 'Faith', 'Faith', 1, 'npcs/Faith', 'boss', 0)"
        )
        clean.execute("INSERT INTO code_facts_meta (game_build_id) VALUES ('24405256')")
    monkeypatch.setattr(
        images, "load_content_lifecycle", lambda _path: ContentLifecycle(pages={}, renames={}, splits={})
    )
    output = Path(variant.unity_project).parent / "images" / "model-captures" / "manifest.json"

    dry = runner.invoke(images.app, ["manifest"], obj=replace(cli_context, dry_run=True))

    assert dry.exit_code == 0, dry.output
    assert "1 models of 1 characters" in dry.output
    assert not output.exists()

    written = runner.invoke(images.app, ["manifest"], obj=cli_context)

    assert written.exit_code == 0, written.output
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["game_build"] == "24405256"
    assert [(entry["subject"], entry["title"], entry["source"]["resources_path"]) for entry in manifest["entries"]] == [
        ("Faith", "Faith render.png", "npcs/Faith")
    ]
