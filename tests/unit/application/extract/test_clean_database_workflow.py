from __future__ import annotations

import sqlite3
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from erenshor.application.extract.clean_database_workflow import (
    CleanDatabaseRequest,
    CleanDatabaseResult,
    CleanDatabaseWorkflow,
    CleanDatabaseWorkflowError,
)
from erenshor.infrastructure.config.paths import PathResolutionError


def _request(tmp_path: Path) -> CleanDatabaseRequest:
    return CleanDatabaseRequest(
        repo_root=tmp_path,
        raw_db_path=tmp_path / "database_raw.sqlite",
        clean_db_path=tmp_path / "database.sqlite",
        mapping_json_path=tmp_path / "mapping.json",
        barriers_path=tmp_path / "barriers.toml",
        export_dir=tmp_path / "ExportedProject",
        images_dir=tmp_path / "images",
    )


def _write_sqlite(path: Path, image_hashes: tuple[str, ...] = ()) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE built (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE images (image_hash TEXT PRIMARY KEY)")
        connection.executemany("INSERT INTO images VALUES (?)", [(image_hash,) for image_hash in image_hashes])


def test_success_passes_resolved_inputs_and_publishes_only_builder_output(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.clean_db_path.write_bytes(b"old")
    calls: list[dict[str, object]] = []

    def builder(**kwargs: object) -> None:
        calls.append(kwargs)
        staged_path = kwargs["clean_db_path"]
        assert isinstance(staged_path, Path)
        assert staged_path != request.clean_db_path
        _write_sqlite(staged_path)

    result = CleanDatabaseWorkflow(builder).run(request)

    assert result == CleanDatabaseResult(clean_db_path=request.clean_db_path)
    with sqlite3.connect(request.clean_db_path) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'built'").fetchone() == ("built",)
    assert calls == [
        {
            "raw_db_path": request.raw_db_path,
            "clean_db_path": calls[0]["clean_db_path"],
            "mapping_json_path": request.mapping_json_path,
            "barriers_path": request.barriers_path,
            "export_dir": request.export_dir,
            "images_dir": request.images_dir,
        }
    ]
    assert not list(tmp_path.glob(".database.sqlite.*.tmp"))


def test_builder_failure_preserves_previous_clean_database(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.clean_db_path.write_bytes(b"old")

    def builder(**kwargs: object) -> None:
        staged_path = kwargs["clean_db_path"]
        assert isinstance(staged_path, Path)
        staged_path.write_bytes(b"partial")
        raise RuntimeError("processor failed")

    with pytest.raises(RuntimeError, match="processor failed"):
        CleanDatabaseWorkflow(builder).run(request)

    assert request.clean_db_path.read_bytes() == b"old"
    assert not list(tmp_path.glob(".database.sqlite.*.tmp"))


def test_missing_builder_output_fails_and_preserves_previous_clean_database(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.clean_db_path.write_bytes(b"old")

    with pytest.raises(CleanDatabaseWorkflowError, match="did not produce"):
        CleanDatabaseWorkflow(lambda **_kwargs: None).run(request)

    assert request.clean_db_path.read_bytes() == b"old"
    assert not list(tmp_path.glob(".database.sqlite.*.tmp"))


@pytest.mark.parametrize(
    ("output_kind", "message"),
    [
        ("empty", "empty output"),
        ("invalid", "invalid SQLite database"),
        ("directory", "not a file"),
    ],
)
def test_invalid_builder_output_fails_and_cleans_staging(
    tmp_path: Path,
    output_kind: str,
    message: str,
) -> None:
    request = _request(tmp_path)
    request.clean_db_path.write_bytes(b"old")

    def builder(**kwargs: object) -> None:
        staged_path = kwargs["clean_db_path"]
        assert isinstance(staged_path, Path)
        if output_kind == "empty":
            staged_path.touch()
        elif output_kind == "invalid":
            staged_path.write_bytes(b"not sqlite")
        else:
            staged_path.mkdir()

    with pytest.raises(CleanDatabaseWorkflowError, match=message):
        CleanDatabaseWorkflow(builder).run(request)

    assert request.clean_db_path.read_bytes() == b"old"
    assert not list(tmp_path.glob(".database.sqlite.*.tmp"))


def test_request_and_result_are_immutable(tmp_path: Path) -> None:
    request = _request(tmp_path)
    result = CleanDatabaseResult(clean_db_path=request.clean_db_path)

    with pytest.raises(FrozenInstanceError):
        request.raw_db_path = tmp_path / "other.sqlite"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.clean_db_path = tmp_path / "other.sqlite"  # type: ignore[misc]


def test_publication_prunes_the_catalog_files_that_the_new_database_does_not_reference(tmp_path: Path) -> None:
    request = _request(tmp_path)
    catalog = request.images_dir / "catalog"
    catalog.mkdir(parents=True)
    (catalog / "kept.png").write_bytes(b"kept")
    (catalog / "gone.png").write_bytes(b"gone")

    def builder(**kwargs: object) -> None:
        staged_path = kwargs["clean_db_path"]
        assert isinstance(staged_path, Path)
        _write_sqlite(staged_path, ("kept",))

    CleanDatabaseWorkflow(builder).run(request)

    assert sorted(path.name for path in catalog.iterdir()) == ["kept.png"]


def test_a_failed_build_leaves_every_catalog_file(tmp_path: Path) -> None:
    request = _request(tmp_path)
    catalog = request.images_dir / "catalog"
    catalog.mkdir(parents=True)
    (catalog / "kept.png").write_bytes(b"kept")

    def builder(**_: object) -> None:
        raise RuntimeError("build failed")

    with pytest.raises(RuntimeError, match="build failed"):
        CleanDatabaseWorkflow(builder).run(request)

    assert [path.name for path in catalog.iterdir()] == ["kept.png"]


@pytest.mark.parametrize("destination_kind", ["file_symlink", "directory_symlink", "absolute", "images"])
def test_cross_checkout_outputs_fail_before_builder_or_staging(tmp_path: Path, destination_kind: str) -> None:
    root = tmp_path / "worktree"
    root.mkdir()
    (root / ".git").write_text("gitdir: ../main/.git/worktrees/test")
    owner = tmp_path / "main"
    owner.mkdir()
    (owner / ".git").mkdir()
    target = owner / "database.sqlite"
    target.write_bytes(b"original")
    request = _request(root)
    if destination_kind == "file_symlink":
        request.clean_db_path.symlink_to(target)
    elif destination_kind == "directory_symlink":
        (root / "shared").symlink_to(owner, target_is_directory=True)
        request = replace(request, clean_db_path=root / "shared/database.sqlite")
    elif destination_kind == "absolute":
        request = replace(request, clean_db_path=target)
    else:
        (root / "images").symlink_to(owner / "images", target_is_directory=True)
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

    def builder(**_kwargs: object) -> None:
        pytest.fail("builder must not run for another checkout's output")

    with pytest.raises(PathResolutionError, match="Refusing cross-checkout write"):
        CleanDatabaseWorkflow(builder).run(request)

    assert target.read_bytes() == b"original"
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")) == before


def test_owned_database_accepts_read_only_shared_inputs(tmp_path: Path) -> None:
    root = tmp_path / "worktree"
    root.mkdir()
    (root / ".git").write_text("gitdir: ../main/.git/worktrees/test")
    owner = tmp_path / "main"
    owner.mkdir()
    (owner / ".git").mkdir()
    raw = owner / "database_raw.sqlite"
    raw.write_bytes(b"read-only input")
    raw.chmod(0o444)
    unity = owner / "unity"
    unity.mkdir()
    request = _request(root)
    request.raw_db_path.symlink_to(raw)
    request.export_dir.symlink_to(unity, target_is_directory=True)

    def builder(**kwargs: object) -> None:
        staged = kwargs["clean_db_path"]
        assert isinstance(staged, Path)
        assert request.raw_db_path.read_bytes() == b"read-only input"
        assert request.export_dir.resolve() == unity.resolve()
        _write_sqlite(staged)

    CleanDatabaseWorkflow(builder).run(request)

    assert request.clean_db_path.is_file()
    assert not request.clean_db_path.is_symlink()
    assert raw.read_bytes() == b"read-only input"
