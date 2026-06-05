"""Repo-owned wiki page deployment manifest."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

ContentModel = Literal["Scribunto", "wikitext", "sanitized-css"]
UploadStage = Literal["gadget", "generated_data", "lua_module", "cargo_declaration", "template"]
DeployAction = Literal["unchanged", "created", "edited"]

_CARGO_TABLE_RE = re.compile(r"_table\s*=\s*([A-Za-z_][A-Za-z0-9_]*)")
_STAGE_ORDER: dict[UploadStage, int] = {
    "gadget": 0,
    "generated_data": 1,
    "lua_module": 2,
    "cargo_declaration": 3,
    "template": 4,
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
    deploy_action: DeployAction | None = None
    null_edit_targets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepoWikiPageManifest:
    """Deploy manifest for repo-owned wiki pages."""

    entries: tuple[RepoWikiPageManifestEntry, ...]


def build_repo_page_manifest(repo_root: Path, variant: str) -> RepoWikiPageManifest:
    """Build a deterministic manifest for repo-owned module/template/data pages."""
    root = repo_root.resolve()
    entries: list[RepoWikiPageManifestEntry] = []

    entries.extend(_gadget_entries(root, root / "wiki" / "gadgets"))
    entries.extend(_module_entries(root, root / "variants" / variant / "wiki" / "lua", "generated_data"))
    entries.extend(_module_entries(root, root / "wiki" / "modules", "lua_module"))
    entries.extend(_template_entries(root, root / "wiki" / "templates"))

    entries.sort(key=lambda entry: (_STAGE_ORDER[entry.upload_stage], entry.title))
    return RepoWikiPageManifest(entries=tuple(entries))


def write_repo_page_manifest(manifest: RepoWikiPageManifest, path: Path) -> None:
    """Write a repo-owned wiki page manifest as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": [asdict(entry) for entry in manifest.entries]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_repo_page_manifest(path: Path) -> RepoWikiPageManifest:
    """Read a repo-owned wiki page manifest written by ``write_repo_page_manifest``."""
    payload = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    raw_entries = cast("list[dict[str, object]]", payload["entries"])
    entries = tuple(_entry_from_payload(raw_entry) for raw_entry in raw_entries)
    return RepoWikiPageManifest(entries=entries)


def _entry_from_payload(raw_entry: dict[str, object]) -> RepoWikiPageManifestEntry:
    return RepoWikiPageManifestEntry(
        title=str(raw_entry["title"]),
        source_path=str(raw_entry["source_path"]),
        source_sha256=str(raw_entry["source_sha256"]),
        ownership_class=_upload_stage(str(raw_entry["ownership_class"])),
        upload_stage=_upload_stage(str(raw_entry["upload_stage"])),
        content_model=_content_model(str(raw_entry["content_model"])),
        declares_cargo_table=bool(raw_entry["declares_cargo_table"]),
        cargo_tables=tuple(str(table) for table in cast("list[object]", raw_entry["cargo_tables"])),
        old_revision_id=_optional_int(raw_entry.get("old_revision_id")),
        old_revision_timestamp=_optional_str(raw_entry.get("old_revision_timestamp")),
        new_revision_id=_optional_int(raw_entry.get("new_revision_id")),
        new_revision_timestamp=_optional_str(raw_entry.get("new_revision_timestamp")),
        rollback_text_source=_optional_str(raw_entry.get("rollback_text_source")),
        deploy_action=_optional_deploy_action(raw_entry.get("deploy_action")),
        null_edit_targets=tuple(str(title) for title in cast("list[object]", raw_entry["null_edit_targets"])),
    )


def _upload_stage(value: str) -> UploadStage:
    if value not in _STAGE_ORDER:
        raise ValueError(f"Unknown wiki deploy upload stage: {value}")
    return value  # type: ignore[return-value]


def _content_model(value: str) -> ContentModel:
    if value not in ("Scribunto", "wikitext", "sanitized-css"):
        raise ValueError(f"Unknown wiki deploy content model: {value}")
    return value  # type: ignore[return-value]


def _optional_deploy_action(value: object) -> DeployAction | None:
    if value is None:
        return None
    text = str(value)
    if text not in ("unchanged", "created", "edited"):
        raise ValueError(f"Unknown wiki deploy action: {text}")
    return text  # type: ignore[return-value]


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Expected int-compatible value, got {type(value).__name__}")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _gadget_entries(root: Path, source_root: Path) -> list[RepoWikiPageManifestEntry]:
    if not source_root.exists():
        return []

    entries: list[RepoWikiPageManifestEntry] = []
    for path in sorted(source_root.rglob("*.css")):
        if not path.is_file():
            continue
        title = "MediaWiki:Gadget-" + path.name
        entries.append(
            _entry(
                root=root,
                path=path,
                title=title,
                content_model="sanitized-css",
                ownership_class="gadget",
                upload_stage="gadget",
                declares_cargo_table=False,
                cargo_tables=(),
            )
        )
    return entries


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
