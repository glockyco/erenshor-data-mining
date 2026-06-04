"""Tests for the article override migration pass."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from erenshor.application.wiki_deploy.override_migration import migrate_article_overrides


class FakeResolver:
    """Returns pre-set generated values for an entity, recording the request."""

    def __init__(self, generated: dict[str, str]) -> None:
        self.generated = generated
        self.requested_fields: tuple[str, ...] = ()
        self.identity_args: Mapping[str, str] = {}

    def resolve(self, identity_args: Mapping[str, str], fields: Sequence[str]) -> dict[str, str]:
        self.identity_args = identity_args
        self.requested_fields = tuple(fields)
        return {field: self.generated.get(field, "") for field in fields}


def test_duplicates_are_removed_and_overrides_kept() -> None:
    """A param equal to generated data is dropped; a divergent one is kept."""
    wikitext = "{{Item|stablekey=ember|type=Weapon|othersource=Behind the waterfall}}"
    resolver = FakeResolver({"type": "Weapon", "othersource": ""})

    result = migrate_article_overrides(
        title="Ember Longsword",
        wikitext=wikitext,
        template_names=["Item"],
        identity_params=("stablekey",),
        resolver=resolver,
    )

    assert "type=" not in result.minimized_wikitext
    assert "othersource=Behind the waterfall" in result.minimized_wikitext
    assert "stablekey=ember" in result.minimized_wikitext
    assert result.removed_fields == ("type",)
    assert result.preserved_fields == ("othersource",)


def test_identity_params_are_kept_and_not_classified() -> None:
    """Identity selectors are never compared or removed; they resolve the entity."""
    wikitext = "{{Item|stablekey=ember|type=Weapon}}"
    resolver = FakeResolver({"type": "Weapon"})

    result = migrate_article_overrides(
        title="Ember Longsword",
        wikitext=wikitext,
        template_names=["Item"],
        identity_params=("stablekey",),
        resolver=resolver,
    )

    assert "stablekey" not in resolver.requested_fields
    assert "type" in resolver.requested_fields
    classified_fields = {decision.field for decision in result.classification.decisions}
    assert classified_fields == {"type"}


def test_blank_sentinel_param_is_preserved() -> None:
    """The documented blank sentinel survives migration as an intentional blank."""
    wikitext = "{{Item|stablekey=ember|imagecaption=-}}"
    resolver = FakeResolver({"imagecaption": "An ember-forged blade"})

    result = migrate_article_overrides(
        title="Ember Longsword",
        wikitext=wikitext,
        template_names=["Item"],
        identity_params=("stablekey",),
        resolver=resolver,
    )

    assert "imagecaption=-" in result.minimized_wikitext
    assert result.removed_fields == ()
    assert result.preserved_fields == ("imagecaption",)


def test_field_without_generated_value_is_kept_as_override() -> None:
    """A param the resolver cannot resolve is kept, never dropped on uncertainty."""
    wikitext = "{{Item|stablekey=ember|image=Custom.png}}"
    resolver = FakeResolver({})  # resolver returns "" for unknown fields

    result = migrate_article_overrides(
        title="Ember Longsword",
        wikitext=wikitext,
        template_names=["Item"],
        identity_params=("stablekey",),
        resolver=resolver,
    )

    assert "image=Custom.png" in result.minimized_wikitext
    assert result.removed_fields == ()
