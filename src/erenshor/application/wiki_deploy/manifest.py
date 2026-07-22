"""Repo-owned wiki page deployment manifest."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

ContentModel = Literal["Scribunto", "wikitext"]
UploadStage = Literal["generated_data", "lua_module", "cargo_declaration", "template", "content_page"]
DeployAction = Literal["unchanged", "created", "edited"]

_CARGO_TABLE_RE = re.compile(r"_table\s*=\s*([A-Za-z_][A-Za-z0-9_]*)")
_DIRECT_DATA_LINK_CONSUMER_TITLES = frozenset(
    {
        "Module:Erenshor/Link",
        "Module:Erenshor/AbilityLink",
        "Module:Erenshor/Link/Search",
        "Module:Erenshor/Item",
    }
)
_STAGE_ORDER: dict[UploadStage, int] = {
    "generated_data": 0,
    "lua_module": 1,
    "cargo_declaration": 2,
    "template": 3,
    "content_page": 4,
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
    """Deployable content pages; MediaWiki interface pages are forbidden."""

    entries: tuple[RepoWikiPageManifestEntry, ...]

    def __post_init__(self) -> None:
        interface_titles = [entry.title for entry in self.entries if _is_mediawiki_interface_title(entry.title)]
        if interface_titles:
            raise ValueError(
                "Ordinary repo-page manifests cannot contain MediaWiki interface pages: " + ", ".join(interface_titles)
            )

        entries_by_title: dict[str, list[RepoWikiPageManifestEntry]] = {}
        for entry in self.entries:
            entries_by_title.setdefault(entry.title, []).append(entry)
        for title in sorted(entries_by_title):
            conflicting_entries = entries_by_title[title]
            if len(conflicting_entries) < 2:
                continue
            first, second = sorted(
                conflicting_entries,
                key=lambda entry: (entry.source_path, entry.upload_stage),
            )[:2]
            raise ValueError(
                f"Duplicate wiki page title {title!r}: "
                f"{first.source_path} (stage {first.upload_stage}) conflicts with "
                f"{second.source_path} (stage {second.upload_stage})"
            )


def _is_mediawiki_interface_title(title: str) -> bool:
    """Return whether MediaWiki normalizes ``title`` into its interface namespace.

    Namespace names are case-insensitive, and MediaWiki ignores surrounding
    whitespace when normalizing page titles.  Only the namespace prefix before
    the first colon is significant; occurrences of ``MediaWiki`` later in the
    title are ordinary page content.
    """
    normalized_title = title.strip()
    namespace, separator, _ = normalized_title.partition(":")
    return bool(separator) and namespace.casefold() == "mediawiki"


def build_repo_page_manifest(
    repo_root: Path,
    variant: str,
    *,
    include_templates: bool = False,
    include_generated_data: bool = False,
    include_content_pages: bool = False,
    requested_titles: set[str] | None = None,
) -> RepoWikiPageManifest:
    """Build a deterministic manifest for the safe default deployment surface.

    Generated Lua data under ``variants/<variant>/wiki/lua`` and maintained
    content pages under ``wiki/content`` are intentionally local-only until
    their deployment surfaces are explicitly opted into. Templates remain
    opt-in because changing them affects every generated wiki page. When
    ``requested_titles`` is supplied, matching optional entries are included
    only so selection can validate their ownership and opt-in requirements;
    an unfiltered manifest remains modules-only.
    """
    root = repo_root.resolve()
    entries: list[RepoWikiPageManifestEntry] = []

    if include_generated_data or requested_titles is not None:
        entries.extend(
            _module_entries(
                root,
                root / "variants" / variant / "wiki" / "lua",
                "generated_data",
                requested_titles=None if include_generated_data else requested_titles,
            )
        )
    entries.extend(_module_entries(root, root / "wiki" / "modules", "lua_module"))
    if include_templates or requested_titles is not None:
        entries.extend(
            _template_entries(
                root,
                root / "wiki" / "templates",
                requested_titles=None if include_templates else requested_titles,
            )
        )
    if include_content_pages or requested_titles is not None:
        entries.extend(
            _content_entries(
                root,
                root / "wiki" / "content",
                requested_titles=None if include_content_pages else requested_titles,
            )
        )

    entries.sort(key=lambda entry: (_STAGE_ORDER[entry.upload_stage], entry.title))
    return RepoWikiPageManifest(entries=tuple(entries))


def select_repo_page_manifest(
    manifest: RepoWikiPageManifest,
    *,
    requested_titles: set[str] | None = None,
    include_templates: bool = False,
    include_generated_data: bool = False,
    include_content_pages: bool = False,
    known_live_titles: set[str] | None = None,
) -> RepoWikiPageManifest:
    """Filter a manifest while enforcing each deployment safety gate."""
    requested_template_titles = {title for title in requested_titles or () if _is_template_title(title)}
    requested_generated_titles = {
        entry.title
        for entry in manifest.entries
        if entry.upload_stage == "generated_data" and requested_titles is not None and entry.title in requested_titles
    } | {title for title in requested_titles or () if _is_generated_data_title(title)}
    requested_content_titles = {
        entry.title
        for entry in manifest.entries
        if entry.upload_stage == "content_page" and requested_titles is not None and entry.title in requested_titles
    }
    if requested_template_titles and not include_templates:
        titles = ", ".join(sorted(requested_template_titles))
        raise ValueError(f"Template pages require --include-templates: {titles}")
    if requested_generated_titles and not include_generated_data:
        titles = ", ".join(sorted(requested_generated_titles))
        raise ValueError(f"Generated data pages require explicit deployment opt-in: {titles}")
    if requested_content_titles and not include_content_pages:
        titles = ", ".join(sorted(requested_content_titles))
        raise ValueError(f"Content pages require explicit deployment opt-in: {titles}")

    selected_entries = tuple(
        entry
        for entry in manifest.entries
        if (include_templates or entry.upload_stage not in {"template", "cargo_declaration"})
        and (include_generated_data or entry.upload_stage != "generated_data")
        and (include_content_pages or entry.upload_stage != "content_page")
    )
    if requested_titles is not None:
        selected_entries = tuple(entry for entry in selected_entries if entry.title in requested_titles)
    selected_manifest = RepoWikiPageManifest(entries=selected_entries)
    validate_repo_page_manifest_for_deploy(
        selected_manifest,
        include_templates=include_templates,
        include_generated_data=include_generated_data,
        include_content_pages=include_content_pages,
        known_live_titles=known_live_titles,
    )
    return selected_manifest


def validate_repo_page_manifest_for_deploy(
    manifest: RepoWikiPageManifest,
    *,
    include_templates: bool = False,
    include_generated_data: bool = False,
    include_content_pages: bool = False,
    known_live_titles: set[str] | None = None,
) -> None:
    """Reject entries that were not explicitly enabled for deployment.

    Resolver modules consume ``Data/Links``. The dependency check is pure: a
    caller either includes that generated module earlier in this manifest or
    passes its exact title in ``known_live_titles`` after an independent live
    check. No network access is performed here.
    """
    if not include_templates:
        template_titles = [
            entry.title for entry in manifest.entries if entry.upload_stage in {"template", "cargo_declaration"}
        ]
        if template_titles:
            raise ValueError("Template pages require explicit deployment opt-in: " + ", ".join(sorted(template_titles)))
    if not include_generated_data:
        generated_titles = [entry.title for entry in manifest.entries if entry.upload_stage == "generated_data"]
        if generated_titles:
            raise ValueError(
                "Generated data pages require explicit deployment opt-in: " + ", ".join(sorted(generated_titles))
            )
    if not include_content_pages:
        content_titles = [entry.title for entry in manifest.entries if entry.upload_stage == "content_page"]
        if content_titles:
            raise ValueError("Content pages require explicit deployment opt-in: " + ", ".join(sorted(content_titles)))

    validate_repo_page_manifest_dependencies(manifest, known_live_titles=known_live_titles)


def validate_repo_page_manifest_dependencies(
    manifest: RepoWikiPageManifest,
    *,
    known_live_titles: set[str] | None = None,
) -> None:
    """Require direct consumers to have an earlier or known-live Links catalog."""
    known_live = set(known_live_titles or ())
    data_links_title = "Module:Erenshor/Data/Links"
    earlier_titles: set[str] = set()
    for entry in manifest.entries:
        if entry.title in _DIRECT_DATA_LINK_CONSUMER_TITLES and data_links_title not in earlier_titles | known_live:
            raise ValueError(
                f"{entry.title} requires {data_links_title} earlier in the manifest or explicitly known live"
            )
        earlier_titles.add(entry.title)


def _is_generated_data_title(title: str) -> bool:
    namespace, separator, rest = title.strip().partition(":")
    return bool(separator) and namespace.casefold() == "module" and rest.casefold().startswith("erenshor/data/")


def _is_template_title(title: str) -> bool:
    namespace, separator, _ = title.strip().partition(":")
    return bool(separator) and namespace.casefold() == "template"


def write_repo_page_manifest(manifest: RepoWikiPageManifest, path: Path) -> None:
    """Atomically write a repo-owned wiki page manifest as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": [asdict(entry) for entry in manifest.entries]}
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_path.replace(path)


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
    if value not in ("Scribunto", "wikitext"):
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


