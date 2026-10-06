"""A capture run reports every zone variant the mod failed to capture."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from PIL import Image

from erenshor.application.capture import orchestrator
from erenshor.application.capture.wine import from_wine_path
from erenshor.cli.commands import capture as capture_command
from erenshor.cli.context import CLIContext
from erenshor.infrastructure.config.schema import Config, GlobalConfig, MapsConfig, UnityConfig, VariantConfig


def _context(tmp_path: Path) -> SimpleNamespace:
    variant = VariantConfig(
        name="Main",
        app_id="0",
        unity_project=str(tmp_path / "unity"),
        editor_scripts=str(tmp_path / "editor"),
        database_raw=str(tmp_path / "raw.sqlite"),
        database=str(tmp_path / "clean.sqlite"),
        logs=str(tmp_path / "logs"),
        backups=str(tmp_path / "backups"),
        wiki=str(tmp_path / "wiki"),
        maps=MapsConfig(
            source_dir=str(tmp_path / "maps"),
            build_dir=str(tmp_path / "maps/build"),
        ),
    )
    return SimpleNamespace(
        obj=CLIContext(
            Config(
                global_=GlobalConfig(unity=UnityConfig(version="2021.3.45f2", path=str(tmp_path / "Unity"))),
                variants={"main": variant},
            ),
            "main",
            False,
            tmp_path,
        )
    )


def _zone(scene: str) -> dict[str, Any]:
    return {"sceneName": scene, "captureVariants": ["clear"], "baseTilesX": 1, "baseTilesY": 1, "maxZoom": 0}


class _FakeMod:
    """Answers capture requests the way MapTileCapture does, per zone behaviour."""

    def __init__(self, behaviour: dict[str, str]) -> None:
        self.behaviour = behaviour
        self._responses: list[dict[str, Any]] = []

    async def send(self, raw: str) -> None:
        request = json.loads(raw)
        outcome = self.behaviour[request["zone"]]
        if outcome == "error":
            self._responses = [{"type": "capture_error", "reason": "scene failed to load"}]
            return
        self._responses = []
        if outcome == "ok":
            for chunk in request["chunks"]:
                path = from_wine_path(chunk["outputPath"])
                Image.new("RGBA", (chunk["pixelWidth"], chunk["pixelHeight"]), (10, 20, 30, 255)).save(path)
                self._responses.append(
                    {"type": "chunk_complete", "chunkIndex": chunk["index"], "path": chunk["outputPath"]}
                )
        self._responses.append({"type": "capture_zone_complete", "roofObjectCount": 0})

    async def recv(self) -> str:
        return json.dumps(self._responses.pop(0))

    async def close(self) -> None:
        pass


def _run_capture_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, behaviour: dict[str, str]) -> Path:
    maps_source_dir = tmp_path / "maps"
    config = {zone: _zone(zone) for zone in behaviour}
    path = maps_source_dir / "src/lib/data/zone-capture-config.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config))
    monkeypatch.setattr("erenshor.application.capture.zone_config.load_zone_config", lambda _path: config)

    async def connect(self: orchestrator.CaptureOrchestrator) -> None:
        self._ws = _FakeMod(behaviour)

    monkeypatch.setattr(orchestrator.CaptureOrchestrator, "connect", connect)
    capture_command.run(_context(tmp_path), zones=None, variant=None, force=False)
    return maps_source_dir / "static" / "tiles"


def test_failed_zone_fails_the_run_and_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit) as exit_info:
        _run_capture_command(tmp_path, monkeypatch, {"Broken": "error", "Good": "ok"})

    assert exit_info.value.exit_code == 1
    output = capsys.readouterr().out
    assert "Broken/clear: scene failed to load" in output
    assert "partial" in output
    assert "Capture pipeline complete" not in output
    assert (tmp_path / "maps" / "static" / "tiles" / "Good").is_dir()


def test_completion_without_chunks_is_a_failure_not_a_stale_master(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stale_master = tmp_path / ".erenshor" / "masters" / "Empty_clear.png"
    stale_master.parent.mkdir(parents=True)
    Image.new("RGBA", (256, 256)).save(stale_master)

    with pytest.raises(typer.Exit):
        _run_capture_command(tmp_path, monkeypatch, {"Empty": "no-chunks"})

    assert "Empty/clear: mod completed the capture with 0 of 1 chunks" in capsys.readouterr().out
    assert not (tmp_path / "maps" / "static" / "tiles" / "Empty").exists()


def test_run_where_every_zone_succeeds_reports_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tiles = _run_capture_command(tmp_path, monkeypatch, {"First": "ok", "Second": "ok"})

    assert "Capture pipeline complete" in capsys.readouterr().out
    assert sorted(path.name for path in tiles.iterdir()) == ["First", "Second"]


def test_retile_fails_and_names_zones_without_a_master(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    maps_source_dir = tmp_path / "maps"
    config = {"Captured": _zone("Captured"), "Uncaptured": _zone("Uncaptured")}
    path = maps_source_dir / "src/lib/data/zone-capture-config.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config))
    monkeypatch.setattr("erenshor.application.capture.zone_config.load_zone_config", lambda _path: config)
    master = tmp_path / ".erenshor" / "masters" / "Captured_clear.png"
    master.parent.mkdir(parents=True)
    Image.new("RGBA", (256, 256)).save(master)
    state = orchestrator.CaptureState({"zones": {"Captured": {"clear": {"status": "ok", "masterPath": str(master)}}}})
    state.save(tmp_path)
    with pytest.raises(typer.Exit) as exit_info:
        capture_command.tile(_context(tmp_path), zones=None)

    assert exit_info.value.exit_code == 1
    assert "Uncaptured/clear: no captured master" in capsys.readouterr().out
    assert not (maps_source_dir / "static" / "tiles" / "Captured").exists()
