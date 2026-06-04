"""Tests for the uniform article override classifier."""

from __future__ import annotations

from erenshor.application.wiki_deploy.override_classifier import classify_article_overrides


def _decisions_by_field(article_params, generated_values):
    classification = classify_article_overrides(
        title="Ember Longsword",
        article_params=article_params,
        generated_values=generated_values,
    )
    return {decision.field: decision for decision in classification.decisions}


def test_value_matching_generated_is_removed_as_duplicate() -> None:
    """A param equal to the generated value after normalization is a removable duplicate."""
    decisions = _decisions_by_field({"type": "Weapon"}, {"type": "Weapon"})

    decision = decisions["type"]
    assert decision.decision == "removed_generated_duplicate"
    assert decision.article_value == "Weapon"
    assert decision.generated_value == "Weapon"


def test_value_diverging_from_generated_is_preserved() -> None:
    """A param that differs from the generated value is a real override to preserve."""
    decisions = _decisions_by_field({"type": "Legendary Weapon"}, {"type": "Weapon"})

    assert decisions["type"].decision == "preserved_manual_override"


def test_wikilink_and_whitespace_are_normalized_before_comparison() -> None:
    """Wikilink display text and whitespace differences do not count as overrides."""
    decisions = _decisions_by_field(
        {"questsource": "[[The Lost Blade|Lost Blade]]"},
        {"questsource": "Lost   Blade"},
    )

    assert decisions["questsource"].decision == "removed_generated_duplicate"


def test_blank_sentinel_is_classified_as_intentional_blank() -> None:
    """The documented '-' sentinel keeps a field intentionally blank rather than dropping it."""
    decisions = _decisions_by_field({"imagecaption": "-"}, {"imagecaption": "An ember-forged blade"})

    assert decisions["imagecaption"].decision == "intentional_blank"


def test_empty_parameter_is_removed_not_treated_as_override() -> None:
    """An empty parameter does not silently erase generated data; it is removed."""
    decisions = _decisions_by_field({"imagecaption": "   "}, {"imagecaption": "An ember-forged blade"})

    assert decisions["imagecaption"].decision == "removed_generated_duplicate"


def test_param_without_generated_counterpart_is_preserved() -> None:
    """A manual value with no generated counterpart is preserved as an override."""
    decisions = _decisions_by_field({"othersource": "Found behind the waterfall"}, {})

    assert decisions["othersource"].decision == "preserved_manual_override"


def test_every_parameter_is_classified_uniformly() -> None:
    """All params are evaluated; there is no override-capable subset in the new architecture."""
    classification = classify_article_overrides(
        title="Ember Longsword",
        article_params={"slot": "Main Hand", "damage": "12", "type": "Custom"},
        generated_values={"slot": "Main Hand", "damage": "12", "type": "Weapon"},
    )

    by_field = {decision.field: decision.decision for decision in classification.decisions}
    assert by_field == {
        "slot": "removed_generated_duplicate",
        "damage": "removed_generated_duplicate",
        "type": "preserved_manual_override",
    }
