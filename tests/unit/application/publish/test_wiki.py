"""Ordered wiki publication keeps native guards and separate prose approval."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.publish import wiki
from erenshor.application.publish.models import SurfaceUncertainError
from erenshor.application.wiki.generators.base import GeneratedPage, PageMetadata
from erenshor.application.wiki.services.generate_service import WikiGenerateService
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_deploy.manifest import read_repo_page_manifest
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.application.wiki_lua.link_catalog import build_links_data
from erenshor.infrastructure.wiki import (
    MediaWikiNetworkError,
    MediaWikiPageSnapshot,
    MediaWikiParse,
    MediaWikiParsedLink,
)


class SnapshotWiki(MediaWikiFake):
    """Keep the host's content-model metadata in snapshots."""

    api_url = "https://fixture.invalid/api.php"
    lose_answer = False

    def get_page_snapshots(
        self,
        titles: Sequence[str],
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> dict[str, MediaWikiPageSnapshot]:
        snapshots = super().get_page_snapshots(titles, assertion=assertion, assert_user=assert_user)
        return {
            title: replace(
                snapshot,
                content_model=("Scribunto" if title.startswith("Module:") else "wikitext")
                if snapshot.revision
                else None,
            )
            for title, snapshot in snapshots.items()
        }

    def safe_edit_page(self, *args: Any, **kwargs: Any) -> int:
        revision = super().safe_edit_page(*args, **kwargs)
        if self.lose_answer:
            raise MediaWikiNetworkError("response lost after write")
        return revision


@pytest.fixture
def wiki_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    wiki_dir = tmp_path / "variants/main/wiki"
    wiki_dir.mkdir(parents=True)
    database = tmp_path / "variants/main/erenshor.sqlite"
    database.write_bytes(b"frozen clean database")
    variant = SimpleNamespace(
        resolved_wiki=lambda _: wiki_dir,
        resolved_database=lambda _: database,
        maps=SimpleNamespace(resolved_source_dir=lambda _: tmp_path / "src/maps"),
    )
    ctx = SimpleNamespace(
        repo_root=tmp_path,
        variant="main",
        config=SimpleNamespace(
            variants={"main": variant},
            global_=SimpleNamespace(
                mediawiki=SimpleNamespace(
                    api_url="https://fixture.invalid/api.php",
                    bot_username="ErenshorBot@Publisher",
                    max_page_bytes=4194304,
                )
            ),
        ),
    )
    client = SnapshotWiki()
    client.put_page("Example", "People's prose.\n{{Item|name=Example|stablekey=item:example|value=old}}")
    client.put_page("Template:Item", "Parameter-only template")
    catalog_sha = str(build_links_data(())["catalogSha256"])
    catalog_source = f'return {{ catalogSha256 = "{catalog_sha}" }}\n'
    client.put_page(wiki.DATA_LINK_TITLE, catalog_source)
    generated_from: list[str] = []

    def generate_lua(_: Any, storage: WikiStorage, output: Path) -> dict[str, Path]:
        path = output / "Erenshor/Data/Links.lua"
        path.parent.mkdir(parents=True)
        path.write_text(catalog_source, encoding="utf-8")
        return {wiki.DATA_LINK_TITLE: path}

    def generate_articles(_: Any, storage: WikiStorage, titles: Sequence[str]) -> tuple[tuple[Any, ...], list[str]]:
        for title in titles:
            original = storage.read_fetched_by_title(title) or ""
            generated_from.append(original)
            storage.save_generated_by_title(
                title,
                ["item:example"],
                original.replace("value=old", "value=new") + "\n",
            )
        return (), []

    monkeypatch.setattr(wiki, "_generate_lua", generate_lua)
    monkeypatch.setattr(wiki, "_generate_articles", generate_articles)
    monkeypatch.setattr(wiki, "create_readonly_mediawiki_client", lambda _: client)
    monkeypatch.setattr("erenshor.cli.commands.wiki._create_mediawiki_client", lambda _: client)
    monkeypatch.setattr(wiki, "recorded_build_id", lambda _: "42")
    return SimpleNamespace(
        ctx=ctx,
        client=client,
        root=tmp_path,
        wiki_dir=wiki_dir,
        run=wiki_dir / "publish/run",
        generated_from=generated_from,
        catalog_sha=catalog_sha,
        generate_articles=generate_articles,
    )


def prepare(env: SimpleNamespace, **selection: Any) -> list[dict[str, Any]]:
    operations = wiki.prepare(env.ctx, {"summary": "Refresh reviewed facts", **selection}, env.run)
    # The coordinator injects this nondigested runtime location after payload loading.
    for operation in operations:
        operation["_run_dir"] = str(env.run)
    return operations


def reviewed_prose(env: SimpleNamespace) -> dict[str, str]:
    path = env.wiki_dir / "reviewed-edits.toml"
    path.write_text(
        '[[pages]]\ntitle = "Example"\nsummary = "Correct the reviewed sentence"\n'
        '[[pages.replace]]\nold = "People\'s prose."\nnew = "Reviewed editor prose."\n',
        encoding="utf-8",
    )
    return {
        "page_edits_file": str(path),
        "prose_review_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_stale_catalog_requires_explicit_data_selection(wiki_env: SimpleNamespace) -> None:
    wiki_env.client.put_page(wiki.DATA_LINK_TITLE, 'return { catalogSha256 = "' + "0" * 64 + '" }')
    with pytest.raises(ValueError, match="Example needs changed data Module:Erenshor/Data/Links"):
        prepare(wiki_env, article_titles=["Example"])
    assert wiki_env.client.revisions["Example"] == 1


def test_selected_catalog_is_a_receipt_bound_article_predecessor(wiki_env: SimpleNamespace) -> None:
    wiki_env.client.put_page(wiki.DATA_LINK_TITLE, 'return { catalogSha256 = "' + "0" * 64 + '" }')
    data, article = prepare(wiki_env, article_titles=["Example"], data_titles=[wiki.DATA_LINK_TITLE])
    assert data["id"] in article["dependencies"]
    base = article["payload"]["dependency_bases"][wiki.DATA_LINK_TITLE]
    assert base["receipt"] == data["id"]
    wiki.check(wiki_env.ctx, article, article["payload"], {})
    receipt = wiki.execute(wiki_env.ctx, data, data["payload"], {})
    wiki.check(wiki_env.ctx, article, article["payload"], {data["id"]: receipt})
    assert wiki_env.client.revisions["Example"] == 1
    # Every review sidecar can be serialized without a custom encoder.
    json.dumps([data["payload"], article["payload"]], allow_nan=False)


def test_dependency_revision_change_invalidates_the_article(wiki_env: SimpleNamespace) -> None:
    [article] = prepare(wiki_env, article_titles=["Example"])
    wiki_env.client.put_page("Template:Item", "Parameter-only template", user="Editor")
    with pytest.raises(ValueError, match="Template:Item changed after review"):
        wiki.check(wiki_env.ctx, article, article["payload"], {})
    assert wiki_env.client.revisions["Example"] == 1


def test_editor_revision_change_invalidates_even_identical_text(wiki_env: SimpleNamespace) -> None:
    [article] = prepare(wiki_env, article_titles=["Example"])
    wiki_env.client.put_page("Example", wiki_env.client.pages["Example"], user="Editor")
    with pytest.raises(ValueError, match="Example changed after review"):
        wiki.check(wiki_env.ctx, article, article["payload"], {})


def test_missing_dependency_is_not_silently_selected(wiki_env: SimpleNamespace) -> None:
    source = wiki_env.root / "wiki/modules/Erenshor/Reader.lua"
    source.parent.mkdir(parents=True)
    source.write_text('return mw.loadData("Module:Erenshor/Data/Absent")', encoding="utf-8")
    with pytest.raises(ValueError, match="Reader needs missing page Module:Erenshor/Data/Absent"):
        prepare(wiki_env, repo_titles=["Module:Erenshor/Reader"])
    assert "Module:Erenshor/Reader" not in wiki_env.client.pages


def test_prose_requires_separate_matching_review_before_generation(wiki_env: SimpleNamespace) -> None:
    selection = reviewed_prose(wiki_env)
    with pytest.raises(ValueError, match="separate prose_review_sha256"):
        prepare(wiki_env, page_edits_file=selection["page_edits_file"])
    with pytest.raises(ValueError, match="separate review digest"):
        prepare(wiki_env, **{**selection, "prose_review_sha256": "0" * 64})
    assert wiki_env.generated_from == []
    assert wiki_env.client.revisions["Example"] == 1


@pytest.mark.parametrize("generation", ["_generate_lua", "_generate_articles"])
def test_mutating_reviewed_prose_during_generation_refuses_preparation(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, generation: str
) -> None:
    selection = reviewed_prose(wiki_env)
    path = Path(selection["page_edits_file"])
    native_generate = getattr(wiki, generation)

    def mutate_file(*args: Any, **kwargs: Any) -> Any:
        path.write_bytes(path.read_bytes().replace(b"Reviewed editor prose.", b"Unreviewed replacement."))
        return native_generate(*args, **kwargs)

    monkeypatch.setattr(wiki, generation, mutate_file)

    with pytest.raises(ValueError, match="changed during preparation after its separate review"):
        prepare(wiki_env, article_titles=["Example"], **selection)

    assert "Reviewed editor prose." in wiki_env.generated_from[0]
    assert "Unreviewed replacement." not in wiki_env.generated_from[0]
    assert wiki_env.client.revisions["Example"] == 1


def test_prose_input_pin_retains_the_separately_approved_hash(wiki_env: SimpleNamespace) -> None:
    selection = reviewed_prose(wiki_env)
    [prose] = prepare(wiki_env, **selection)

    assert prose["input_sha256"] == {selection["page_edits_file"]: selection["prose_review_sha256"]}


def test_temporarily_mutated_prose_is_never_parsed_as_reviewed_content(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection = reviewed_prose(wiki_env)
    path = Path(selection["page_edits_file"])
    approved = path.read_bytes()
    native_lua = wiki._generate_lua
    native_articles = wiki._generate_articles

    def changed_before_planning(*args: Any, **kwargs: Any) -> Any:
        path.write_bytes(approved.replace(b"Reviewed editor prose.", b"Unreviewed replacement."))
        return native_lua(*args, **kwargs)

    def restored_after_planning(*args: Any, **kwargs: Any) -> Any:
        result = native_articles(*args, **kwargs)
        path.write_bytes(approved)
        return result

    monkeypatch.setattr(wiki, "_generate_lua", changed_before_planning)
    monkeypatch.setattr(wiki, "_generate_articles", restored_after_planning)
    prose, article = prepare(wiki_env, article_titles=["Example"], **selection)

    assert "Reviewed editor prose." in prose["payload"]["content"]
    assert "Reviewed editor prose." in article["payload"]["content"]
    assert "Unreviewed replacement." not in article["payload"]["content"]
    assert prose["input_sha256"][str(path)] == selection["prose_review_sha256"]


def test_projection_preserves_editor_prose_and_uses_receipt_revision(wiki_env: SimpleNamespace) -> None:
    prose, article = prepare(wiki_env, article_titles=["Example"], **reviewed_prose(wiki_env))
    assert "Reviewed editor prose." in wiki_env.generated_from[0]
    assert "People's prose." not in article["payload"]["content"]
    assert article["expected_base"]["receipt"] == prose["id"]
    assert article["expected_base"]["initial"]["revision_id"] == 1
    # Initial preflight must work before the prose receipt exists.
    wiki.check(wiki_env.ctx, article, article["payload"], {})
    prose_receipt = wiki.execute(wiki_env.ctx, prose, prose["payload"], {})
    receipts = {prose["id"]: prose_receipt}
    article_receipt = wiki.execute(wiki_env.ctx, article, article["payload"], receipts)
    receipts[article["id"]] = article_receipt
    assert article_receipt["old_revision"] == prose_receipt["new_revision"]
    assert "Reviewed editor prose." in wiki_env.client.pages["Example"]
    assert "value=new" in wiki_env.client.pages["Example"]
    assert len(wiki_env.generated_from) == 2
    # A completed article is the only permitted same-page successor of prose.
    wiki.reconcile(wiki_env.ctx, prose, prose["payload"], prose_receipt, receipts)
    wiki.reconcile(wiki_env.ctx, article, article["payload"], article_receipt, receipts)
    assert not (wiki_env.root / "wiki/content/Example.wiki").exists()


def test_real_regeneration_mismatch_stops_before_article_write(
    wiki_env: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prose, article = prepare(wiki_env, article_titles=["Example"], **reviewed_prose(wiki_env))
    receipt = wiki.execute(wiki_env.ctx, prose, prose["payload"], {})

    def different_generation(
        ctx: Any, storage: WikiStorage, titles: Sequence[str]
    ) -> tuple[tuple[Any, ...], list[str]]:
        wiki_env.generate_articles(ctx, storage, titles)
        for title in titles:
            storage.save_generated_by_title(title, ["item:example"], "Different unreviewed bytes")
        return (), []

    monkeypatch.setattr(wiki, "_generate_articles", different_generation)
    with pytest.raises(ValueError, match="regenerated article differs"):
        wiki.execute(wiki_env.ctx, article, article["payload"], {prose["id"]: receipt})
    assert wiki_env.client.revisions["Example"] == receipt["new_revision"]
    manifest = read_repo_page_manifest(Path(receipt["manifest"]))
    assert manifest.api_url == wiki_env.client.api_url
    assert manifest.variant == "main"
    assert manifest.wiki_root == str(wiki_env.ctx.config.variants["main"].resolved_wiki(wiki_env.root))
    assert manifest.entries[0].new_revision_id == receipt["new_revision"]
    assert (wiki_env.root / manifest.entries[0].rollback_text_source).read_text() == prose["payload"]["original"]


def test_unrelated_post_prose_revision_is_not_accepted(wiki_env: SimpleNamespace) -> None:
    prose, article = prepare(wiki_env, article_titles=["Example"], **reviewed_prose(wiki_env))
    receipt = wiki.execute(wiki_env.ctx, prose, prose["payload"], {})
    wiki_env.client.put_page("Example", wiki_env.client.pages["Example"], user="Editor")
    with pytest.raises(ValueError, match="Example changed after review"):
        wiki.check(wiki_env.ctx, article, article["payload"], {prose["id"]: receipt})


def test_prose_receipt_must_match_projected_content(wiki_env: SimpleNamespace) -> None:
    prose, article = prepare(wiki_env, article_titles=["Example"], **reviewed_prose(wiki_env))
    receipt = wiki.execute(wiki_env.ctx, prose, prose["payload"], {})
    with pytest.raises(ValueError, match="Predecessor content does not match"):
        wiki.check(
            wiki_env.ctx,
            article,
            article["payload"],
            {
                prose["id"]: {**receipt, "content_sha256": "0" * 64},
            },
        )


@pytest.mark.parametrize("generate_transcluded_article", [False, True])
@pytest.mark.parametrize("flattened_live_reference", [False, True])
def test_article_transclusion_uses_the_approved_dependency_stage(
    wiki_env: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    generate_transcluded_article: bool,
    flattened_live_reference: bool,
) -> None:
    dependency = "Other Article"
    original = "Old prose.\n{{Old}}\n{{Item|name=Other|stablekey=item:other|value=old}}"
    projected = original.replace("Old prose.\n{{Old}}", "Reviewed prose.\n{{New}}")
    wiki_env.client.put_page("Example", wiki_env.client.pages["Example"] + "\n{{:Other Article}}")
    wiki_env.client.put_page(dependency, original)
    wiki_env.client.put_page("Template:Old", "Old dependency")
    wiki_env.client.put_page("Template:New", "Approved dependency")
    path = wiki_env.wiki_dir / "reviewed-edits.toml"
    path.write_text(
        f'[[pages]]\ntitle = "{dependency}"\nsummary = "Reviewed prose"\n'
        f"[[pages.replace]]\nold = {json.dumps(original)}\nnew = {json.dumps(projected)}\n",
        encoding="utf-8",
    )
    native_parse = wiki_env.client.parse_wikitext

    def parse_transclusions(title: str, text: str, **kwargs: Any) -> MediaWikiParse:
        result = native_parse(title, text, **kwargs)
        # Main-namespace transclusions come from action=parse, not the template-only scan.
        references = []
        if "{{:Other Article}}" in text:
            references.append(MediaWikiParsedLink(dependency, True))
            if flattened_live_reference and "{{Old}}" in wiki_env.client.pages[dependency]:
                references.append(MediaWikiParsedLink("Template:Old", True))
        if "{{Old}}" in text:
            references.append(MediaWikiParsedLink("Template:Old", True))
        if "{{New}}" in text:
            references.append(MediaWikiParsedLink("Template:New", True))
        return replace(result, templates=tuple(references))

    monkeypatch.setattr(wiki_env.client, "parse_wikitext", parse_transclusions)
    operations = prepare(
        wiki_env,
        article_titles=["Example", dependency] if generate_transcluded_article else ["Example"],
        page_edits_file=str(path),
        prose_review_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    by_id = {operation["id"]: operation for operation in operations}
    prose = by_id["wiki_prose:" + dependency]
    article = by_id["wiki_article:Example"]
    predecessor = by_id[("wiki_article:" if generate_transcluded_article else "wiki_prose:") + dependency]
    bases = article["payload"]["dependency_bases"]
    assert bases[dependency]["receipt"] == predecessor["id"]
    assert bases[dependency]["content_sha256"] == predecessor["payload"]["expected_content_sha256"]
    assert predecessor["id"] in article["dependencies"]
    assert "Template:New" in bases
    # Preserve conservative live parser evidence while traversing B's approved text.
    assert ("Template:Old" in bases) is flattened_live_reference
    assert "Template:New" in prose["payload"]["dependency_bases"]
    assert "Template:Old" not in prose["payload"]["dependency_bases"]
    # Initial preflight still pins the original snapshots before any receipts exist.
    wiki.check(wiki_env.ctx, article, article["payload"], {})
    receipts = {prose["id"]: wiki.execute(wiki_env.ctx, prose, prose["payload"], {})}
    # Resume can inspect A after B's prose succeeded but before B's article ran.
    wiki.check(wiki_env.ctx, article, article["payload"], receipts)
    if generate_transcluded_article:
        receipts[predecessor["id"]] = wiki.execute(wiki_env.ctx, predecessor, predecessor["payload"], receipts)
    wiki.check(wiki_env.ctx, article, article["payload"], receipts)
    receipt = wiki.execute(wiki_env.ctx, article, article["payload"], receipts)

    assert receipt["new_revision"] == wiki_env.client.revisions["Example"]
    assert "value=new" in wiki_env.client.pages["Example"]
    assert "Reviewed prose." in wiki_env.client.pages[dependency]


def test_missing_conservative_parser_dependency_requires_explicit_selection(wiki_env: SimpleNamespace) -> None:
    wiki_env.client.put_page("Other Article", "Live text")
    original_revision = wiki_env.client.revisions["Other Article"]
    wiki_env.client.parse_overrides[("Example", None)] = MediaWikiParse(
        html="<p>Projected article</p>",
        templates=(
            MediaWikiParsedLink("Other Article", True),
            MediaWikiParsedLink("Template:Missing live dependency", False),
        ),
        categories=(),
    )

    with pytest.raises(ValueError, match="needs missing page Template:Missing live dependency"):
        wiki._dependencies(
            "Example",
            "{{:Other Article}}",
            client=wiki_env.client,
            selected={"Other Article": "Approved text with no template"},
            generated={},
            cache={},
            projection_receipts={"Other Article": "wiki_prose:Other Article"},
        )

    assert "Template:Missing live dependency" not in wiki_env.client.pages
    assert wiki_env.client.revisions["Other Article"] == original_revision


def test_native_repo_manifest_and_rollback_are_preserved(wiki_env: SimpleNamespace) -> None:
    title = "Module:Erenshor/Example"
    source = wiki_env.root / "wiki/modules/Erenshor/Example.lua"
    source.parent.mkdir(parents=True)
    source.write_text('return { value = "new" }\n', encoding="utf-8")
    wiki_env.client.put_page(title, 'return { value = "old" }')
    [operation] = prepare(wiki_env, repo_titles=[title])
    receipt = wiki.execute(wiki_env.ctx, operation, operation["payload"], {})
    manifest = read_repo_page_manifest(Path(receipt["manifest"]))
    [entry] = manifest.entries
    assert entry.ownership_class == "lua_module"
    assert entry.content_model == "Scribunto"
    assert entry.source_sha256 == operation["payload"]["manifest_entry"]["source_sha256"]
    assert entry.old_revision_id == operation["expected_base"]["initial"]["revision_id"]
    assert entry.new_revision_id == receipt["new_revision"]
    assert (wiki_env.root / entry.source_path).read_bytes() == source.read_bytes()
    assert (wiki_env.root / entry.rollback_text_source).read_text() == 'return { value = "old" }'
    wiki.reconcile(wiki_env.ctx, operation, operation["payload"], receipt, {})
    wiki_env.client.put_page(title, wiki_env.client.pages[title], user="Editor")
    with pytest.raises(ValueError, match="Completed wiki page changed"):
        wiki.reconcile(wiki_env.ctx, operation, operation["payload"], receipt, {})


def test_lost_prose_response_retains_native_preimage_and_is_uncertain(wiki_env: SimpleNamespace) -> None:
    [prose] = prepare(wiki_env, **reviewed_prose(wiki_env))
    wiki_env.client.lose_answer = True
    with pytest.raises(SurfaceUncertainError) as failure:
        wiki.execute(wiki_env.ctx, prose, prose["payload"], {})
    manifest = read_repo_page_manifest(Path(failure.value.evidence["manifest"]))
    [entry] = manifest.entries
    assert entry.old_revision_id == 1
    assert entry.new_revision_id is None
    assert entry.pending_mutation
    assert (wiki_env.root / entry.rollback_text_source).read_text() == prose["payload"]["original"]
    assert "Reviewed editor prose." in wiki_env.client.pages["Example"]


def test_dynamic_item_shards_need_explicit_selection(wiki_env: SimpleNamespace) -> None:
    index = "Module:Erenshor/Data/Items"
    shard = index + "/Armor"
    path = wiki_env.run / "lua/Armor.lua"
    path.parent.mkdir(parents=True)
    path.write_text("return { new = true }", encoding="utf-8")
    wiki_env.client.put_page(index, "return { byKey = {} }")
    wiki_env.client.put_page(shard, "return {}")
    with pytest.raises(ValueError, match="needs changed data Module:Erenshor/Data/Items/Armor"):
        wiki._dependencies(
            index,
            "return { byKey = {} }",
            client=wiki_env.client,
            selected={},
            generated={shard: path},
            cache={},
        )
    dependencies = wiki._dependencies(
        index,
        "return { byKey = {} }",
        client=wiki_env.client,
        selected={shard: path.read_text()},
        generated={shard: path},
        cache={},
    )
    assert dependencies[shard]["receipt"] == "wiki_repo:" + shard


def test_destination_account_change_invalidates_plan(wiki_env: SimpleNamespace) -> None:
    [article] = prepare(wiki_env, article_titles=["Example"])
    wiki_env.ctx.config.global_.mediawiki.bot_username = "AnotherAccount@Publisher"
    with pytest.raises(ValueError, match="destination or bot account changed"):
        wiki.check(wiki_env.ctx, article, article["payload"], {})


def test_optional_templates_require_opt_in_before_local_preparation(wiki_env: SimpleNamespace) -> None:
    with pytest.raises(ValueError, match="include_templates"):
        prepare(wiki_env, repo_titles=["Template:Item"])
    assert not wiki_env.run.exists()


def test_magic_words_are_not_mistaken_for_missing_templates(wiki_env: SimpleNamespace) -> None:
    dependencies = wiki._dependencies(
        "Example",
        "{{PAGENAME}} {{Item}}",
        client=wiki_env.client,
        selected={},
        generated={},
        cache={},
    )
    assert set(dependencies) == {"Template:Item"}


def test_native_generation_merges_projected_prose_in_isolated_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = WikiStorage(tmp_path / "run/projected")
    storage.save_fetched_by_title(
        "Example",
        ["item:example"],
        "Reviewed editor prose.\n{{Item|name=Example|stablekey=item:example|quality=Common}}",
        17,
    )
    generated = GeneratedPage(
        title="Example",
        content="{{Item|name=Example|stablekey=item:example|quality=Rare}}",
        metadata=PageMetadata(summary="Update facts"),
        stable_keys=["item:example"],
    )
    monkeypatch.setattr(
        "erenshor.application.wiki.services.generate_service.get_generators_by_name",
        lambda *_: [SimpleNamespace(generate_pages=lambda **_: [generated])],
    )
    service = WikiGenerateService(context=SimpleNamespace(storage=storage), link_catalog=())
    result = service.generate_all(page_titles=["Example"])
    assert result.failed == 0
    content = storage.read_generated_by_title("Example")
    assert "Reviewed editor prose." in content
    assert "|quality=Rare" in content
    assert storage.get_metadata_by_titles(["Example"])["Example"].fetched_revision_id == 17


def test_empty_wiki_section_prepares_no_wiki_artifacts(wiki_env: SimpleNamespace) -> None:
    assert prepare(wiki_env) == []
    assert not wiki_env.run.exists()
    assert wiki_env.generated_from == []


def test_prose_cannot_overwrite_unselected_repository_content(wiki_env: SimpleNamespace) -> None:
    source = wiki_env.root / "wiki/content/Help/Example.wiki"
    source.parent.mkdir(parents=True)
    source.write_text("Repository-owned content", encoding="utf-8")
    selection = reviewed_prose(wiki_env)
    edit_file = Path(selection["page_edits_file"])
    edit_file.write_text(edit_file.read_text().replace('title = "Example"', 'title = "Help:Example"'))
    selection["prose_review_sha256"] = hashlib.sha256(edit_file.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="Prose edits cannot target repository-owned"):
        prepare(wiki_env, **selection)

    assert wiki_env.client.revisions["Example"] == 1


def test_article_and_prose_snapshots_must_describe_the_same_initial_revision(
    wiki_env: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native_plan = wiki.plan_page_edits

    def changed_between_reads(requests: Any, client: Any) -> Any:
        client.put_page("Example", client.pages["Example"] + "\nAn editor's new paragraph.", user="Editor")
        return native_plan(requests, client)

    monkeypatch.setattr(wiki, "plan_page_edits", changed_between_reads)

    with pytest.raises(ValueError, match="changed between the article and prose snapshots"):
        prepare(wiki_env, article_titles=["Example"], **reviewed_prose(wiki_env))

    assert wiki_env.generated_from == []


def test_explicit_retry_preserves_a_native_no_write_manifest(wiki_env: SimpleNamespace) -> None:
    title = "Module:Erenshor/Example"
    source = wiki_env.root / "wiki/modules/Erenshor/Example.lua"
    source.parent.mkdir(parents=True)
    source.write_text("return { new = true }\n", encoding="utf-8")
    wiki_env.client.put_page(title, "return {}")
    wiki_env.client.put_page("Reader", "{{#invoke:Erenshor/Example|show}}")
    wiki_env.client.embedded_in[title] = ("Reader",)
    [operation] = prepare(wiki_env, repo_titles=[title])
    wiki_env.client.parse_overrides[("Reader", title)] = MediaWikiParse(
        html='<strong class="scribunto-error">script error</strong>',
        templates=(),
        categories=(),
    )

    with pytest.raises(wiki.WikiGuardError) as failure:
        wiki.execute(wiki_env.ctx, operation, operation["payload"], {})

    manifest_path = Path(failure.value.evidence["manifest"])
    [before] = read_repo_page_manifest(manifest_path).entries
    assert before.new_revision_id is None
    assert wiki_env.client.revisions[title] == operation["expected_base"]["initial"]["revision_id"]
    wiki_env.client.parse_overrides.clear()

    receipt = wiki.execute(wiki_env.ctx, operation, operation["payload"], {})

    [archived] = (manifest_path.parent / "previous").glob("*.json")
    assert read_repo_page_manifest(archived).entries[0] == before
    assert (wiki_env.root / before.rollback_text_source).read_text() == "return {}"
    assert receipt["new_revision"] == wiki_env.client.revisions[title]
    wiki.reconcile(wiki_env.ctx, operation, operation["payload"], receipt, {})


def test_configured_external_variant_run_preserves_native_relative_paths(wiki_env: SimpleNamespace) -> None:
    repo_root = wiki_env.root / "repository"
    repo_root.mkdir()
    wiki_env.ctx.repo_root = repo_root
    wiki_env.root = repo_root
    title = "Module:Erenshor/External"
    source = repo_root / "wiki/modules/Erenshor/External.lua"
    source.parent.mkdir(parents=True)
    source.write_text("return { external = true }\n", encoding="utf-8")
    wiki_env.client.put_page(title, "return {}")
    assert not wiki_env.run.is_relative_to(repo_root)
    operations = prepare(
        wiki_env,
        repo_titles=[title],
        data_titles=[wiki.DATA_LINK_TITLE],
        article_titles=["Example"],
        **reviewed_prose(wiki_env),
    )
    receipts: dict[str, dict[str, Any]] = {}

    for operation in operations:
        receipt = wiki.execute(wiki_env.ctx, operation, operation["payload"], receipts)
        receipts[operation["id"]] = receipt
        wiki.reconcile(wiki_env.ctx, operation, operation["payload"], receipt, receipts)
        manifest = read_repo_page_manifest(Path(receipt["manifest"]))
        for entry in manifest.entries:
            assert not Path(entry.source_path).is_absolute()
            resolved_source = (repo_root / entry.source_path).resolve()
            assert resolved_source.is_relative_to(wiki_env.run)
            assert resolved_source.read_text() == operation["payload"]["content"]
            if entry.rollback_text_source is not None:
                assert not Path(entry.rollback_text_source).is_absolute()
                assert (repo_root / entry.rollback_text_source).resolve().is_relative_to(wiki_env.run)

    for operation in operations:
        wiki.reconcile(wiki_env.ctx, operation, operation["payload"], receipts[operation["id"]], receipts)

    repo_operation = next(operation for operation in operations if operation["target"] == title)
    native = read_repo_page_manifest(Path(receipts[repo_operation["id"]]["manifest"]))
    rollback_repo_pages(
        manifest=native,
        repo_root=repo_root,
        client=wiki_env.client,
        summary="Restore the reviewed repository page",
        assertion="bot",
        assert_user=wiki_env.client.edit_account,
    )
    assert wiki_env.client.pages[title] == "return {}"
    with pytest.raises(ValueError, match="Completed wiki page changed"):
        wiki.reconcile(
            wiki_env.ctx,
            repo_operation,
            repo_operation["payload"],
            receipts[repo_operation["id"]],
            receipts,
        )


def test_check_many_reads_the_union_once_and_checks_every_page(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki_env.client.put_page("Other", wiki_env.client.pages["Example"].replace("Example", "Other"))
    operations = prepare(wiki_env, article_titles=["Example", "Other"])
    native_snapshots = wiki_env.client.get_page_snapshots
    batches: list[tuple[str, ...]] = []
    clients: list[Any] = []

    def snapshots(titles: Sequence[str], **kwargs: Any) -> dict[str, MediaWikiPageSnapshot]:
        batches.append(tuple(titles))
        return native_snapshots(titles, **kwargs)

    def reader(_: Any) -> SnapshotWiki:
        clients.append(wiki_env.client)
        return wiki_env.client

    monkeypatch.setattr(wiki_env.client, "get_page_snapshots", snapshots)
    monkeypatch.setattr(wiki, "create_readonly_mediawiki_client", reader)
    pairs = [(operation, operation["payload"]) for operation in operations]
    wiki.check_many(wiki_env.ctx, pairs, {})

    assert len(clients) == 1
    assert batches == [tuple(sorted({"Example", "Other", "Template:Item", wiki.DATA_LINK_TITLE}))]
    wiki_env.client.put_page("Other", wiki_env.client.pages["Other"], user="Editor")
    with pytest.raises(wiki.WikiBatchGuardError, match="Other changed after review") as error:
        wiki.check_many(wiki_env.ctx, pairs, {})
    assert error.value.operation_id == "wiki_article:Other"


def test_reconcile_many_reads_completed_pages_once_and_checks_each_receipt(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki_env.client.put_page("Other", wiki_env.client.pages["Example"].replace("Example", "Other"))
    operations = prepare(wiki_env, article_titles=["Example", "Other"])
    receipts = {}
    for operation in operations:
        receipts[operation["id"]] = wiki.execute(wiki_env.ctx, operation, operation["payload"], receipts)
    native_snapshots = wiki_env.client.get_page_snapshots
    batches: list[tuple[str, ...]] = []
    clients: list[Any] = []

    def snapshots(titles: Sequence[str], **kwargs: Any) -> dict[str, MediaWikiPageSnapshot]:
        batches.append(tuple(titles))
        return native_snapshots(titles, **kwargs)

    def reader(_: Any) -> SnapshotWiki:
        clients.append(wiki_env.client)
        return wiki_env.client

    monkeypatch.setattr(wiki_env.client, "get_page_snapshots", snapshots)
    monkeypatch.setattr(wiki, "create_readonly_mediawiki_client", reader)
    completed = [(operation, operation["payload"], receipts[operation["id"]]) for operation in operations]
    wiki.reconcile_many(wiki_env.ctx, completed, receipts)

    assert len(clients) == 1
    assert batches == [("Example", "Other")]
    wiki_env.client.put_page("Other", wiki_env.client.pages["Other"], user="Editor")
    with pytest.raises(ValueError, match="Completed wiki page changed after its receipt: Other"):
        wiki.reconcile_many(wiki_env.ctx, completed, receipts)


@pytest.mark.parametrize("kind", ["wiki_repo", "wiki_article"])
@pytest.mark.parametrize("durability_failure", [False, True])
def test_adapter_source_durability_gates_the_native_writer(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, kind: str, durability_failure: bool
) -> None:
    if kind == "wiki_repo":
        title = "Module:Erenshor/Example"
        source = wiki_env.root / "wiki/modules/Erenshor/Example.lua"
        source.parent.mkdir(parents=True)
        source.write_text("return { approved = true }\n", encoding="utf-8")
        wiki_env.client.put_page(title, "return {}\n")
        [operation] = prepare(wiki_env, repo_titles=[title])
        owner_name = "deploy_repo_pages"
    else:
        title = "Example"
        [operation] = prepare(wiki_env, article_titles=[title])
        owner_name = "deploy_articles"
    original = wiki_env.client.pages[title]
    native_durable_write = wiki.durable_write_text
    native_owner = getattr(wiki, owner_name)
    durable_sources: dict[Path, str] = {}
    owner_calls = []

    def durable_source(path: Path, text: str) -> None:
        if durability_failure:
            raise OSError("planned source durability failure")
        native_durable_write(path, text)
        durable_sources[path.resolve()] = text

    def owning_writer(*args: Any, **kwargs: Any) -> Any:
        owner_calls.append(title)
        if kind == "wiki_repo":
            planned_source = wiki_env.root / kwargs["manifest"].entries[0].source_path
        else:
            planned_source = kwargs["storage"].generated_path(title)
        assert durable_sources[planned_source.resolve()] == planned_source.read_text(encoding="utf-8")
        assert durable_sources[planned_source.resolve()] == operation["payload"]["content"]
        return native_owner(*args, **kwargs)

    monkeypatch.setattr(wiki, "durable_write_text", durable_source)
    monkeypatch.setattr(wiki, owner_name, owning_writer)
    if durability_failure:
        with pytest.raises(wiki.WikiGuardError, match="planned source durability failure"):
            wiki.execute(wiki_env.ctx, operation, operation["payload"], {})
        assert owner_calls == []
        assert wiki_env.client.pages[title] == original
        assert wiki_env.client.revisions[title] == operation["expected_base"]["initial"]["revision_id"]
    else:
        receipt = wiki.execute(wiki_env.ctx, operation, operation["payload"], {})
        assert owner_calls == [title]
        assert receipt["new_revision"] == wiki_env.client.revisions[title]
        assert wiki_env.client.pages[title] != original


@pytest.mark.parametrize("literal", ["$RUN/example", "$REPO/wiki"])
def test_frozen_literal_prose_survives_relocation_and_native_guarded_write(
    wiki_env: SimpleNamespace, literal: str
) -> None:
    from erenshor.application.publish.coordinator import _payload_paths
    from erenshor.infrastructure.wiki.content import normalize_saved_text

    selection = reviewed_prose(wiki_env)
    path = Path(selection["page_edits_file"])
    path.write_text(path.read_text().replace("Reviewed editor prose.", literal))
    selection["prose_review_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    [operation] = prepare(wiki_env, **selection)
    frozen = _payload_paths(operation["kind"], operation["payload"], wiki_env.ctx, wiki_env.run)
    reviewed = json.loads(json.dumps(frozen, sort_keys=True))
    loaded = _payload_paths(operation["kind"], reviewed, wiki_env.ctx, wiki_env.run, expand=True)
    assert loaded["content"] == operation["payload"]["content"]
    assert loaded["content"].startswith(literal)
    receipt = wiki.execute(wiki_env.ctx, operation, loaded, {})
    wiki.reconcile(wiki_env.ctx, operation, loaded, receipt, {operation["id"]: receipt})
    assert wiki_env.client.pages["Example"] == normalize_saved_text(operation["payload"]["content"])


def _canonical_snapshot_aliases(env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, aliases: dict[str, str]) -> None:
    native_snapshots = env.client.get_page_snapshots

    def snapshots(titles: Sequence[str], **kwargs: Any) -> dict[str, MediaWikiPageSnapshot]:
        canonical = native_snapshots([aliases.get(title, title) for title in titles], **kwargs)
        return {title: canonical[aliases.get(title, title)] for title in titles}

    monkeypatch.setattr(env.client, "get_page_snapshots", snapshots)


@pytest.mark.parametrize(
    ("alias", "canonical", "message"),
    [
        ("Template :Item", "Template:Item", "repository-owned or bot-owned"),
        ("Module :Erenshor/Data/Links", wiki.DATA_LINK_TITLE, "repository-owned or bot-owned"),
        ("MediaWiki :Sidebar", "MediaWiki:Sidebar", "dedicated deployment path"),
    ],
)
def test_prose_alias_cannot_bypass_canonical_page_ownership(
    wiki_env: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    alias: str,
    canonical: str,
    message: str,
) -> None:
    source = wiki_env.root / "wiki/templates/Item.wiki"
    source.parent.mkdir(parents=True)
    source.write_text("Parameter-only template", encoding="utf-8")
    if canonical == "MediaWiki:Sidebar":
        wiki_env.client.put_page(canonical, "Interface registration")
    original = wiki_env.client.pages[canonical]
    original_revision = wiki_env.client.revisions[canonical]
    _canonical_snapshot_aliases(wiki_env, monkeypatch, {alias: canonical})
    path = wiki_env.wiki_dir / "reviewed-edits.toml"
    path.write_text(
        f'[[pages]]\ntitle = {json.dumps(alias)}\nsummary = "Reviewed edit"\n'
        f'[[pages.replace]]\nold = {json.dumps(original)}\nnew = "Changed protected text"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        prepare(wiki_env, page_edits_file=str(path), prose_review_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    assert wiki_env.client.pages[canonical] == original
    assert wiki_env.client.revisions[canonical] == original_revision


def test_prose_duplicate_aliases_are_rejected_by_canonical_identity(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = "Help:Manual"
    alias = "Help :Manual"
    wiki_env.client.put_page(canonical, "Manual prose")
    original_revision = wiki_env.client.revisions[canonical]
    _canonical_snapshot_aliases(wiki_env, monkeypatch, {alias: canonical})
    path = wiki_env.wiki_dir / "reviewed-edits.toml"
    path.write_text(
        "".join(
            f'[[pages]]\ntitle = {json.dumps(title)}\nsummary = "Reviewed edit"\n'
            '[[pages.replace]]\nold = "Manual prose"\nnew = "Approved manual prose"\n'
            for title in (canonical, alias)
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="same wiki page more than once"):
        prepare(wiki_env, page_edits_file=str(path), prose_review_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    assert wiki_env.client.revisions[canonical] == original_revision


@pytest.mark.parametrize("use_alias", [False, True])
def test_only_the_canonical_manual_page_title_is_accepted(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, use_alias: bool
) -> None:
    canonical = "Help:Manual"
    alias = "Help :Manual"
    wiki_env.client.put_page(canonical, "Manual prose")
    original_revision = wiki_env.client.revisions[canonical]
    _canonical_snapshot_aliases(wiki_env, monkeypatch, {alias: canonical})
    path = wiki_env.wiki_dir / "reviewed-edits.toml"
    path.write_text(
        f'[[pages]]\ntitle = {json.dumps(alias if use_alias else canonical)}\nsummary = "Reviewed edit"\n'
        '[[pages.replace]]\nold = "Manual prose"\nnew = "Approved manual prose"\n',
        encoding="utf-8",
    )
    selection = {"page_edits_file": str(path), "prose_review_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    if use_alias:
        with pytest.raises(ValueError, match=r"not canonical\. Use 'Help:Manual'"):
            prepare(wiki_env, **selection)
    else:
        [prose] = prepare(wiki_env, **selection)
        assert prose["target"] == canonical
        assert prose["id"] == "wiki_prose:" + canonical
        assert prose["payload"]["content"] == "Approved manual prose"
    assert wiki_env.client.revisions[canonical] == original_revision


def test_distinct_canonical_manual_title_case_is_not_duplicate_ownership(wiki_env: SimpleNamespace) -> None:
    titles = ("Case Page", "Case page")
    blocks = []
    for title in titles:
        wiki_env.client.put_page(title, "People's prose.\n")
        blocks.append(
            f'[[pages]]\ntitle = {json.dumps(title)}\nsummary = "Update isolated case fixture"\n'
            f'[[pages.replace]]\nold = "People\'s prose."\nnew = {json.dumps("Changed " + title)}\n'
        )
    path = wiki_env.wiki_dir / "case-sensitive-edits.toml"
    path.write_text("\n".join(blocks), encoding="utf-8")
    operations = prepare(
        wiki_env, page_edits_file=str(path), prose_review_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    assert {operation["target"] for operation in operations} == set(titles)
    for operation in operations:
        receipt = wiki.execute(wiki_env.ctx, operation, operation["payload"], {})
        wiki.reconcile(wiki_env.ctx, operation, operation["payload"], receipt, {operation["id"]: receipt})


def test_case_distinct_editor_template_does_not_alias_maintained_source(wiki_env: SimpleNamespace) -> None:
    source = wiki_env.root / "wiki/templates/Example.wiki"
    source.parent.mkdir(parents=True)
    source.write_text("Maintained template", encoding="utf-8")
    wiki_env.client.put_page("Template:EXAMPLE", "People's prose.\n")
    path = wiki_env.wiki_dir / "case-distinct-owner.toml"
    path.write_text(
        '[[pages]]\ntitle = "Template:EXAMPLE"\nsummary = "Update editor-owned case fixture"\n'
        '[[pages.replace]]\nold = "People\\u0027s prose."\nnew = "Changed editor prose."\n',
        encoding="utf-8",
    )
    [operation] = prepare(
        wiki_env, page_edits_file=str(path), prose_review_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    assert operation["target"] == "Template:EXAMPLE"
    assert source.read_text() == "Maintained template"


def test_acknowledged_wiki_mismatch_is_failed_with_actual_parent_recovery(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    from erenshor.infrastructure.wiki import MediaWikiEditVerificationError

    [operation] = prepare(wiki_env, **reviewed_prose(wiki_env))
    assert operation["payload"]["guard"] == "checked-revision-and-exact-saved-source"
    edit = wiki_env.client.safe_edit_page

    def merged_write(title: str, content: str, **kwargs: Any) -> int:
        wiki_env.client.put_page(title, operation["payload"]["original"] + "\nEditor paragraph.", user="Editor")
        parent = wiki_env.client.get_page_snapshots([title])[title]
        revision_id = edit(title, content + "\nEditor paragraph.", parent.revision)
        written = wiki_env.client.get_revision_snapshots([revision_id])[revision_id]
        raise MediaWikiEditVerificationError(
            "Saved revision has an unapproved parent",
            new_revision_id=revision_id,
            written_snapshot=written,
            actual_parent_snapshot=parent,
        )

    monkeypatch.setattr(wiki_env.client, "safe_edit_page", merged_write)
    with pytest.raises(wiki.WikiWriteError) as failure:
        wiki.execute(wiki_env.ctx, operation, operation["payload"], {})
    assert not failure.value.evidence["safe_to_resume"]
    manifest = read_repo_page_manifest(Path(failure.value.evidence["manifest"]))
    [entry] = manifest.entries
    assert entry.new_revision_id == wiki_env.client.revisions[operation["target"]]
    assert entry.requires_rollback
    assert not entry.pending_mutation
    assert (wiki_env.root / entry.rollback_text_source).read_text() == (
        operation["payload"]["original"] + "\nEditor paragraph."
    )
    assert "Editor paragraph." in wiki_env.client.pages[operation["target"]]


def test_explicit_native_wiki_rejection_remains_safe_to_resume(
    wiki_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    from erenshor.infrastructure.wiki import MediaWikiPermissionError

    [operation] = prepare(wiki_env, **reviewed_prose(wiki_env))
    before = dict(wiki_env.client.revisions)

    def reject(*args: Any, **kwargs: Any) -> int:
        raise MediaWikiPermissionError("Provider rejected the write")

    monkeypatch.setattr(wiki_env.client, "safe_edit_page", reject)
    with pytest.raises(wiki.WikiGuardError) as failure:
        wiki.execute(wiki_env.ctx, operation, operation["payload"], {})
    assert failure.value.evidence["safe_to_resume"]
    manifest = read_repo_page_manifest(Path(failure.value.evidence["manifest"]))
    assert all(entry.new_revision_id is None and not entry.pending_mutation for entry in manifest.entries)
    assert wiki_env.client.revisions == before
