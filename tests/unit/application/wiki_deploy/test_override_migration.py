"""Tests for the article override migration pass."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

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


class FakeExpansionClient:
    def __init__(self, outputs: dict[str, str]) -> None:
        self.outputs = outputs
        self.calls: list[str] = []

    def expand_templates(self, text: str) -> str:
        self.calls.append(text)
        if text in self.outputs:
            return self.outputs[text]
        if len(self.outputs) == 1:
            return next(iter(self.outputs.values()))
        return ""


def test_live_resolver_batches_field_accessor_expansions() -> None:
    """The resolver expands all requested fields in one parser pass for an entity."""
    from erenshor.application.wiki_deploy.override_migration import LiveGeneratedValueResolver

    client = FakeExpansionClient(
        {
            "expected": (
                "@@ERENSHOR_FIELD:0@@\nWeapon\n@@ERENSHOR_END:0@@\n@@ERENSHOR_FIELD:1@@\nA blade\n@@ERENSHOR_END:1@@"
            )
        }
    )
    resolver = LiveGeneratedValueResolver(client=client, module="Erenshor/Item")
    resolved = resolver.resolve({"stablekey": "item:ember"}, ["type", "description"])
    assert resolved == {"type": "Weapon", "description": "A blade"}
    assert len(client.calls) == 1
    assert "{{#invoke:Erenshor/Item|field|stablekey=item:ember|1=type}}" in client.calls[0]
    assert "{{#invoke:Erenshor/Item|field|stablekey=item:ember|1=description}}" in client.calls[0]


def test_live_resolver_omits_fields_the_module_cannot_read() -> None:
    """A Scribunto error is not a generated value; the field is left for preservation."""
    from erenshor.application.wiki_deploy.override_migration import LiveGeneratedValueResolver

    slot_text = "{{#invoke:Erenshor/Item|field|stablekey=item:ember|1=slot}}"
    error = '<strong class="error"><span class="scribunto-error">Lua error: Unknown field.</span></strong>'
    client = FakeExpansionClient({slot_text: error})
    resolver = LiveGeneratedValueResolver(client=client, module="Erenshor/Item")
    resolved = resolver.resolve({"stablekey": "item:ember"}, ["slot"])
    assert resolved == {}


def test_migration_injects_authoritative_identity_when_article_lacks_it() -> None:
    """The repo page mapping supplies stable identity for legacy root templates."""
    wikitext = "{{Item|title=Ember Longsword|type=Weapon|source=Custom drop}}"
    resolver = FakeResolver({"title": "Ember Longsword", "type": "Weapon", "source": "Quest"})

    result = migrate_article_overrides(
        title="Ember Longsword",
        wikitext=wikitext,
        template_names=["Item"],
        identity_params=("stablekey",),
        resolver=resolver,
        authoritative_identity={"stablekey": "item:ember_longsword"},
    )

    assert resolver.identity_args == {"stablekey": "item:ember_longsword"}
    assert "stablekey=item:ember_longsword" in result.minimized_wikitext
    assert "title=" not in result.minimized_wikitext
    assert "type=" not in result.minimized_wikitext
    assert "source=Custom drop" in result.minimized_wikitext


def test_migration_rejects_conflicting_article_identity() -> None:
    """A page stablekey that disagrees with the repo mapping is unsafe to minimize."""
    from erenshor.application.wiki_deploy.override_migration import ArticleIdentityConflictError

    with pytest.raises(ArticleIdentityConflictError, match="Ember Longsword"):
        migrate_article_overrides(
            title="Ember Longsword",
            wikitext="{{Item|stablekey=item:wrong|type=Weapon}}",
            template_names=["Item"],
            identity_params=("stablekey",),
            resolver=FakeResolver({"type": "Weapon"}),
            authoritative_identity={"stablekey": "item:ember_longsword"},
        )


class FakeReviewClient(FakeExpansionClient):
    def __init__(self, pages: dict[str, str | None], outputs: dict[str, str]) -> None:
        super().__init__(outputs)
        self.pages = pages
        self.fetched_titles: list[str] = []

    def get_page(self, title: str) -> str | None:
        self.fetched_titles.append(title)
        return self.pages.get(title)


def test_review_article_overrides_fetches_pages_and_returns_migrations() -> None:
    """The review service fetches page text and classifies it through authoritative identity."""
    from erenshor.application.wiki_deploy.override_migration import review_article_overrides

    type_text = "{{#invoke:Erenshor/Item|field|stablekey=item:ember|1=type}}"
    source_text = "{{#invoke:Erenshor/Item|field|stablekey=item:ember|1=source}}"
    client = FakeReviewClient(
        pages={"Ember Longsword": "{{Item|title=Ember Longsword|type=Weapon|source=Custom drop}}"},
        outputs={
            "batched": (
                "@@ERENSHOR_FIELD:0@@\nEmber Longsword\n@@ERENSHOR_END:0@@\n"
                "@@ERENSHOR_FIELD:1@@\nWeapon\n@@ERENSHOR_END:1@@\n"
                "@@ERENSHOR_FIELD:2@@\nQuest\n@@ERENSHOR_END:2@@"
            )
        },
    )

    reviews = review_article_overrides(
        client=client,
        titles=("Ember Longsword",),
        template_names=("Item",),
        module="Erenshor/Item",
        article_identities={"Ember Longsword": ("item:ember",)},
    )

    assert client.fetched_titles == ["Ember Longsword"]
    assert len(reviews) == 1
    [review] = reviews
    assert review.title == "Ember Longsword"
    assert review.changed is True
    assert review.skipped_reason is None
    assert review.migration is not None
    assert review.migration.removed_fields == ("title", "type")
    assert review.migration.preserved_fields == ("source",)
    assert review.migration.minimized_wikitext == "{{Item|source=Custom drop|stablekey=item:ember}}"
    assert len(client.calls) == 1
    assert type_text in client.calls[0]
    assert source_text in client.calls[0]


def test_review_article_overrides_fails_fast_when_article_is_missing() -> None:
    """Missing pages abort the review instead of silently producing an empty report."""
    from erenshor.application.wiki_deploy.override_migration import MissingArticleError, review_article_overrides

    client = FakeReviewClient(pages={"Missing Sword": None}, outputs={})

    with pytest.raises(MissingArticleError, match="Missing Sword"):
        review_article_overrides(
            client=client,
            titles=("Missing Sword",),
            template_names=("Item",),
            module="Erenshor/Item",
        )


def test_review_article_overrides_skips_ambiguous_identity_without_expansion() -> None:
    """Multi-entity pages are reported for manual review instead of guessing a stablekey."""
    from erenshor.application.wiki_deploy.override_migration import review_article_overrides

    client = FakeReviewClient(pages={"A Lost Poem": "{{Item|title=A Lost Poem (1)}}"}, outputs={})

    reviews = review_article_overrides(
        client=client,
        titles=("A Lost Poem",),
        template_names=("Item",),
        module="Erenshor/Item",
        article_identities={"A Lost Poem": ("item:poem_1", "item:poem_2")},
    )

    assert len(reviews) == 1
    [review] = reviews
    assert review.migration is None
    assert review.skipped_reason == "ambiguous identity: 2 stable keys mapped to page"
    assert client.calls == []
