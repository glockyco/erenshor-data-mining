"""Unit tests for maps precondition checks."""

from pathlib import Path

import pytest

from erenshor.application.maps import build_info
from erenshor.cli.preconditions.checks import maps


def _write_maps_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    maps_dir = tmp_path / "maps"
    build_dir = maps_dir / "build"
    (maps_dir / "src").mkdir(parents=True)
    (maps_dir / "static" / "db").mkdir(parents=True)
    (maps_dir / "package.json").write_text("{}\n")
    (maps_dir / "src" / "app.ts").write_text("export const ok = true;\n")
    database_path = tmp_path / "erenshor.sqlite"
    database_path.write_bytes(b"sqlite")
    return maps_dir, build_dir, database_path


def test_build_exists_requires_non_empty_directory(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"

    missing = maps.build_exists({"build_dir": build_dir})
    assert missing.passed is False
    assert "maps build" in missing.detail

    build_dir.mkdir()
    empty = maps.build_exists({"build_dir": build_dir})
    assert empty.passed is False

    (build_dir / "index.html").write_text("<h1>ok</h1>\n")
    present = maps.build_exists({"build_dir": build_dir})
    assert present.passed is True


def test_build_matches_inputs_requires_sidecar(tmp_path: Path) -> None:
    maps_dir, build_dir, database_path = _write_maps_inputs(tmp_path)
    build_dir.mkdir()

    result = maps.build_matches_inputs(
        {"maps_source_dir": maps_dir, "build_dir": build_dir, "database_path": database_path}
    )

    assert result.passed is False
    assert "maps build" in result.detail


def test_build_matches_inputs_reports_changed_groups(tmp_path: Path) -> None:
    maps_dir, build_dir, database_path = _write_maps_inputs(tmp_path)
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<h1>ok</h1>\n")
    hashes = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)
    build_info.write_build_info(build_dir, hashes)

    (maps_dir / "src" / "app.ts").write_text("export const ok = false;\n")
    result = maps.build_matches_inputs(
        {"maps_source_dir": maps_dir, "build_dir": build_dir, "database_path": database_path}
    )

    assert result.passed is False
    assert "code" in result.detail


def test_build_matches_inputs_passes_for_fresh_sidecar(tmp_path: Path) -> None:
    maps_dir, build_dir, database_path = _write_maps_inputs(tmp_path)
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<h1>ok</h1>\n")
    hashes = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)
    build_info.write_build_info(build_dir, hashes)

    result = maps.build_matches_inputs(
        {"maps_source_dir": maps_dir, "build_dir": build_dir, "database_path": database_path}
    )

    assert result.passed is True


def test_cloudflare_auth_configured_passes_with_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")

    result = maps.cloudflare_auth_configured({"maps_source_dir": Path("configured/maps")})

    assert result.passed is True


def test_cloudflare_auth_configured_requires_maps_source_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setattr(maps.shutil, "which", lambda _name: None)

    with pytest.raises(KeyError, match="maps_source_dir"):
        maps.cloudflare_auth_configured({})


def test_cloudflare_auth_configured_fails_without_token_or_wrangler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setattr(maps.shutil, "which", lambda _name: None)

    result = maps.cloudflare_auth_configured({"maps_source_dir": Path("configured/maps")})

    assert result.passed is False
    assert "CLOUDFLARE_API_TOKEN" in result.detail
