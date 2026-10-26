"""Repo-owned wiki page deployment manifest."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlsplit

ContentModel = Literal["Scribunto", "sanitized-css", "wikitext"]
UploadStage = Literal["stylesheet", "generated_data", "lua_module", "template", "content_page", "article"]
DeployAction = Literal["unchanged", "created", "edited"]
PendingOperation = Literal["deploy", "rollback"]

_CONTENT_MODELS: tuple[ContentModel, ...] = ("Scribunto", "sanitized-css", "wikitext")

# Stylesheets go first because Lua modules as well as templates load them.
# Other pages load earlier stages or dependencies ordered within their own stage.
UPLOAD_STAGES: tuple[UploadStage, ...] = (
    "stylesheet",
    "generated_data",
    "lua_module",
    "template",
    "content_page",
    "article",
)
# The stages that a deploy includes only with --include-templates.
TEMPLATE_STAGES: frozenset[UploadStage] = frozenset({"stylesheet", "template"})
# The stages whose pages other pages load, so a deploy renders their users first.
RENDER_CHECKED_STAGES: frozenset[UploadStage] = frozenset({"stylesheet", "generated_data", "lua_module", "template"})


def stage_rank(stage: UploadStage) -> int:
    """The position of a stage in the deploy order."""
    return UPLOAD_STAGES.index(stage)


@dataclass(frozen=True, slots=True)
class RepoWikiPageManifestEntry:
    """One repo-owned wiki page eligible for safe deployment."""

    title: str
    source_path: str
    source_sha256: str
    ownership_class: UploadStage
    upload_stage: UploadStage
    content_model: ContentModel
    old_revision_id: int | None = None
    old_revision_timestamp: str | None = None
    new_revision_id: int | None = None
    new_revision_timestamp: str | None = None
    rollback_text_source: str | None = None
    deploy_action: DeployAction | None = None
    pending_mutation: bool = False
    rollback_revision_id: int | None = None
    pending_operation: PendingOperation | None = None
    pending_base_revision_id: int | None = None
    pending_acknowledged_revision_id: int | None = None
    requires_rollback: bool = False
    rollback_content_model: str | None = None


@dataclass(frozen=True, slots=True)
class RepoWikiPageManifest:
    """Deployable content pages; MediaWiki interface pages are forbidden."""

    entries: tuple[RepoWikiPageManifestEntry, ...]
    api_url: str | None = None
    variant: str | None = None
    wiki_root: str | None = None

    def __post_init__(self) -> None:
        # Manifests are durable review artifacts, so endpoint credentials must never enter them.
        if self.api_url is not None:
            endpoint = urlsplit(self.api_url)
            if endpoint.username is not None or endpoint.password is not None:
                raise ValueError("Manifest API URL must not contain credentials")
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

    entries.sort(key=lambda entry: (stage_rank(entry.upload_stage), entry.title))
    return RepoWikiPageManifest(entries=tuple(entries))


def select_repo_page_manifest(
    manifest: RepoWikiPageManifest,
    *,
    requested_titles: set[str] | None = None,
    include_templates: bool = False,
    include_generated_data: bool = False,
    include_content_pages: bool = False,
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
        if (include_templates or entry.upload_stage not in TEMPLATE_STAGES)
        and (include_generated_data or entry.upload_stage != "generated_data")
        and (include_content_pages or entry.upload_stage != "content_page")
    )
    if requested_titles is not None:
        selected_entries = tuple(entry for entry in selected_entries if entry.title in requested_titles)
    selected_manifest = replace(manifest, entries=selected_entries)
    validate_repo_page_manifest_for_deploy(
        selected_manifest,
        include_templates=include_templates,
        include_generated_data=include_generated_data,
        include_content_pages=include_content_pages,
    )
    return selected_manifest


def validate_repo_page_manifest_for_deploy(
    manifest: RepoWikiPageManifest,
    *,
    include_templates: bool = False,
    include_generated_data: bool = False,
    include_content_pages: bool = False,
) -> None:
    """Reject entries that were not explicitly enabled for deployment."""
    if not include_templates:
        template_titles = [entry.title for entry in manifest.entries if entry.upload_stage in TEMPLATE_STAGES]
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


def _is_generated_data_title(title: str) -> bool:
    namespace, separator, rest = title.strip().partition(":")
    return bool(separator) and namespace.casefold() == "module" and rest.casefold().startswith("erenshor/data/")


def _is_template_title(title: str) -> bool:
    namespace, separator, _ = title.strip().partition(":")
    return bool(separator) and namespace.casefold() == "template"


def durable_write_text(path: Path, text: str) -> None:
    """Atomically replace UTF-8 text and persist its bytes and directory entry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
        # Include ancestors because callers may have just created the run directory.
        for directory in (path.absolute().parent, *path.absolute().parent.parents):
            directory_descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_repo_page_manifest(manifest: RepoWikiPageManifest, path: Path) -> None:
    """Durably replace a repo-owned wiki page manifest as deterministic JSON."""
    payload = asdict(manifest)
    durable_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_repo_page_manifest(path: Path) -> RepoWikiPageManifest:
    """Read a repo-owned wiki page manifest written by ``write_repo_page_manifest``."""
    payload = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    raw_entries = cast("list[dict[str, object]]", payload["entries"])
    entries = tuple(_entry_from_payload(raw_entry) for raw_entry in raw_entries)
    return RepoWikiPageManifest(
        entries=entries,
        api_url=_optional_str(payload.get("api_url")),
        variant=_optional_str(payload.get("variant")),
        wiki_root=_optional_str(payload.get("wiki_root")),
    )


