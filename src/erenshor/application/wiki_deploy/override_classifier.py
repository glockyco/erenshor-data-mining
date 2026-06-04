"""Pre-cutover classifier for manual article overrides.

During the Lua/Cargo cutover, existing article parameters must not be frozen as
permanent manual overrides just because they exist. This pass compares each
override-capable article parameter against the value the generated Lua/export
data would produce, normalizes both sides with the field's documented rule, and
classifies the parameter so reviewed migration edits keep only genuine human
divergence:

- ``removed_generated_duplicate`` - the article value duplicates generated data
  (after normalization) and should be dropped so future exports keep flowing.
- ``preserved_manual_override`` - the article value diverges meaningfully and is
  kept as a human-authored override.
- ``intentional_blank`` - the article uses the documented blank sentinel to keep
  the resolved value intentionally empty.

A field is "override-capable" when its root template keeps manual parameters for
it (i.e. it has a non-default preservation handler). The pass fails closed if an
override-capable field present on the article has no comparison rule, rather than
guessing whether the value is a duplicate.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from erenshor.application.wiki.generators.field_preservation import DEFAULT_PRESERVATION_RULES

ClassificationDecision = Literal[
    "removed_generated_duplicate",
    "preserved_manual_override",
    "intentional_blank",
]

# Documented sentinel meaning "intentionally blank" (see migration plan).
BLANK_SENTINEL = "-"

# Preservation handlers that keep manual content map to a comparison rule. The
# default ``override`` handler is not override-capable: those fields always
# regenerate, so they are excluded from this pass entirely.
_HANDLER_RULES: dict[str, str] = {
    "preserve": "scalar",
    "prefer_manual": "scalar",
    "prefer_database": "scalar",
    "merge": "list_subset",
}

_WIKILINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]|]+)\]\]")
_WHITESPACE_RE = re.compile(r"\s+")
_LIST_SPLIT_RE = re.compile(r"[,\n]")


class MissingComparisonRuleError(Exception):
    """Raised when an override-capable field has no comparison rule.

    The deploy/migration pass must fail closed instead of guessing whether an
    article value duplicates generated data.
    """


@dataclass(frozen=True, slots=True)
class OverrideFieldDecision:
    """Classification of a single override-capable article parameter."""

    field: str
    article_value: str
    generated_value: str
    normalization_rule: str
    decision: ClassificationDecision
    reason: str


@dataclass(frozen=True, slots=True)
class ArticleOverrideClassification:
    """All override decisions for one article page."""

    title: str
    template: str
    decisions: tuple[OverrideFieldDecision, ...]


def classify_article_overrides(
    *,
    title: str,
    template: str,
    article_params: Mapping[str, str],
    generated_values: Mapping[str, str],
    preservation_rules: Mapping[str, Mapping[str, str]] = DEFAULT_PRESERVATION_RULES,
) -> ArticleOverrideClassification:
    """Classify override-capable article parameters against generated values."""
    template_rules = preservation_rules.get(template, {})

    decisions: list[OverrideFieldDecision] = []
    for field, handler in template_rules.items():
        if field not in article_params:
            continue
        if handler == "override":
            # Explicitly always-regenerate; not an override-capable field.
            continue

        rule = _HANDLER_RULES.get(handler)
        if rule is None:
            raise MissingComparisonRuleError(
                f"Override-capable field '{field}' on '{title}' uses handler "
                f"'{handler}' with no comparison rule; refusing to classify."
            )

        article_value = article_params[field]
        generated_value = generated_values.get(field, "")
        decision, reason = _classify_field(rule, article_value, generated_value)
        decisions.append(
            OverrideFieldDecision(
                field=field,
                article_value=article_value,
                generated_value=generated_value,
                normalization_rule=rule,
                decision=decision,
                reason=reason,
            )
        )

    return ArticleOverrideClassification(title=title, template=template, decisions=tuple(decisions))


def _classify_field(rule: str, article_value: str, generated_value: str) -> tuple[ClassificationDecision, str]:
    """Apply one comparison rule to an article/generated value pair."""
    if article_value.strip() == BLANK_SENTINEL:
        return "intentional_blank", "documented blank sentinel"

    if not article_value.strip():
        return "removed_generated_duplicate", "empty parameter is not an override"

    if rule == "scalar":
        if _normalize_scalar(article_value) == _normalize_scalar(generated_value):
            return "removed_generated_duplicate", "scalar value matches generated data"
        return "preserved_manual_override", "scalar value diverges from generated data"

    if rule == "list_subset":
        article_items = _normalize_list(article_value)
        generated_items = _normalize_list(generated_value)
        if article_items <= generated_items:
            return "removed_generated_duplicate", "list entries are all present in generated data"
        return "preserved_manual_override", "list adds entries absent from generated data"

    raise MissingComparisonRuleError(f"Unhandled comparison rule: {rule}")


def _normalize_scalar(value: str) -> str:
    """Strip wikilink markup and collapse whitespace for scalar comparison."""
    without_links = _WIKILINK_RE.sub(r"\1", value)
    return _WHITESPACE_RE.sub(" ", without_links).strip()


def _normalize_list(value: str) -> frozenset[str]:
    """Split a list field into a normalized, order-independent set of entries."""
    items = (_normalize_scalar(part) for part in _LIST_SPLIT_RE.split(value))
    return frozenset(item for item in items if item)
