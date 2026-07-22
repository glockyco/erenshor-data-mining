"""Tests for maps build provenance sidecar hashing."""

from pathlib import Path

from erenshor.application.maps import build_info


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    repo_dir = tmp_path / "repo"
    maps_dir = repo_dir / "src" / "maps"
    (maps_dir / "src").mkdir(parents=True)
    (maps_dir / "static" / "tiles" / "0" / "0").mkdir(parents=True)

    (maps_dir / "package.json").write_text('{"scripts": {}}\n')
    (maps_dir / "vite.config.ts").write_text("export default {};\n")
    (maps_dir / "wrangler.jsonc").write_text('{"name": "erenshor-maps"}\n')
    (repo_dir / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    (maps_dir / "src" / "app.ts").write_text("export const answer = 42;\n")
    (maps_dir / "static" / "tiles" / "tiles-manifest.json").write_text('{"tiles": 1}\n')
    (maps_dir / "static" / "tiles" / "0" / "0" / "0.png").write_bytes(b"tile")

    database_path = tmp_path / "erenshor.sqlite"
    database_path.write_bytes(b"sqlite")
    return maps_dir, database_path


def test_compute_input_hashes_is_deterministic(tmp_path: Path) -> None:
    maps_dir, database_path = _write_inputs(tmp_path)

    first = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)
    second = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    assert first == second
    assert set(first) == {"code", "data", "tiles"}


def test_database_change_flips_only_data_group(tmp_path: Path) -> None:
    maps_dir, database_path = _write_inputs(tmp_path)
    before = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    database_path.write_bytes(b"changed")
    after = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    assert build_info.changed_groups(before, after) == {"data"}


def test_code_change_flips_only_code_group(tmp_path: Path) -> None:
    maps_dir, database_path = _write_inputs(tmp_path)
    before = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    (maps_dir / "src" / "app.ts").write_text("export const answer = 43;\n")
    after = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    assert build_info.changed_groups(before, after) == {"code"}


def test_worker_config_change_flips_only_code_group(tmp_path: Path) -> None:
    maps_dir, database_path = _write_inputs(tmp_path)
    before = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    (maps_dir / "wrangler.jsonc").write_text('{"name": "erenshor-maps", "compatibility_date": "2026-07-14"}\n')
    after = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    assert build_info.changed_groups(before, after) == {"code"}


def test_lockfile_change_flips_only_code_group(tmp_path: Path) -> None:
    maps_dir, database_path = _write_inputs(tmp_path)
    before = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    (maps_dir.parents[1] / "pnpm-lock.yaml").write_text(
        "lockfileVersion: '9.0'\nsettings:\n  autoInstallPeers: false\n"
    )
    after = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    assert build_info.changed_groups(before, after) == {"code"}


def test_tile_manifest_change_flips_only_tiles_group(tmp_path: Path) -> None:
    maps_dir, database_path = _write_inputs(tmp_path)
    before = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    (maps_dir / "static" / "tiles" / "tiles-manifest.json").write_text('{"tiles": 2}\n')
    after = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)

    assert build_info.changed_groups(before, after) == {"tiles"}


def test_write_build_info_is_atomic_and_readable(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    hashes = {"code": "abc", "data": "def", "tiles": "jkl"}

    build_info.write_build_info(build_dir, hashes)

    assert build_info.read_build_info(build_dir) == hashes
    assert not list(build_dir.glob("*.tmp"))


def test_read_build_info_rejects_legacy_mods_group(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / build_info.BUILD_INFO_NAME).write_text(
        '{"code": "abc", "data": "def", "tiles": "jkl", "mods": "legacy"}\n'
    )

    assert build_info.read_build_info(build_dir) is None


def test_read_build_info_returns_none_when_missing(tmp_path: Path) -> None:
    assert build_info.read_build_info(tmp_path / "build") is None
