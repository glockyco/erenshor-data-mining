"""Unit tests for the image commands."""

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from erenshor.application.services.model_image_manifest import CALIBRATED_CAMERA_PRESET, CAMERA_PRESET
from erenshor.cli.commands import images
from erenshor.cli.context import CLIContext
from erenshor.infrastructure.content_lifecycle import ContentLifecycle

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


def test_character_lighting_choices_apply_across_variants_and_local_approval(
    cli_context: CLIContext, tmp_path: Path
) -> None:
    (tmp_path / "portrait-lighting.json").write_text(
        json.dumps({"character:kept": "calibrated", "character:cross-variant": "calibrated"}), encoding="utf-8"
    )
    cli_context = replace(cli_context, repo_root=tmp_path)
    capture_dir = tmp_path / "images" / "model-captures"
    staged = capture_dir / "lighting-review" / CAMERA_PRESET
    png_dir = staged / "png"
    png_dir.mkdir(parents=True)
    entries = [
        {
            "subject": name,
            "stable_key": key,
            "title": f"{name} render.png",
            "kind": "character",
            "pages": [name],
            "source": {"resources_path": f"npcs/{name}"},
        }
        for name, key in (
            ("Kept", "character:kept"),
            ("Cross Variant", "character:cross-variant"),
            ("Unreviewed", "character:unreviewed"),
        )
    ]
    (capture_dir / "manifest.json").write_text(
        json.dumps({"game_build": "1", "camera_preset": CAMERA_PRESET, "entries": entries}), encoding="utf-8"
    )
    png = b"portrait"
    (png_dir / "Kept.png").write_bytes(png)
    (staged / "captures.json").write_text(
        json.dumps(
            {
                "game_build": "1",
                "preset": CAMERA_PRESET,
                "results": [
                    {
                        **entries[0],
                        "status": "accepted",
                        "png": "Kept.png",
                        "sha256": hashlib.sha256(png).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    approved = runner.invoke(images.app, ["approve", "--lighting", "current", "Kept"], obj=cli_context)
    assert approved.exit_code == 0, approved.output
    assert (capture_dir / "approved" / "Kept.png").read_bytes() == png
    picks = json.loads((capture_dir / "approved.json").read_text(encoding="utf-8"))
    assert picks["images"][0]["lighting_reviewed"]
    assert picks["images"][0]["preset"] == CAMERA_PRESET

    dry = replace(cli_context, dry_run=True)
    for name, preset in (
        ("Kept", CAMERA_PRESET),
        ("Cross Variant", CALIBRATED_CAMERA_PRESET),
        ("Unreviewed", CAMERA_PRESET),
    ):
        planned = runner.invoke(images.app, ["capture", "--subject", name], obj=dry)
        assert planned.exit_code == 0, planned.output
        assert f"1 {preset}" in planned.output