def _entry_from_payload(raw_entry: dict[str, object]) -> RepoWikiPageManifestEntry:
    return RepoWikiPageManifestEntry(
        title=str(raw_entry["title"]),
        source_path=str(raw_entry["source_path"]),
        source_sha256=str(raw_entry["source_sha256"]),
        ownership_class=_upload_stage(str(raw_entry["ownership_class"])),
        upload_stage=_upload_stage(str(raw_entry["upload_stage"])),
        content_model=_content_model(str(raw_entry["content_model"])),
        old_revision_id=_optional_int(raw_entry.get("old_revision_id")),
        old_revision_timestamp=_optional_str(raw_entry.get("old_revision_timestamp")),
        new_revision_id=_optional_int(raw_entry.get("new_revision_id")),
        new_revision_timestamp=_optional_str(raw_entry.get("new_revision_timestamp")),
        rollback_text_source=_optional_str(raw_entry.get("rollback_text_source")),
        deploy_action=_optional_deploy_action(raw_entry.get("deploy_action")),
        pending_mutation=_boolean(raw_entry.get("pending_mutation", False), "pending_mutation"),
        rollback_revision_id=_optional_int(raw_entry.get("rollback_revision_id")),
        pending_operation=_optional_pending_operation(raw_entry.get("pending_operation")),
        pending_base_revision_id=_optional_int(raw_entry.get("pending_base_revision_id")),
        pending_acknowledged_revision_id=_optional_int(raw_entry.get("pending_acknowledged_revision_id")),
        requires_rollback=_boolean(raw_entry.get("requires_rollback", False), "requires_rollback"),
        rollback_content_model=_optional_str(raw_entry.get("rollback_content_model")),
    )


def _optional_pending_operation(value: object) -> PendingOperation | None:
    if value is None:
        return None
    if value not in ("deploy", "rollback"):
        raise ValueError("Unknown native pending operation")
    return value


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"Expected bool for {field}")
    return value


def _upload_stage(value: str) -> UploadStage:
    if value not in UPLOAD_STAGES:
        raise ValueError(f"Unknown wiki deploy upload stage: {value}")
    return value


def _content_model(value: str) -> ContentModel:
    if value not in _CONTENT_MODELS:
        raise ValueError(f"Unknown wiki deploy content model: {value}")
    return value


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
            )
        )
    return entries


def _template_entries(
    root: Path,
    source_root: Path,
    requested_titles: set[str] | None = None,
) -> list[RepoWikiPageManifestEntry]:
    """Templates from ``wiki/templates/<Name>.wiki`` and their TemplateStyles
    stylesheets from ``wiki/templates/<Name>/styles.css``, which keep their
    ``.css`` suffix in the title and the ``sanitized-css`` content model."""
    if not source_root.exists():
        return []

    entries: list[RepoWikiPageManifestEntry] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix not in {".wiki", ".css"}:
            continue
        relative = path.relative_to(source_root)
        if path.suffix == ".css":
            title = "Template:" + "/".join(relative.parts)
            if requested_titles is not None and title not in requested_titles:
                continue
            entries.append(
                _entry(
                    root=root,
                    path=path,
                    title=title,
                    content_model="sanitized-css",
                    ownership_class="stylesheet",
                    upload_stage="stylesheet",
                )
            )
            continue
        title = "Template:" + "/".join(relative.with_suffix("").parts)
        if requested_titles is not None and title not in requested_titles:
            continue
        entries.append(
            _entry(
                root=root,
                path=path,
                title=title,
                content_model="wikitext",
                ownership_class="template",
                upload_stage="template",
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
) -> RepoWikiPageManifestEntry:
    source_bytes = path.read_bytes()
    return RepoWikiPageManifestEntry(
        title=title,
        source_path=path.relative_to(root).as_posix(),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        ownership_class=ownership_class,
        upload_stage=upload_stage,
        content_model=content_model,
    )
