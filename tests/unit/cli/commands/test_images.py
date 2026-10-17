"""Unit tests for the image commands."""

import io
import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from erenshor.application.services.image_publication_run import RunRecord
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


def test_publication_record_reports_pending_separately_from_skips_and_writes(tmp_path: Path) -> None:
    record = RunRecord(
        tmp_path,
        [
            {"title": "File:Known.png", "action": "redirect", "done": True, "pending_mutation": False},
            {"title": "File:Unknown.png", "action": "redirect", "done": None, "pending_mutation": True},
        ],
    )
    output = io.StringIO()

    images._print_record(Console(file=output, width=120), record)

    text = output.getvalue()
    assert "Written: 1 redirect" in text
    assert "pending redirect File:Unknown.png" in text
    assert "skipped" not in text


def test_revert_dry_run_accepts_a_pending_only_image_run(cli_context: CLIContext) -> None:
    variant = cli_context.config.variants[cli_context.variant]
    run_dir = variant.resolved_images_output(cli_context.repo_root) / "publish" / "pending-run"
    record = RunRecord(run_dir)
    record.add({"title": "File:Unknown.png", "action": "redirect", "done": None, "pending_mutation": True})
    mediawiki = cli_context.config.global_.mediawiki.model_copy(
        update={"bot_username": "WoWBot@Publish", "bot_password": "offline-fixture"}
    )
    global_config = cli_context.config.global_.model_copy(update={"mediawiki": mediawiki})
    context = replace(
        cli_context,
        dry_run=True,
        config=cli_context.config.model_copy(update={"global_": global_config}),
    )

    result = runner.invoke(images.app, ["publish", "--revert", "pending-run"], obj=context)

    assert result.exit_code == 0, result.output
    assert "0 writes to undo, 1 pending edits to reconcile" in result.output
    assert "Dry run: nothing was written." in result.output
    assert RunRecord.load(run_dir).entries == record.entries
