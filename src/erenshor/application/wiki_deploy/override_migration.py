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
from dataclasses import dataclass, field
from typing import Protocol

from erenshor.application.wiki_deploy.override_classifier import (
    ArticleOverrideClassification,
    classify_article_overrides,
)
from erenshor.infrastructure.wiki.template_parser import TemplateParser

# Selectors the presentation modules use to resolve an entity; never overrides.
DEFAULT_IDENTITY_PARAMS = ("stablekey", "stableKey", "key", "id")


_DEFAULT_IDENTITY_PARAM = "stablekey"


class GeneratedValueResolver(Protocol):
    """Resolves the generated value of each field for an entity.

    ``identity_args`` are the article's identity selectors (e.g. ``stablekey``)
    that the presentation module uses to find the entity; the resolver invokes
    that module with only those args so each returned value is the generated
    default, with no override applied.
    """

    def resolve(self, identity_args: Mapping[str, str], fields: Sequence[str]) -> dict[str, str]: ...


class ArticleIdentityConflictError(RuntimeError):
    """Raised when article text disagrees with the authoritative page identity."""


class UnsafeOverrideApplyError(RuntimeError):
    """Raised when override apply would freeze known-unemitted generated data."""


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
    authoritative_identity: Mapping[str, str] | None = None,
    apply_guard_fields: Sequence[str] = (),
    parser: TemplateParser | None = None,
) -> ArticleMigration:
    """Remove infobox parameters that duplicate generated data, keeping real overrides."""
    parser = parser or TemplateParser()
    code = parser.parse(wikitext)
    template = parser.find_template(code, template_names)
    params = parser.get_params(template)

    identity = set(identity_params)
    article_identity_args = {name: value for name, value in params.items() if name in identity}
    if authoritative_identity is not None:
        for name, value in authoritative_identity.items():
            article_value = article_identity_args.get(name)
            if article_value is not None and article_value != value:
                raise ArticleIdentityConflictError(
                    f"{title}: article {name}={article_value!r} conflicts with authoritative {name}={value!r}"
                )
            if article_value is None:
                parser.set_param(template, name, value)
        identity_args = dict(authoritative_identity)
    else:
        identity_args = article_identity_args
    candidate = {name: value for name, value in params.items() if name not in identity}

    generated_values = resolver.resolve(identity_args, tuple(candidate))
    classification = classify_article_overrides(
        title=title,
        article_params=candidate,
        generated_values=generated_values,
    )
    _raise_for_unsafe_apply_fields(
        title=title,
        article_params=candidate,
        generated_values=generated_values,
        guarded_fields=apply_guard_fields,
    )

    removed_fields = tuple(
        decision.field for decision in classification.decisions if decision.decision == "removed_generated_duplicate"
    )
    preserved_fields = tuple(
        decision.field for decision in classification.decisions if decision.decision != "removed_generated_duplicate"
    )

    for field_name in removed_fields:
        parser.remove_param(template, field_name)

    return ArticleMigration(
        title=title,
        minimized_wikitext=parser.render(code),
        classification=classification,
        removed_fields=removed_fields,
        preserved_fields=preserved_fields,
    )


def _raise_for_unsafe_apply_fields(
    *,
    title: str,
    article_params: Mapping[str, str],
    generated_values: Mapping[str, str],
    guarded_fields: Sequence[str],
) -> None:
    guarded = set(guarded_fields)
    if not guarded:
        return
    unsafe_fields = tuple(
        field
        for field, article_value in article_params.items()
        if field in guarded and article_value.strip() not in ("", "-") and not generated_values.get(field, "").strip()
    )
    if unsafe_fields:
        fields = ", ".join(unsafe_fields)
        raise UnsafeOverrideApplyError(
            f"{title}: override apply is unsafe because generated values are empty for guarded fields: {fields}"
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
    migration: ArticleMigration | None
    skipped_reason: str | None = None

    @property
    def changed(self) -> bool:
        return self.migration is not None and self.original_wikitext != self.migration.minimized_wikitext


def _authoritative_identity_for_page(
    title: str,
    article_identities: Mapping[str, Sequence[str]] | None,
    identity_param: str,
) -> tuple[dict[str, str] | None, str | None]:
    if article_identities is None:
        return None, None
    stable_keys = tuple(article_identities.get(title, ()))
    if not stable_keys:
        return None, "no stable key mapped to page"
    if len(stable_keys) > 1:
        return None, f"ambiguous identity: {len(stable_keys)} stable keys mapped to page"
    return {identity_param: stable_keys[0]}, None


def review_article_overrides(
    *,
    client: ArticleReviewClient,
    titles: Sequence[str],
    template_names: Sequence[str],
    module: str,
    identity_params: Sequence[str] = DEFAULT_IDENTITY_PARAMS,
    article_identities: Mapping[str, Sequence[str]] | None = None,
    parser: TemplateParser | None = None,
) -> tuple[ArticleOverrideReview, ...]:
    """Fetch article pages and produce review-only override minimization results."""
    resolver = LiveGeneratedValueResolver(client=client, module=module)
    reviews: list[ArticleOverrideReview] = []
    for title in titles:
        wikitext = client.get_page(title)
        if wikitext is None:
            raise MissingArticleError(f"Article page does not exist: {title}")
        authoritative_identity, skipped_reason = _authoritative_identity_for_page(
            title,
            article_identities,
            identity_params[0] if identity_params else _DEFAULT_IDENTITY_PARAM,
        )
        if skipped_reason is not None:
            reviews.append(
                ArticleOverrideReview(
                    title=title,
                    original_wikitext=wikitext,
                    migration=None,
                    skipped_reason=skipped_reason,
                )
            )
            continue
        migration = migrate_article_overrides(
            title=title,
            wikitext=wikitext,
            template_names=template_names,
            resolver=resolver,
            identity_params=identity_params,
            authoritative_identity=authoritative_identity,
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
    _cache: dict[tuple[tuple[tuple[str, str], ...], str], str | None] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    def resolve(self, identity_args: Mapping[str, str], fields: Sequence[str]) -> dict[str, str]:
        identity_key = tuple(sorted(identity_args.items()))
        missing_fields = [field for field in fields if (identity_key, field) not in self._cache]
        if missing_fields:
            identity = "".join(f"|{name}={value}" for name, value in identity_args.items())
            snippets = []
            for index, field_name in enumerate(missing_fields):
                snippets.append(
                    f"@@ERENSHOR_FIELD:{index}@@\n"
                    "{{#invoke:" + self.module + "|field" + identity + "|1=" + field_name + "}}\n"
                    f"@@ERENSHOR_END:{index}@@"
                )
            expanded = self.client.expand_templates("\n".join(snippets))
            for index, field_name in enumerate(missing_fields):
                match = re.search(
                    rf"@@ERENSHOR_FIELD:{index}@@\n?(.*?)\n?@@ERENSHOR_END:{index}@@",
                    expanded,
                    flags=re.DOTALL,
                )
                if match is None:
                    self._cache[(identity_key, field_name)] = None
                    continue
                value = match.group(1).strip()
                if _SCRIBUNTO_ERROR.search(value):
                    self._cache[(identity_key, field_name)] = None
                    continue
                self._cache[(identity_key, field_name)] = value

        resolved: dict[str, str] = {}
        for field_name in fields:
            value = self._cache.get((identity_key, field_name))
            if value is not None:
                resolved[field_name] = value
        return resolved
