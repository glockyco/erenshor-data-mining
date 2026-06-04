"""Article override migration pass for the Lua/Cargo cutover.

For a single article, this parses the infobox invocation, asks a resolver for
the generated (Lua) value of each non-identity parameter, classifies each
against that value, and removes the parameters that merely duplicate generated
data. What remains is the minimal set of genuine overrides plus the identity
selector, so future data exports flow through untouched fields while real
human edits are preserved.

The generated-value resolver is a protocol so the pass is testable without a
live wiki; the live implementation resolves values through the deployed
presentation module (the single source of truth for what a field generates).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from erenshor.application.wiki_deploy.override_classifier import (
    ArticleOverrideClassification,
    classify_article_overrides,
)
from erenshor.infrastructure.wiki.template_parser import TemplateParser

# Selectors the presentation modules use to resolve an entity; never overrides.
DEFAULT_IDENTITY_PARAMS = ("stablekey", "stableKey", "key", "id")


class GeneratedValueResolver(Protocol):
    """Resolves the generated value of each field for an entity.

    ``identity_args`` are the article's identity selectors (e.g. ``stablekey``)
    that the presentation module uses to find the entity; the resolver invokes
    that module with only those args so each returned value is the generated
    default, with no override applied.
    """

    def resolve(self, identity_args: Mapping[str, str], fields: Sequence[str]) -> dict[str, str]: ...


@dataclass(frozen=True, slots=True)
class ArticleMigration:
    """The minimized article plus the evidence behind every decision."""

    title: str
    minimized_wikitext: str
    classification: ArticleOverrideClassification
    removed_fields: tuple[str, ...]
    preserved_fields: tuple[str, ...]


def migrate_article_overrides(
    *,
    title: str,
    wikitext: str,
    template_names: Sequence[str],
    resolver: GeneratedValueResolver,
    identity_params: Sequence[str] = DEFAULT_IDENTITY_PARAMS,
    parser: TemplateParser | None = None,
) -> ArticleMigration:
    """Remove infobox parameters that duplicate generated data, keeping real overrides."""
    parser = parser or TemplateParser()
    code = parser.parse(wikitext)
    template = parser.find_template(code, template_names)
    params = parser.get_params(template)

    identity = set(identity_params)
    identity_args = {name: value for name, value in params.items() if name in identity}
    candidate = {name: value for name, value in params.items() if name not in identity}

    generated_values = resolver.resolve(identity_args, tuple(candidate))
    classification = classify_article_overrides(
        title=title,
        article_params=candidate,
        generated_values=generated_values,
    )

    removed_fields = tuple(
        decision.field for decision in classification.decisions if decision.decision == "removed_generated_duplicate"
    )
    preserved_fields = tuple(
        decision.field for decision in classification.decisions if decision.decision != "removed_generated_duplicate"
    )

    for field in removed_fields:
        parser.remove_param(template, field)

    return ArticleMigration(
        title=title,
        minimized_wikitext=parser.render(code),
        classification=classification,
        removed_fields=removed_fields,
        preserved_fields=preserved_fields,
    )


# A Scribunto error means the module cannot read that field; it is not a value.
_SCRIBUNTO_ERROR = re.compile(r'scribunto-error|class="error"')


class TemplateExpansionClient(Protocol):
    """Minimal client surface needed to resolve generated values."""

    def expand_templates(self, text: str) -> str: ...


class ArticleReviewClient(TemplateExpansionClient, Protocol):
    """Client surface needed to fetch articles and resolve generated values."""

    def get_page(self, title: str) -> str | None: ...


class MissingArticleError(RuntimeError):
    """Raised when a requested article page does not exist."""


@dataclass(frozen=True, slots=True)
class ArticleOverrideReview:
    """Original and minimized article text for review-only cleanup."""

    title: str
    original_wikitext: str
    migration: ArticleMigration

    @property
    def changed(self) -> bool:
        return self.original_wikitext != self.migration.minimized_wikitext


def review_article_overrides(
    *,
    client: ArticleReviewClient,
    titles: Sequence[str],
    template_names: Sequence[str],
    module: str,
    identity_params: Sequence[str] = DEFAULT_IDENTITY_PARAMS,
    parser: TemplateParser | None = None,
) -> tuple[ArticleOverrideReview, ...]:
    """Fetch article pages and produce review-only override minimization results."""
    resolver = LiveGeneratedValueResolver(client=client, module=module)
    reviews: list[ArticleOverrideReview] = []
    for title in titles:
        wikitext = client.get_page(title)
        if wikitext is None:
            raise MissingArticleError(f"Article page does not exist: {title}")
        migration = migrate_article_overrides(
            title=title,
            wikitext=wikitext,
            template_names=template_names,
            resolver=resolver,
            identity_params=identity_params,
            parser=parser,
        )
        reviews.append(
            ArticleOverrideReview(
                title=title,
                original_wikitext=wikitext,
                migration=migration,
            )
        )
    return tuple(reviews)


@dataclass(frozen=True, slots=True)
class LiveGeneratedValueResolver:
    """Resolves generated values through a deployed presentation module.
    Invokes ``{{#invoke:<module>|field|<identity>|1=<field>}}`` with only the
    identity selectors, so each result is the value the module generates with no
    override applied. Fields the module cannot read (a Scribunto error) are
    omitted, so the migration keeps those parameters rather than dropping them.
    """

    client: TemplateExpansionClient
    module: str

    def resolve(self, identity_args: Mapping[str, str], fields: Sequence[str]) -> dict[str, str]:
        identity = "".join(f"|{name}={value}" for name, value in identity_args.items())
        resolved: dict[str, str] = {}
        for field in fields:
            text = "{{#invoke:" + self.module + "|field" + identity + "|1=" + field + "}}"
            value = self.client.expand_templates(text)
            if _SCRIBUNTO_ERROR.search(value):
                continue
            resolved[field] = value
        return resolved
