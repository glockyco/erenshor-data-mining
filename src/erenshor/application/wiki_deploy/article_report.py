"""Review report of an article deploy plan.

The report groups the planned writes by the kind of change that they make,
so that a reviewer can check tier changes, value changes, and structural
changes before the deploy writes anything. Field values compare with link
syntax ignored: a value whose links reach the same pages through other
syntax is a link change, not a value change. The report also lists the live
roots that generation kept because no generated entity matches them, and the
pages whose live revision is no longer the fetched revision.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from erenshor.application.wiki.generators.field_preservation import ROOT_COMPANIONS, ROOT_NAME_FIELDS
from erenshor.application.wiki_deploy.articles import ArticleIssue, PlannedArticle, live_conflict
from erenshor.infrastructure.wiki.template_parser import TemplateParser

if TYPE_CHECKING:
    from mwparserfromhell.nodes import Template
    from mwparserfromhell.wikicode import Wikicode

    from erenshor.application.wiki.services.storage import WikiStorage
    from erenshor.application.wiki_deploy.articles import ArticleDeployPlan
    from erenshor.application.wiki_deploy.link_audit import LinkTargets

ChangeKind = Literal["new page", "encounter tier", "field values", "links", "stable key", "categories", "structure"]
CHANGE_KINDS: tuple[ChangeKind, ...] = (
    "new page",
    "encounter tier",
    "field values",
    "links",
    "stable key",
    "categories",
    "structure",
)
# Kinds that do not change what a reader sees on the page.
_INVISIBLE_KINDS: frozenset[ChangeKind] = frozenset({"links", "stable key"})

_GENERATED_TEMPLATES = frozenset(ROOT_COMPANIONS).union(*ROOT_COMPANIONS.values())
_PARSER = TemplateParser()

# A generated template on a page: its name, the entity name of a root, and its
# position among the templates with the same name and entity name.
_Identity = tuple[str, str, int]


@dataclass(frozen=True, slots=True)
class TierChange:
    """An encounter tier change of one character root."""

    name: str
    old: str
    new: str


@dataclass(frozen=True, slots=True)
class ArticleChange:
    """The kinds of change that one planned write makes.

    ``fields`` names each ``<template>.<field>`` whose value changes with link
    syntax ignored. ``structure`` describes each added or removed generated
    template and a change of the text outside them. ``kept_roots`` names the
    live roots that generation kept because they match no generated entity.
    """

    title: str
    kinds: frozenset[ChangeKind]
    tier_changes: tuple[TierChange, ...]
    fields: frozenset[str]
    structure: tuple[str, ...]
    kept_roots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArticleDeployReport:
    """The planned writes grouped by kind of change, with the conflicts."""

    changes: tuple[ArticleChange, ...]
    conflicts: tuple[ArticleIssue, ...]
    unchanged: int

    def pages(self, kind: ChangeKind) -> tuple[str, ...]:
        """Return the titles of the planned writes that make a change of ``kind``."""
        return tuple(change.title for change in self.changes if kind in change.kinds)

    def invisible_pages(self) -> tuple[str, ...]:
        """Return the titles of the planned writes that change only links and stable keys."""
        return tuple(change.title for change in self.changes if change.kinds <= _INVISIBLE_KINDS)

    def field_pages(self) -> dict[str, tuple[str, ...]]:
        """Return the pages that change each field value, most changed field first."""
        pages: dict[str, list[str]] = {}
        for change in self.changes:
            for field in change.fields:
                pages.setdefault(field, []).append(change.title)
        return {
            field: tuple(titles) for field, titles in sorted(pages.items(), key=lambda item: (-len(item[1]), item[0]))
        }

    def to_json(self) -> dict[str, Any]:
        """Return the full report as JSON-serializable data."""
        return {
            "unchanged": self.unchanged,
            "kinds": {kind: list(self.pages(kind)) for kind in CHANGE_KINDS},
            "invisible": list(self.invisible_pages()),
            "fields": {field: list(titles) for field, titles in self.field_pages().items()},
            "tier_changes": [
                {"title": change.title, "name": tier.name, "old": tier.old, "new": tier.new}
                for change in self.changes
                for tier in change.tier_changes
            ],
            "structure": {change.title: list(change.structure) for change in self.changes if change.structure},
            "kept_roots": {change.title: list(change.kept_roots) for change in self.changes if change.kept_roots},
            "conflicts": {issue.title: issue.reason for issue in self.conflicts},
        }


def build_article_report(
    plan: ArticleDeployPlan,
    storage: WikiStorage,
    live_revisions: Mapping[str, int | None],
    link_targets: LinkTargets,
) -> ArticleDeployReport:
    """Describe every planned write and check it against its live revision.

    ``live_revisions`` maps each planned title to its current revision, or to
    None when the page does not exist. ``link_targets`` resolves links through
    the link catalog that generation used.
    """
    metadata = storage.get_metadata_by_titles([article.title for article in plan.writes])
    changes: list[ArticleChange] = []
    conflicts: list[ArticleIssue] = []
    for article in plan.writes:
        conflict = live_conflict(article, live_revisions[article.title])
        if conflict is not None:
            conflicts.append(ArticleIssue(article.title, conflict))
        page_metadata = metadata.get(article.title)
        kept_roots = tuple(page_metadata.kept_roots) if page_metadata is not None else ()
        changes.append(describe_change(article, storage.read_fetched_by_title(article.title), kept_roots, link_targets))
    return ArticleDeployReport(changes=tuple(changes), conflicts=tuple(conflicts), unchanged=plan.count("unchanged"))


def describe_change(
    article: PlannedArticle,
    fetched_text: str | None,
    kept_roots: tuple[str, ...],
    link_targets: LinkTargets,
) -> ArticleChange:
    """Return the kinds of change that writing ``article`` over ``fetched_text`` makes.

    Generated templates pair by name, by the entity name of a root, and by
    position among the templates with the same name and entity name.
    """
    if fetched_text is None:
        return ArticleChange(article.title, frozenset({"new page"}), (), frozenset(), (), kept_roots)

    old_code = _PARSER.parse(fetched_text)
    new_code = _PARSER.parse(article.generated_text)
    old_templates = _generated_templates(old_code)
    new_templates = _generated_templates(new_code)
    kinds: set[ChangeKind] = set()
    tier_changes: list[TierChange] = []
    fields: set[str] = set()
    structure = [f"added {_display(identity)}" for identity in new_templates if identity not in old_templates]
    structure.extend(f"removed {_display(identity)}" for identity in old_templates if identity not in new_templates)

    for identity in old_templates.keys() & new_templates.keys():
        name = identity[0]
        old_params, new_params = old_templates[identity], new_templates[identity]
        for field in sorted(old_params.keys() | new_params.keys()):
            old_value, new_value = old_params.get(field, ""), new_params.get(field, "")
            if old_value == new_value:
                continue
            if field == "stablekey":
                kinds.add("stable key")
            elif name == "Character" and field == "type" and _visible(old_value) != _visible(new_value):
                kinds.add("encounter tier")
                tier_changes.append(TierChange(_display_name(identity), _visible(old_value), _visible(new_value)))
            elif _link_insensitive(old_value, link_targets) == _link_insensitive(new_value, link_targets):
                kinds.add("links")
            else:
                kinds.add("field values")
                fields.add(f"{name}.{field}")

    if sorted(_categories(old_code)) != sorted(_categories(new_code)):
        kinds.add("categories")
    if _other_text(old_code) != _other_text(new_code):
        structure.append("changed the text outside the generated templates")
    if not kinds and not structure:
        structure.append("changed only the formatting of the generated templates")
    if structure:
        kinds.add("structure")
    return ArticleChange(
        article.title,
        frozenset(kinds),
        tuple(sorted(tier_changes, key=lambda tier: tier.name)),
        frozenset(fields),
        tuple(structure),
        kept_roots,
    )


def _generated_templates(code: Wikicode) -> dict[_Identity, dict[str, str]]:
    """Return the parameters of each generated template, with whitespace collapsed."""
    templates: dict[_Identity, dict[str, str]] = {}
    ordinals: Counter[tuple[str, str]] = Counter()
    for template in code.filter_templates(recursive=True):
        name = str(template.name).strip()
        if name not in _GENERATED_TEMPLATES:
            continue
        label = _root_label(template, name)
        ordinals[(name, label)] += 1
        templates[(name, label, ordinals[(name, label)])] = {
            str(param.name).strip(): " ".join(str(param.value).split()) for param in template.params
        }
    return templates


def _root_label(template: Template, name: str) -> str:
    field = ROOT_NAME_FIELDS.get(name)
    if field is None or not template.has(field):
        return ""
    return " ".join(str(template.get(field).value).split())


def _display_name(identity: _Identity) -> str:
    """Return the entity name of a root, with its position when the page repeats the name."""
    _, label, ordinal = identity
    text = label or "(unnamed)"
    return text if ordinal == 1 else f"{text} #{ordinal}"


def _display(identity: _Identity) -> str:
    """Return a generated template as ``<template>: <name>``, or its name when it has no entity name."""
    name, label, ordinal = identity
    text = f"{name}: {label}" if label else name
    return text if ordinal == 1 else f"{text} #{ordinal}"


def _visible(value: str) -> str:
    """Return the text that a reader sees for a plain or linked value."""
    return " ".join(_PARSER.parse(value).strip_code().split())


def _link_insensitive(value: str, link_targets: LinkTargets) -> str:
    """Return ``value`` with each link replaced by the page that it links, with whitespace collapsed."""
    parts: list[str] = []
    for node in _PARSER.parse(value).nodes:
        target = link_targets.node_target(node)
        parts.append(str(node) if target is None else f"[[{target}]]")
    return " ".join("".join(parts).split())


def _categories(code: Wikicode) -> list[str]:
    """Return the categories that the page text assigns."""
    categories: list[str] = []
    for link in code.filter_wikilinks(recursive=True):
        title = " ".join(str(link.title).split())
        if title.casefold().startswith("category:"):
            categories.append(title)
    return categories


def _other_text(code: Wikicode) -> str:
    """Return the page text outside generated templates and categories, with whitespace collapsed.

    This removes those nodes from ``code``.
    """
    for template in code.filter_templates(recursive=True):
        if str(template.name).strip() in _GENERATED_TEMPLATES and code.contains(template):
            code.remove(template)
    for link in code.filter_wikilinks(recursive=True):
        if str(link.title).strip().casefold().startswith("category:") and code.contains(link):
            code.remove(link)
    return " ".join(str(code).split())
