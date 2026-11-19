"""Bind a tooltip parity result to the exact build and renderer inputs."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from erenshor.application.extract.database_comparison import recorded_build_id
from erenshor.application.wiki_tooltips.capture import reconcile


@dataclass(frozen=True, slots=True)
class ParityPaths:
    root: Path
    database: Path
    wiki: Path

    @property
    def output(self) -> Path:
        return self.wiki / "tooltip-parity"

    @property
    def evidence(self) -> Path:
        return self.output / "game.json"

    @property
    def report(self) -> Path:
        return self.output / "report.json"

    def is_page_input(self, source: Path) -> bool:
        """Identify publication inputs without reading an old report."""
        relative = (self.root / source).resolve()
        return any(
            relative.is_relative_to(directory.resolve())
            for directory in (
                self.wiki / "generated",
                self.wiki / "lua/Erenshor/Data",
                self.root / "wiki/modules",
                self.root / "wiki/templates",
            )
        )

    def inputs(self) -> dict[str, str]:
        """Hash each input separately so a stale report names the changed source."""
        paths = [self.evidence, self.database, self.root / "wiki/gadgets/erenshor.css"]
        for base, pattern in (
            (self.wiki / "generated", "*.txt"),
            (self.wiki / "lua/Erenshor/Data", "*.lua"),
            (self.root / "wiki/modules", "*.lua"),
            (self.root / "wiki/templates", "*"),
            (Path(__file__).parent, "*"),
        ):
            paths.extend(
                path
                for path in base.rglob(pattern)
                if path.is_file()
                and path.suffix
                in {
                    ".txt",
                    ".lua",
                    ".wiki",
                    ".css",
                    ".py",
                    ".cs",
                }
            )
        paths.extend(
            self.root / "wiki-dev" / name
            for name in (
                "compose.yml",
                "Dockerfile",
                "bootstrap.sh",
                "LocalSettings.extra.php",
                "import_pages.py",
                "tooltip_parity.py",
                "smoke/mediawiki.py",
                "smoke/render.py",
            )
        )
        hashes = {}
        for path in sorted(set(paths)):
            with path.open("rb") as source:
                key = path.resolve().relative_to(self.root.resolve()).as_posix()
                hashes[key] = hashlib.file_digest(source, "sha256").hexdigest()
        return hashes


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    temporary.replace(path)


def require_current(paths: ParityPaths) -> None:
    """Reject a missing, failing, incomplete, inconsistent, or stale report."""
    try:
        report = read_json(paths.report)
        if report.get("schema") != 1 or report.get("complete") is not True or report.get("findings") != []:
            raise ValueError("comparison did not finish without findings")
        evidence = read_json(paths.evidence)
        build = recorded_build_id(paths.database)
        if report.get("build") != build or evidence.get("build") != build or evidence.get("installed_build") != build:
            raise ValueError(f"expected clean database build {build}")
        entries = evidence.get("entries")
        if evidence.get("failures") != [] or not entries:
            raise ValueError("missing collection coverage")
        excluded = reconcile(paths.database.resolve(), entries)
        if excluded != evidence.get("exclusions") or excluded != report.get("exclusions"):
            raise ValueError("collection and report exclusions do not match the database")
        hidden = {row["stable_key"] for row in excluded}
        published = {entry["stable_key"] for entry in entries} | {
            entry["stance_key"] for entry in entries if "stance_key" in entry
        }
        expected = Counter(key.split(":", 1)[0] for key in published - hidden)
        expected["item_cards"] = sum(entry["kind"] == "item" and entry["stable_key"] not in hidden for entry in entries)
        if report.get("coverage") != dict(expected):
            raise ValueError(f"expected complete coverage: {dict(expected)}")
        recorded = report.get("inputs")
        current = paths.inputs()
        if not isinstance(recorded, dict):
            raise ValueError("missing input hashes")
        changed = sorted(key for key in current.keys() | recorded.keys() if current.get(key) != recorded.get(key))
        if changed:
            raise ValueError(f"changed inputs: {', '.join(changed)}")
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        raise ValueError(f"Tooltip parity report {paths.report} cannot be used: {exc}") from exc
