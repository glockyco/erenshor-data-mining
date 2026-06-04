"""Tests for the pre-cutover article override classifier."""

from __future__ import annotations

import pytest

from erenshor.application.wiki_deploy.override_classifier import (
    MissingComparisonRuleError,
    classify_article_overrides,
)


def _decisions_by_field(title: str, template: str, article_params, generated_values, **kwargs):
    classification = classify_article_overrides(
        title=title,
        template=template,
        article_params=article_params,
        generated_values=generated_values,
        **kwargs,
    )
    return {decision.field: decision for decision in classification.decisions}


def test_scalar_field_matching_generated_value_is_removed_as_duplicate() -> None:
    """A manual scalar field equal to the generated value after normalization is a removable duplicate."""
    decisions = _decisions_by_field(
        "Ember Longsword",
        "Item",
        {"imagecaption": "A  fiery   blade"},
        {"imagecaption": "A fiery blade"},
    )

    decision = decisions["imagecaption"]
    assert decision.decision == "removed_generated_duplicate"
    assert decision.article_value == "A  fiery   blade"
    assert decision.generated_value == "A fiery blade"
    assert decision.normalization_rule == "scalar"


def test_scalar_field_diverging_from_generated_value_is_preserved() -> None:
    """A manual scalar field that differs from the generated value is a real override to preserve."""
    decisions = _decisions_by_field(
        "Ember Longsword",
        "Item",
        {"imagecaption": "Hand-drawn concept art"},
        {"imagecaption": "A fiery blade"},
    )

    decision = decisions["imagecaption"]
    assert decision.decision == "preserved_manual_override"


def test_scalar_field_wikilink_markup_is_normalized_before_comparison() -> None:
    """Wikilink display text equal to the generated plain value is a removable duplicate."""
    decisions = _decisions_by_field(
        "Ember Longsword",
        "Item",
        {"imagecaption": "[[Forge|Fiery blade]]"},
        {"imagecaption": "Fiery blade"},
    )

    assert decisions["imagecaption"].decision == "removed_generated_duplicate"


def test_blank_sentinel_is_classified_as_intentional_blank() -> None:
    """The documented '-' sentinel keeps a field intentionally blank rather than dropping it."""
    decisions = _decisions_by_field(
        "Ember Longsword",
        "Item",
        {"imagecaption": "-"},
        {"imagecaption": "A fiery blade"},
    )

    decision = decisions["imagecaption"]
    assert decision.decision == "intentional_blank"


def test_empty_parameter_is_removed_not_treated_as_blank_override() -> None:
    """An empty parameter does not silently erase generated data; it is removed."""
    decisions = _decisions_by_field(
        "Ember Longsword",
        "Item",
        {"imagecaption": "   "},
        {"imagecaption": "A fiery blade"},
    )

    assert decisions["imagecaption"].decision == "removed_generated_duplicate"


def test_merge_field_subset_of_generated_list_is_removed_as_duplicate() -> None:
    """A merge-list field whose entries are all generated adds nothing and is removable."""
    decisions = _decisions_by_field(
        "Ember Longsword",
        "Item",
        {"type": "Sword, Weapon"},
        {"type": "Weapon, Sword, One-Handed"},
    )

    decision = decisions["type"]
    assert decision.decision == "removed_generated_duplicate"
    assert decision.normalization_rule == "list_subset"


def test_merge_field_with_manual_addition_is_preserved() -> None:
    """A merge-list field with an entry absent from generated data is a real override."""
    decisions = _decisions_by_field(
        "Ember Longsword",
        "Item",
        {"type": "Weapon, Collector Favorite"},
        {"type": "Weapon"},
    )

    assert decisions["type"].decision == "preserved_manual_override"


def test_scalar_field_absent_from_generated_data_is_preserved() -> None:
    """A manual value with no generated counterpart is preserved as an override."""
    decisions = _decisions_by_field(
        "Ember Longsword",
        "Item",
        {"othersource": "Found behind the waterfall"},
        {},
    )

    assert decisions["othersource"].decision == "preserved_manual_override"


def test_non_override_capable_field_is_not_classified() -> None:
    """Fields that always regenerate (default override handler) are left for blanket removal."""
    classification = classify_article_overrides(
        title="Ember Longsword",
        template="Item",
        article_params={"source": "Drops from Ember Drake", "imagecaption": "A fiery blade"},
        generated_values={"imagecaption": "A fiery blade"},
    )

    classified_fields = {decision.field for decision in classification.decisions}
    assert "source" not in classified_fields
    assert "imagecaption" in classified_fields


def test_override_capable_field_without_comparison_rule_fails_closed() -> None:
    """An override-capable field whose handler has no comparison rule aborts the pass."""
    with pytest.raises(MissingComparisonRuleError) as excinfo:
        classify_article_overrides(
            title="Ember Longsword",
            template="Item",
            article_params={"mystery": "value"},
            generated_values={},
            preservation_rules={"Item": {"mystery": "handler_with_no_rule"}},
        )

    assert "mystery" in str(excinfo.value)


def test_unknown_template_yields_no_decisions() -> None:
    """A template with no preservation rules keeps no manual overrides."""
    classification = classify_article_overrides(
        title="Some Page",
        template="NotATemplate",
        article_params={"field": "value"},
        generated_values={},
    )

    assert classification.decisions == ()
