"""Build provenance sidecar support for the maps website."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path

BUILD_INFO_NAME = ".build-info.json"
_INPUT_GROUPS = ("code", "data", "tiles")
_CODE_EXTENSIONS = {".ts", ".js", ".svelte", ".css", ".html", ".json"}
_CONFIG_FILES = (
    "package.json",
    "svelte.config.js",
    "vite.config.ts",
    "tailwind.config.js",
    "tailwind.config.cjs",
    "tailwind.config.ts",
    "postcss.config.js",
    "postcss.config.cjs",
    "wrangler.jsonc",
)
_ROOT_CONFIG_FILES = ("pnpm-lock.yaml",)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_files(paths: Iterable[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        relative_path = path.relative_to(root).as_posix().encode()
        digest.update(relative_path)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _code_hash(maps_source_dir: Path) -> str:
    source_dir = maps_source_dir / "src"
    paths: list[Path] = []
    if source_dir.is_dir():
        paths.extend(path for path in source_dir.rglob("*") if path.is_file() and path.suffix in _CODE_EXTENSIONS)
    paths.extend(maps_source_dir / name for name in _CONFIG_FILES if (maps_source_dir / name).is_file())
    repo_root = maps_source_dir.parent.parent
    paths.extend(repo_root / name for name in _ROOT_CONFIG_FILES if (repo_root / name).is_file())
    return _hash_files(paths, repo_root)


def _tiles_hash(maps_source_dir: Path) -> str:
    tiles_dir = maps_source_dir / "static" / "tiles"
    if not tiles_dir.is_dir():
        return ""

    tile_files = [path for path in tiles_dir.rglob("*") if path.is_file()]
    manifest_path = tiles_dir / "tiles-manifest.json"
    manifest_bytes = manifest_path.read_bytes() if manifest_path.is_file() else b""
    total_bytes = sum(path.stat().st_size for path in tile_files)
    summary = json.dumps(
        {
            "manifest": manifest_bytes.decode(errors="surrogateescape"),
            "file_count": len(tile_files),
            "total_bytes": total_bytes,
        },
        sort_keys=True,
    )
    return _sha(summary.encode())


def compute_input_hashes(*, maps_source_dir: Path, database_path: Path) -> dict[str, str]:
    """Compute input hashes that describe the current maps build inputs."""
    return {
        "code": _code_hash(maps_source_dir),
        "data": _sha(database_path.read_bytes()) if database_path.is_file() else "",
        "tiles": _tiles_hash(maps_source_dir),
    }


def changed_groups(before: dict[str, str], after: dict[str, str]) -> set[str]:
    """Return input groups whose hashes differ between two snapshots."""
    return {group for group in _INPUT_GROUPS if before.get(group) != after.get(group)}


def write_build_info(build_dir: Path, hashes: dict[str, str]) -> None:
    """Atomically write the build input hash sidecar into a build directory."""
    build_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = build_dir / BUILD_INFO_NAME
    tmp_path = sidecar_path.with_name(f"{BUILD_INFO_NAME}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(sidecar_path)


def read_build_info(build_dir: Path) -> dict[str, str] | None:
    """Read the build input hash sidecar, returning None when it is absent or invalid."""
    sidecar_path = build_dir / BUILD_INFO_NAME
    if not sidecar_path.is_file():
        return None

    try:
        data = json.loads(sidecar_path.read_text())
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None
    if set(data) != set(_INPUT_GROUPS):
        return None
    if not all(isinstance(value, str) for value in data.values()):
        return None
    return data