def _module_entries(
    root: Path,
    source_root: Path,
    stage: Literal["generated_data", "lua_module"],
    requested_titles: set[str] | None = None,
) -> list[RepoWikiPageManifestEntry]:
    if not source_root.exists():
        return []

    entries: list[RepoWikiPageManifestEntry] = []
    for path in source_root.rglob("*.lua"):
        if not path.is_file():
            continue
        if path.name == "testcases.lua":
            # Scribunto testcases run against the local harness only; they
            # are never deployed to the production wiki.
            continue
        relative_module = path.relative_to(source_root).with_suffix("")
        title = "Module:" + "/".join(relative_module.parts)
        if requested_titles is not None and title not in requested_titles:
            continue
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


def _content_entries(
    root: Path,
    source_root: Path,
    requested_titles: set[str] | None = None,
) -> list[RepoWikiPageManifestEntry]:
    if not source_root.exists():
        return []

    entries: list[RepoWikiPageManifestEntry] = []
    for path in source_root.rglob("*.wiki"):
        if not path.is_file():
            continue
        relative_page = path.relative_to(source_root).with_suffix("")
        if len(relative_page.parts) < 2:
            if requested_titles is not None:
                continue
            raise ValueError(
                "Content page source must be wiki/content/<Namespace>/<Title>.wiki: "
                + path.relative_to(root).as_posix()
            )
        namespace, *title_parts = relative_page.parts
        title = namespace + ":" + "/".join(title_parts)
        if requested_titles is not None and title not in requested_titles:
            continue
        entries.append(
            _entry(
                root=root,
                path=path,
                title=title,
                content_model="wikitext",
                ownership_class="content_page",
                upload_stage="content_page",
                declares_cargo_table=False,
                cargo_tables=(),
            )
        )
    return entries


def _template_entries(
    root: Path,
    source_root: Path,
    requested_titles: set[str] | None = None,
) -> list[RepoWikiPageManifestEntry]:
    if not source_root.exists():
        return []

    entries: list[RepoWikiPageManifestEntry] = []
    for path in source_root.rglob("*.wiki"):
        if not path.is_file():
            continue
        relative_template = path.relative_to(source_root).with_suffix("")
        title = "Template:" + "/".join(relative_template.parts)
        if requested_titles is not None and title not in requested_titles:
            continue
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
