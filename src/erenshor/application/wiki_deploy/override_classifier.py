"""Uniform article override classifier for the Lua/Cargo cutover.

The new architecture separates the two data sources cleanly: generated data
lives in the ``Module:Erenshor/Data/*`` modules, and manual overrides live in
the infobox parameters on each article. The presentation module applies a
straight ``article-arg-else-generated`` resolution for every parameter, so
every parameter is uniformly overridable.

Migrating an article to the cutover therefore reduces to one rule, applied to
every parameter: if the parameter equals the generated value it is a redundant
duplicate and is dropped so future exports flow through; if it differs it is a
genuine manual override and is kept. The documented ``-`` sentinel keeps a
field intentionally blank.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ClassificationDecision = Literal[
    "removed_generated_duplicate",
    "preserved_manual_override",
    "intentional_blank",
]

# Documented sentinel meaning "intentionally blank" (see migration plan).
BLANK_SENTINEL = "-"

_WIKILINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]|]+)\]\]")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class OverrideFieldDecision:
    """Classification of a single article parameter against generated data."""

    field: str
    article_value: str
    generated_value: str
    decision: ClassificationDecision
    reason: str


@dataclass(frozen=True, slots=True)
class ArticleOverrideClassification:
    """All override decisions for one article page."""

    title: str
    decisions: tuple[OverrideFieldDecision, ...]


def classify_article_overrides(
    *,
    title: str,
    article_params: Mapping[str, str],
    generated_values: Mapping[str, str],
) -> ArticleOverrideClassification:
    """Classify each article parameter against its generated value.

    ``article_params`` is the set of infobox parameters to evaluate (the caller
    excludes identity selectors such as ``stablekey``). ``generated_values`` is
    the value the presentation module produces for each field with no override
    applied; a field absent from it is treated as having no generated value.
    """
    decisions: list[OverrideFieldDecision] = []
    for field, article_value in article_params.items():
        generated_value = generated_values.get(field, "")
        decision, reason = _classify(article_value, generated_value)
        decisions.append(
            OverrideFieldDecision(
                field=field,
                article_value=article_value,
                generated_value=generated_value,
                decision=decision,
                reason=reason,
            )
        )
    return ArticleOverrideClassification(title=title, decisions=tuple(decisions))


def _classify(article_value: str, generated_value: str) -> tuple[ClassificationDecision, str]:
    """Decide whether one article value is a duplicate, an override, or an intentional blank."""
    if article_value.strip() == BLANK_SENTINEL:
        return "intentional_blank", "documented blank sentinel"
    if not article_value.strip():
        return "removed_generated_duplicate", "empty parameter is not an override"
    if _normalize(article_value) == _normalize(generated_value):
        return "removed_generated_duplicate", "value matches generated data"
    return "preserved_manual_override", "value diverges from generated data"


def _normalize(value: str) -> str:
    """Strip wikilink markup and collapse whitespace for comparison."""
    without_links = _WIKILINK_RE.sub(r"\1", value)
    return _WHITESPACE_RE.sub(" ", without_links).strip()
