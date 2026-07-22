"""Deterministic semantic-link auditing for generated and live wiki content.

The audit deliberately operates on plain mappings.  Callers that use
:class:`~erenshor.application.wiki.services.storage.WikiStorage` can load the
small ``generated`` mapping at the integration boundary, while this module
remains straightforward to use from generation, deployment, and tests.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal

from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
from erenshor.infrastructure.wiki.template_parser import TemplateParser

if TYPE_CHECKING:
    from erenshor.infrastructure.wiki.client import MediaWikiTitleStatus


Origin = Literal["generated_output", "live_wiki"]
Severity = Literal["error", "warning"]

SUPPORTED_TEMPLATES: Mapping[str, str] = MappingProxyType(
    {
        "ItemLink": "item",
        "AbilityLink": "ability",
        "CharacterLink": "character",
        "QuestLink": "quest",
        "ZoneLink": "zone",
        "FactionLink": "faction",
        "ClassLink": "class",
    }
)

ERROR_CODES = frozenset(
    {
        "missing_stable_key_data",
        "stable_key_target_mismatch",
        "missing_generated_target_article",
    }
)
WARNING_CODES = frozenset(
    {
        "ambiguous_manual_semantic_link",
        "manual_red_link",
        "stale_manual_redirect",
        "live_link_catalog_stale",
        "runtime_tracking_category",
    }
)
FINDING_CODES = ERROR_CODES | WARNING_CODES

_PREFIXES: Mapping[str, tuple[str, ...]] = {
    "item": ("item:",),
    "ability": ("spell:", "skill:", "stance:"),
    "character": ("character:",),
    "quest": ("quest:",),
    "zone": ("zone:",),
    "faction": ("faction:",),
    "class": ("class:",),
}


@dataclass(frozen=True, slots=True)
class LinkOccurrence:
    """One semantic template invocation found in source wikitext."""

    source_page: str
    template: str
    kind: str
    stable_key: str | None
    supplied_target: str | None
    canonical_target: str | None
    origin: Origin


@dataclass(frozen=True, slots=True)
class LinkAuditFinding:
    """One deterministic audit finding."""

    code: str
    severity: Severity
    source_page: str
    kind: str | None
    stable_key: str | None
    supplied_target: str | None
    canonical_target: str | None
    message: str


@dataclass(frozen=True, slots=True)
class LinkAuditReport:
    """Audit result and the occurrences used to produce it.

    ``occurrences`` is intentionally omitted from :meth:`to_dict`: the report
    format is a compact deployment artifact whose exact top-level fields are
    defined by the semantic-link plan.
    """

    variant: str
    remote_checked: bool
    generated_content_sha256: str
    findings: tuple[LinkAuditFinding, ...]
    occurrences: tuple[LinkOccurrence, ...] = ()

    @property
    def has_errors(self) -> bool:
        """Return whether generation/deployment must be blocked."""
        return any(finding.severity == "error" for finding in self.findings)

    @property
    def summary(self) -> Mapping[str, int]:
        """Return counts by finding code in deterministic key order."""
        counts: dict[str, int] = defaultdict(int)
        for finding in self.findings:
            counts[finding.code] += 1
        return MappingProxyType(dict(sorted(counts.items())))

    def to_dict(self) -> dict[str, object]:
        """Return the exact JSON-serializable report shape."""
        return {
            "schema_version": 1,
            "variant": self.variant,
            "remote_checked": self.remote_checked,
            "generated_content_sha256": self.generated_content_sha256,
            "summary": dict(self.summary),
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity,
                    "source_page": finding.source_page,
                    "kind": finding.kind,
                    "stable_key": finding.stable_key,
                    "supplied_target": finding.supplied_target,
                    "canonical_target": finding.canonical_target,
                    "message": finding.message,
                }
                for finding in self.findings
            ],
        }

    def write_json(self, path: Path) -> None:
        """Write the deterministic report JSON without mutating wiki content."""
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )


def write_audit_report(report: LinkAuditReport, path: Path) -> None:
    """Write ``report`` to ``path`` (a convenience for CLI integrations)."""
    report.write_json(path)


def generated_content_sha256(generated_pages: Mapping[str, str]) -> str:
    """Hash generated page titles and exact content in deterministic order.

    Titles are part of the payload so swapping content between pages cannot
    accidentally retain the same report hash.  JSON separators and UTF-8
    encoding are fixed to make the value stable across platforms and mapping
    insertion orders.
    """
    pairs = sorted(
        ((str(title), content) for title, content in generated_pages.items()),
        key=lambda pair: (pair[0].casefold(), pair[0]),
    )
    payload = json.dumps(pairs, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# A short alias reads naturally in integrations while retaining the explicit
# public function above for callers that want to name the hash operation.
hash_generated_content = generated_content_sha256


@dataclass(frozen=True, slots=True)
class _CatalogIndex:
    entries_by_key: Mapping[str, LinkCatalogEntry]
    entries_by_page: Mapping[str, tuple[LinkCatalogEntry, ...]]
    entries_by_name: Mapping[str, tuple[LinkCatalogEntry, ...]]


def _nonblank(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Blank link catalog {field}: {value!r}")
    return value.strip()


def _catalog_entry(value: LinkCatalogEntry | Mapping[str, object]) -> LinkCatalogEntry:
    if isinstance(value, LinkCatalogEntry):
        # Reconstructing also validates test doubles and malformed objects that
        # bypass the dataclass type annotation at runtime.
        return LinkCatalogEntry(
            key=_nonblank(value.key, "key"),
            kind=_nonblank(value.kind, "kind"),
            subtype=value.subtype,
            name=_nonblank(value.name, "name"),
            page=_nonblank(value.page, "page"),
            image=value.image,
        )
    if not isinstance(value, Mapping):
        raise ValueError(f"Invalid link catalog entry: {value!r}")
    required = ("key", "kind", "subtype", "name", "page", "image")
    missing = [field for field in required if field not in value]
    if missing:
        raise ValueError(f"Missing link catalog fields: {', '.join(missing)}")
    image = value["image"]
    if image is not None and not isinstance(image, str):
        raise ValueError(f"Invalid link catalog image: {image!r}")
    subtype = value["subtype"]
    if subtype is not None and not isinstance(subtype, str):
        raise ValueError(f"Invalid link catalog subtype: {subtype!r}")
    return LinkCatalogEntry(
        key=_nonblank(value["key"], "key"),
        kind=_nonblank(value["kind"], "kind"),
        subtype=subtype,
        name=_nonblank(value["name"], "name"),
        page=_nonblank(value["page"], "page"),
        image=image,
    )


def _title_key(value: str) -> str:
    """Normalize enough MediaWiki title syntax for local catalog indexes."""
    return re.sub(r"\s+", " ", value.replace("_", " ").strip()).casefold()


def _name_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _build_catalog_index(entries: Sequence[LinkCatalogEntry | Mapping[str, object]]) -> _CatalogIndex:
    by_key: dict[str, LinkCatalogEntry] = {}
    by_page: dict[str, list[LinkCatalogEntry]] = defaultdict(list)
    by_name: dict[str, list[LinkCatalogEntry]] = defaultdict(list)
    for raw_entry in entries:
        entry = _catalog_entry(raw_entry)
        if entry.kind not in _PREFIXES:
            raise ValueError(f"Unsupported link catalog kind: {entry.kind!r}")
        if entry.subtype is not None and not entry.subtype.strip():
            raise ValueError(f"Blank link catalog subtype for {entry.key!r}")
        if not any(entry.key.startswith(prefix) for prefix in _PREFIXES[entry.kind]):
            raise ValueError(f"Link catalog key {entry.key!r} has wrong prefix for kind {entry.kind!r}")
        if entry.key in by_key:
            raise ValueError(f"Duplicate link catalog key: {entry.key}")
        by_key[entry.key] = entry
        by_page[_title_key(entry.page)].append(entry)
        by_name[_name_key(entry.name)].append(entry)
    return _CatalogIndex(
        entries_by_key=MappingProxyType(dict(sorted(by_key.items()))),
        entries_by_page=MappingProxyType(
            {key: tuple(sorted(value, key=_entry_key)) for key, value in sorted(by_page.items())}
        ),
        entries_by_name=MappingProxyType(
            {key: tuple(sorted(value, key=_entry_key)) for key, value in sorted(by_name.items())}
        ),
    )


def _entry_key(entry: LinkCatalogEntry) -> tuple[str, str, str, str]:
    return (entry.name.casefold(), entry.kind, entry.subtype or "", entry.key)


def catalog_sha256(entries: Sequence[LinkCatalogEntry | Mapping[str, object]]) -> str:
    """Return the digest used by generated ``Module:Erenshor/Data/Links``."""
    index = _build_catalog_index(entries)
    ordered = sorted(index.entries_by_key.values(), key=_entry_key)
    payload = json.dumps(
        [entry.primitive() for entry in ordered],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# The plan names the local side explicitly when comparing the live digest.
local_catalog_sha256 = catalog_sha256


def _parameter_values(template: Any) -> tuple[dict[str, str], list[str]]:
    named: dict[str, str] = {}
    positional: list[str] = []
    for parameter in template.params:
        name = str(parameter.name).strip()
        value = str(parameter.value).strip()
        if getattr(parameter, "showkey", False):
            named[name.casefold()] = value
        else:
            positional.append(value)
    return named, positional


def _target_from_values(named: Mapping[str, str], positional: Sequence[str]) -> str | None:
    value = named.get("link")
    if value is None:
        value = named.get("page")
    if value is None and positional:
        value = positional[0]
    if value is None:
        return None
    # QuestLink's public compatibility syntax uses {{!}} inside |link=page|text.
    value = value.split("{{!}}", 1)[0].strip()
    if "|" in value and not value.startswith("[["):
        value = value.split("|", 1)[0].strip()
    return value or None


def _stable_key_from_values(named: Mapping[str, str]) -> str | None:
    for parameter in ("stablekey", "stable_key", "key", "id"):
        value = named.get(parameter)
        if value is not None:
            return value.strip() or None
    return None


def _manual_candidates(index: _CatalogIndex, kind: str, target: str) -> tuple[LinkCatalogEntry, ...]:
    candidates = [*index.entries_by_page.get(_title_key(target), ()), *index.entries_by_name.get(_name_key(target), ())]
    unique = {entry.key: entry for entry in candidates if entry.kind == kind}
    return tuple(sorted(unique.values(), key=_entry_key))


def _occurrence_from_template(
    source_page: str,
    template_name: str,
    kind: str,
    template: Any,
    index: _CatalogIndex,
    origin: Origin,
) -> tuple[LinkOccurrence | None, LinkAuditFinding | None]:
    named, positional = _parameter_values(template)
    supplied_target = _target_from_values(named, positional)
    stable_key = _stable_key_from_values(named)
    # A rendered page_title=None link is plain text and has no template. An
    # empty compatibility invocation is equivalent and is excluded here.
    # Stable-key-only invocations are valid and resolve their target from the
    # catalog, so they must remain auditable without an explicit fallback.
    if stable_key is None and supplied_target is None:
        return None, None
    if stable_key is not None:
        entry = index.entries_by_key.get(stable_key)
        if entry is None or entry.kind != kind:
            occurrence = LinkOccurrence(source_page, template_name, kind, stable_key, supplied_target, None, origin)
            finding = LinkAuditFinding(
                "missing_stable_key_data",
                "error",
                source_page,
                kind,
                stable_key,
                supplied_target,
                None,
                f"{template_name} stable key {stable_key!r} is absent or has kind {kind!r} in the link catalog",
            )
            return occurrence, finding
        occurrence = LinkOccurrence(
            source_page,
            template_name,
            kind,
            stable_key,
            supplied_target,
            entry.page,
            origin,
        )
        if supplied_target is not None and _title_key(supplied_target) != _title_key(entry.page):
            return occurrence, LinkAuditFinding(
                "stable_key_target_mismatch",
                "error",
                source_page,
                kind,
                stable_key,
                supplied_target,
                entry.page,
                (
                    f"{template_name} key {stable_key!r} resolves to {entry.page!r}, "
                    f"not supplied target {supplied_target!r}"
                ),
            )
        return occurrence, None

    assert supplied_target is not None
    candidates = _manual_candidates(index, kind, supplied_target)
    if len(candidates) == 1:
        canonical_target: str | None = candidates[0].page
    elif len(candidates) > 1:
        canonical_target = None
    else:
        canonical_target = supplied_target
    occurrence = LinkOccurrence(
        source_page,
        template_name,
        kind,
        None,
        supplied_target,
        canonical_target,
        origin,
    )
    if len(candidates) > 1:
        return occurrence, LinkAuditFinding(
            "ambiguous_manual_semantic_link",
            "warning",
            source_page,
            kind,
            None,
            supplied_target,
            None,
            f"{template_name} target {supplied_target!r} matches multiple {kind} catalog records",
        )
    return occurrence, None


def parse_link_occurrences(
    source_page: str,
    wikitext: str,
    catalog_entries: Sequence[LinkCatalogEntry | Mapping[str, object]],
    *,
    origin: Origin = "generated_output",
) -> tuple[LinkOccurrence, ...]:
    """Parse semantic templates without changing the source wikitext."""
    index = _build_catalog_index(catalog_entries)
    parser = TemplateParser()
    code = parser.parse(wikitext)
    occurrences: list[LinkOccurrence] = []
    for template in code.filter_templates():
        template_name = str(template.name).strip()
        kind = next(
            (
                mapped_kind
                for known_name, mapped_kind in SUPPORTED_TEMPLATES.items()
                if known_name.casefold() == template_name.casefold()
            ),
            None,
        )
        if kind is None:
            continue
        occurrence, _ = _occurrence_from_template(source_page, template_name, kind, template, index, origin)
        if occurrence is not None:
            occurrences.append(occurrence)
    return tuple(occurrences)


def _status_for(
    title_statuses: Mapping[str, MediaWikiTitleStatus] | None,
    title: str,
) -> MediaWikiTitleStatus | None:
    if title_statuses is None:
        return None
    status = title_statuses.get(title)
    if status is not None:
        return status
    normalized = _title_key(title)
    for candidate in title_statuses.values():
        requested = getattr(candidate, "requested", "")
        candidate_normalized = getattr(candidate, "normalized", "")
        if _title_key(requested) == normalized or _title_key(candidate_normalized) == normalized:
            return candidate
    return None


def _status_exists(status: MediaWikiTitleStatus | None) -> bool:
    if status is None:
        return False
    return bool(getattr(status, "exists", False) or getattr(status, "redirect_target", None))


def _planned(planned_title_keys: Collection[str], target: str) -> bool:
    return _title_key(target) in planned_title_keys


def _finding_sort_key(finding: LinkAuditFinding) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        finding.source_page.casefold(),
        finding.source_page,
        finding.kind or "",
        finding.stable_key or "",
        finding.supplied_target or "",
        finding.canonical_target or "",
        finding.code,
        finding.message,
    )


def _occurrence_sort_key(occurrence: LinkOccurrence) -> tuple[str, str, str, str, str, str, str]:
    return (
        occurrence.source_page.casefold(),
        occurrence.source_page,
        occurrence.template,
        occurrence.kind,
        occurrence.stable_key or "",
        occurrence.supplied_target or "",
        occurrence.canonical_target or "",
    )


def audit_links(
    *,
    generated_pages: Mapping[str, str],
    catalog_entries: Sequence[LinkCatalogEntry | Mapping[str, object]],
    planned_titles: Collection[str],
    known_generated_titles: Collection[str] | None = None,
    title_statuses: Mapping[str, MediaWikiTitleStatus] | None = None,
    live_pages: Mapping[str, str] | None = None,
    live_catalog_sha256: str | None = None,
    wanted_pages: Iterable[str] = (),
    linking_pages: Mapping[str, Iterable[str]] | None = None,
    runtime_tracking_categories: Mapping[str, Iterable[str]] | None = None,
    variant: str = "",
    remote_checked: bool | None = None,
) -> LinkAuditReport:
    """Audit generated pages and optional post-deploy observations.

    ``generated_pages`` and ``planned_titles`` are the effective page scope
    after page filters and limits have been applied. ``known_generated_titles``
    is the complete local generated-article universe used to detect targets
    excluded from an offline plan. Targets outside that universe require online
    title status and remain unknown offline. No storage or Lua file is consulted
    here, so this function is safe to call before any login/edit.
    """
    index = _build_catalog_index(catalog_entries)
    # Validate all page inputs before parsing, making malformed catalog/scope
    # data fail fast instead of returning a partial report.
    normalized_pages: dict[str, str] = {}
    for page, content in generated_pages.items():
        page_title = _nonblank(page, "generated page title")
        if not isinstance(content, str):
            raise ValueError(f"Generated page content for {page_title!r} is not text")
        normalized_pages[page_title] = content
    planned_title_keys = {_title_key(_nonblank(title, "planned article title")) for title in planned_titles}
    known_generated_title_keys = {
        _title_key(_nonblank(title, "known generated article title")) for title in (known_generated_titles or ())
    }
    wanted = tuple(
        sorted({_nonblank(title, "wanted page title") for title in wanted_pages}, key=lambda x: (x.casefold(), x))
    )
    linking_source_sets: dict[str, set[str]] = defaultdict(set)
    if linking_pages:
        for target, sources in linking_pages.items():
            target_title = _nonblank(target, "linking-page target")
            linking_source_sets[_title_key(target_title)].update(
                _nonblank(source, "linking-page source") for source in sources
            )
    normalized_linking = {
        target: tuple(sorted(sources, key=lambda value: (value.casefold(), value)))
        for target, sources in linking_source_sets.items()
    }
    # Validate live pages at the same boundary as generated pages.
    normalized_live: dict[str, str] = {}
    for page, content in (live_pages or {}).items():
        page_title = _nonblank(page, "live page title")
        if not isinstance(content, str):
            raise ValueError(f"Live page content for {page_title!r} is not text")
        normalized_live[page_title] = content
    occurrences: list[LinkOccurrence] = []
    findings: list[LinkAuditFinding] = []

    def process_pages(pages: Mapping[str, str], origin: Origin) -> None:
        for source_page, content in sorted(pages.items(), key=lambda pair: (pair[0].casefold(), pair[0])):
            parser = TemplateParser()
            code = parser.parse(content)
            for template in code.filter_templates():
                template_name = str(template.name).strip()
                kind = next(
                    (
                        mapped
                        for known, mapped in SUPPORTED_TEMPLATES.items()
                        if known.casefold() == template_name.casefold()
                    ),
                    None,
                )
                if kind is None:
                    continue
                occurrence, local_finding = _occurrence_from_template(
                    source_page, template_name, kind, template, index, origin
                )
                if occurrence is None:
                    continue
                occurrences.append(occurrence)
                if local_finding is not None:
                    findings.append(local_finding)

                if occurrence.stable_key is not None:
                    if occurrence.canonical_target is None:
                        continue
                    status = _status_for(title_statuses, occurrence.canonical_target)
                    missing_target = not (
                        _planned(planned_title_keys, occurrence.canonical_target) or _status_exists(status)
                    )
                    target_must_be_known = title_statuses is not None or _planned(
                        known_generated_title_keys,
                        occurrence.canonical_target,
                    )
                    if origin == "generated_output" and missing_target and target_must_be_known:
                        findings.append(
                            LinkAuditFinding(
                                "missing_generated_target_article",
                                "error",
                                source_page,
                                occurrence.kind,
                                occurrence.stable_key,
                                occurrence.supplied_target,
                                occurrence.canonical_target,
                                (
                                    f"Generated semantic link target {occurrence.canonical_target!r} "
                                    "is neither live nor planned for this deployment"
                                ),
                            )
                        )
                    continue

                # Manual compatibility links are never promoted to errors.  A
                # known missing target remains a native MediaWiki red link.
                effective_target = occurrence.canonical_target or occurrence.supplied_target or ""
                status = _status_for(title_statuses, effective_target)
                redirect_target = getattr(status, "redirect_target", None) if status is not None else None
                if redirect_target:
                    canonical = occurrence.canonical_target
                    if canonical is None or _title_key(canonical) != _title_key(redirect_target):
                        findings.append(
                            LinkAuditFinding(
                                "stale_manual_redirect",
                                "warning",
                                source_page,
                                occurrence.kind,
                                None,
                                occurrence.supplied_target,
                                occurrence.canonical_target,
                                (
                                    f"Manual {occurrence.kind} link target {occurrence.supplied_target!r} "
                                    f"redirects to {redirect_target!r} instead of its catalog target"
                                ),
                            )
                        )
                elif status is not None and not _status_exists(status):
                    findings.append(
                        LinkAuditFinding(
                            "manual_red_link",
                            "warning",
                            source_page,
                            occurrence.kind,
                            None,
                            occurrence.supplied_target,
                            occurrence.canonical_target,
                            f"Manual {occurrence.kind} link target {effective_target!r} does not exist",
                        )
                    )

    process_pages(normalized_pages, "generated_output")
    if normalized_live:
        process_pages(normalized_live, "live_wiki")

    # WantedPages is a remote, reparsing-lagging warning source. Linking-page
    # facts identify the source pages when MediaWiki exposes them. Retain the
    # wanted title itself as the deterministic location only when no linker is
    # available.
    for title in wanted:
        sources = normalized_linking.get(_title_key(title), ()) or (title,)
        for source_page in sources:
            findings.append(
                LinkAuditFinding(
                    "manual_red_link",
                    "warning",
                    source_page,
                    None,
                    None,
                    title,
                    title,
                    f"MediaWiki reports wanted page {title!r}",
                )
            )

    if runtime_tracking_categories:
        for category, members in sorted(
            runtime_tracking_categories.items(), key=lambda pair: (pair[0].casefold(), pair[0])
        ):
            category_title = _nonblank(category, "runtime tracking category")
            for member in sorted(
                {_nonblank(member, "runtime tracking category member") for member in members},
                key=lambda x: (x.casefold(), x),
            ):
                findings.append(
                    LinkAuditFinding(
                        "runtime_tracking_category",
                        "warning",
                        member,
                        None,
                        None,
                        category_title,
                        category_title,
                        f"Live page {member!r} is in runtime tracking category {category_title!r}",
                    )
                )

    inferred_remote = (
        title_statuses is not None
        or live_pages is not None
        or live_catalog_sha256 is not None
        or bool(wanted)
        or bool(normalized_linking)
        or bool(runtime_tracking_categories)
    )
    report = LinkAuditReport(
        variant=variant,
        remote_checked=inferred_remote if remote_checked is None else remote_checked,
        generated_content_sha256=generated_content_sha256(normalized_pages),
        findings=tuple(sorted(findings, key=_finding_sort_key)),
        occurrences=tuple(sorted(occurrences, key=_occurrence_sort_key)),
    )
    # Catalog stale is a remote fact and therefore cannot be raised by an
    # offline call that did not provide a live digest.
    if live_catalog_sha256 is not None or remote_checked is True:
        stale = live_catalog_sha256 != catalog_sha256(tuple(index.entries_by_key.values()))
        if stale:
            stale_finding = LinkAuditFinding(
                "live_link_catalog_stale",
                "warning",
                "Module:Erenshor/Data/Links",
                None,
                None,
                None,
                None,
                "Live semantic-link catalog is absent or differs from the generated catalog digest",
            )
            report = LinkAuditReport(
                variant=report.variant,
                remote_checked=report.remote_checked,
                generated_content_sha256=report.generated_content_sha256,
                findings=tuple(sorted((*report.findings, stale_finding), key=_finding_sort_key)),
                occurrences=report.occurrences,
            )
    return report


__all__ = [
    "ERROR_CODES",
    "FINDING_CODES",
    "SUPPORTED_TEMPLATES",
    "WARNING_CODES",
    "LinkAuditFinding",
    "LinkAuditReport",
    "LinkOccurrence",
    "audit_links",
    "catalog_sha256",
    "generated_content_sha256",
    "hash_generated_content",
    "local_catalog_sha256",
    "parse_link_occurrences",
    "write_audit_report",
]
