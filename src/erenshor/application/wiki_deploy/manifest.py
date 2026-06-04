"""Repo-owned wiki page deployment manifest."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ContentModel = Literal["Scribunto", "wikitext"]
UploadStage = Literal["generated_data", "lua_module", "cargo_declaration", "template"]

_CARGO_TABLE_RE = re.compile(r"_table\s*=\s*([A-Za-z_][A-Za-z0-9_]*)")
_STAGE_ORDER: dict[UploadStage, int] = {
    "generated_data": 0,
    "lua_module": 1,
    "cargo_declaration": 2,
    "template": 3,
}


@dataclass(frozen=True, slots=True)
class RepoWikiPageManifestEntry:
    """One repo-owned wiki page eligible for safe deployment."""

    title: str
    source_path: str
    source_sha256: str
    ownership_class: UploadStage
    upload_stage: UploadStage
    content_model: ContentModel
    declares_cargo_table: bool
    cargo_tables: tuple[str, ...]
    old_revision_id: int | None = None
    old_revision_timestamp: str | None = None
    new_revision_id: int | None = None
    new_revision_timestamp: str | None = None
    rollback_text_source: str | None = None
    null_edit_targets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepoWikiPageManifest:
    """Deploy manifest for repo-owned wiki pages."""

    entries: tuple[RepoWikiPageManifestEntry, ...]


def build_repo_page_manifest(repo_root: Path, variant: str) -> RepoWikiPageManifest:
    """Build a deterministic manifest for repo-owned module/template/data pages."""
    root = repo_root.resolve()
    entries: list[RepoWikiPageManifestEntry] = []

    entries.extend(_module_entries(root, root / "variants" / variant / "wiki" / "lua", "generated_data"))
    entries.extend(_module_entries(root, root / "wiki" / "modules", "lua_module"))
    entries.extend(_template_entries(root, root / "wiki" / "templates"))

    entries.sort(key=lambda entry: (_STAGE_ORDER[entry.upload_stage], entry.title))
    return RepoWikiPageManifest(entries=tuple(entries))


def _module_entries(
    root: Path, source_root: Path, stage: Literal["generated_data", "lua_module"]
) -> list[RepoWikiPageManifestEntry]:
    if not source_root.exists():
        return []

    entries: list[RepoWikiPageManifestEntry] = []
    for path in source_root.rglob("*.lua"):
        if not path.is_file():
            continue
        relative_module = path.relative_to(source_root).with_suffix("")
        title = "Module:" + "/".join(relative_module.parts)
        entries.append(
            _entry(
                root=root,
                path=path,
                title=title,
                content_model="Scribunto",
                ownership_class=stage,
                upload_stage=stage,
                declares_cargo_table=False,
                cargo_tables=(),
            )
        )
    return entries


def _template_entries(root: Path, source_root: Path) -> list[RepoWikiPageManifestEntry]:
    if not source_root.exists():
        return []

    entries: list[RepoWikiPageManifestEntry] = []
    for path in source_root.rglob("*.wiki"):
        if not path.is_file():
            continue
        relative_template = path.relative_to(source_root).with_suffix("")
        title = "Template:" + "/".join(relative_template.parts)
        content = path.read_text(encoding="utf-8")
        declares_cargo_table = _declares_real_cargo_table(title, content)
        cargo_tables = _cargo_tables(content) if declares_cargo_table else ()
        upload_stage: UploadStage = "cargo_declaration" if declares_cargo_table else "template"
        entries.append(
            _entry(
                root=root,
                path=path,
                title=title,
                content_model="wikitext",
                ownership_class=upload_stage,
                upload_stage=upload_stage,
                declares_cargo_table=declares_cargo_table,
                cargo_tables=cargo_tables,
            )
        )
    return entries


def _entry(
    *,
    root: Path,
    path: Path,
    title: str,
    content_model: ContentModel,
    ownership_class: UploadStage,
    upload_stage: UploadStage,
    declares_cargo_table: bool,
    cargo_tables: tuple[str, ...],
) -> RepoWikiPageManifestEntry:
    source_bytes = path.read_bytes()
    return RepoWikiPageManifestEntry(
        title=title,
        source_path=path.relative_to(root).as_posix(),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        ownership_class=ownership_class,
        upload_stage=upload_stage,
        content_model=content_model,
        declares_cargo_table=declares_cargo_table,
        cargo_tables=cargo_tables,
    )


def _declares_real_cargo_table(title: str, content: str) -> bool:
    if title.endswith("/CargoDeclare"):
        return False
    return "#cargo_declare" in content


def _cargo_tables(content: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group(1) for match in _CARGO_TABLE_RE.finditer(content)))
