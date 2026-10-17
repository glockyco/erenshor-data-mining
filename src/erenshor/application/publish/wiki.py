"""Prepare exact wiki pages and execute them through their native guarded owners."""

from __future__ import annotations

import difflib
import hashlib
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from os.path import relpath
from pathlib import Path
from typing import TYPE_CHECKING, Any

from erenshor.application.extract.database_comparison import recorded_build_id
from erenshor.application.publish.models import SurfaceUncertainError, WikiSelection
from erenshor.application.wiki.lifecycle import load_content_lifecycle
from erenshor.application.wiki.semantic_validation import validate_wiki_pages
from erenshor.application.wiki.services.generate_service import WikiGenerateService
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_deploy.article_report import build_article_report
from erenshor.application.wiki_deploy.articles import (
    deploy_articles,
    parse_problems,
    plan_article_deploy,
)
from erenshor.application.wiki_deploy.dependencies import literal_dependencies, transcluded_titles
from erenshor.application.wiki_deploy.guarded_edits import GuardedPageEdit, apply_guarded_edits
from erenshor.application.wiki_deploy.link_audit import LinkTargets
from erenshor.application.wiki_deploy.link_audit_service import (
    DATA_LINK_TITLE,
    LinkAuditService,
    extract_catalog_sha256,
)
from erenshor.application.wiki_deploy.manifest import (
    RepoWikiPageManifest,
    RepoWikiPageManifestEntry,
    build_repo_page_manifest,
    durable_write_text,
    read_repo_page_manifest,
    select_repo_page_manifest,
    stage_rank,
    write_repo_page_manifest,
)
from erenshor.application.wiki_deploy.page_edits import parse_page_edit_requests, plan_page_edits
from erenshor.application.wiki_deploy.pages import (
    RepoPageDriftError,
    build_deployed_manifest,
    deploy_repo_pages,
    find_drift,
    prepare_repo_page_checks,
    read_repo_page_sources,
    render_repo_page_checks,
    repo_page_action,
)
from erenshor.application.wiki_lua.generation import generate_lua_data_modules
from erenshor.application.wiki_lua.link_catalog import build_links_data
from erenshor.cli.mediawiki import create_readonly_mediawiki_client
from erenshor.infrastructure.database.repositories.build_metadata import BuildMetadataRepository
from erenshor.infrastructure.database.repositories.treasure import TreasureRepository
from erenshor.infrastructure.wiki.content import normalize_saved_text

if TYPE_CHECKING:
    from erenshor.application.wiki.services.generate_service import GeneratedCorpus
    from erenshor.application.wiki_deploy.page_edits import PageEditRequest
    from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
    from erenshor.cli.context import CLIContext
    from erenshor.infrastructure.wiki import MediaWikiPageSnapshot


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class WikiGuardError(ValueError):
    """A known refusal before a page write, with native recovery evidence."""

    def __init__(self, message: str, manifest: Path) -> None:
        super().__init__(message)
        self.evidence = {"safe_to_resume": True, "manifest": str(manifest)}


class WikiWriteError(ValueError):
    """An acknowledged write needs native recovery before another continuation."""

    def __init__(self, message: str, manifest: Path, entries: Sequence[RepoWikiPageManifestEntry]) -> None:
        super().__init__(message)
        self.evidence = {
            "safe_to_resume": False,
            "manifest": str(manifest),
            "entries": [asdict(entry) for entry in entries],
        }


class WikiBatchGuardError(ValueError):
    """A batched preflight refusal attributed to its exact operation."""

    def __init__(self, message: str, operation_id: str) -> None:
        super().__init__(message)
        self.operation_id = operation_id


def _id(kind: str, title: str) -> str:
    return f"{kind}:{title}"


def _destination(ctx: CLIContext) -> dict[str, str]:
    config = ctx.config.global_.mediawiki
    account = config.bot_username.strip().partition("@")[0]
    if not config.api_url or not account:
        raise ValueError("Wiki publishing requires an endpoint and an explicit bot account")
    return {"api_url": config.api_url, "account": account, "assertion": "bot"}


def _base(snapshot: MediaWikiPageSnapshot) -> dict[str, Any]:
    if snapshot.source_text is not None and snapshot.revision is None:
        raise ValueError(f"{snapshot.title} has text without revision metadata")
    return {
        "revision_id": snapshot.revision.revision_id if snapshot.revision else None,
        "content_sha256": _sha(snapshot.source_text) if snapshot.source_text is not None else None,
        "content_model": snapshot.content_model,
    }


def _snapshots(client: Any, titles: Sequence[str]) -> dict[str, MediaWikiPageSnapshot]:
    if not titles:
        return {}
    snapshots: dict[str, MediaWikiPageSnapshot] = client.get_page_snapshots(sorted(set(titles)))
    missing = set(titles) - snapshots.keys()
    if missing:
        raise ValueError(f"Missing wiki snapshots: {', '.join(sorted(missing))}")
    for snapshot in snapshots.values():
        _base(snapshot)
    return snapshots


def _composition(ctx: CLIContext, storage: WikiStorage) -> Any:
    # The standalone commands own repository construction and variant configuration.
    from erenshor.cli.commands.wiki import _create_wiki_composition

    return _create_wiki_composition(ctx, with_client=False, storage=storage)


def _generate_lua(ctx: CLIContext, storage: WikiStorage, output: Path) -> dict[str, Path]:
    with _composition(ctx, storage) as composition:
        context = composition.context
        result = generate_lua_data_modules(
            item_repo=context.item_repo,
            character_repo=context.character_repo,
            spell_repo=context.spell_repo,
            skill_repo=context.skill_repo,
            stance_repo=context.stance_repo,
            quest_repo=context.quest_repo,
            zone_repo=context.zone_repo,
            faction_repo=context.faction_repo,
            class_display=context.class_display,
            build_repo=BuildMetadataRepository(composition.database),
            treasure_repo=TreasureRepository(composition.database),
            output_root=output,
            max_page_bytes=ctx.config.global_.mediawiki.max_page_bytes,
        )
    return {"Module:" + path.relative_to(output).with_suffix("").as_posix(): path for path in result.written_paths}


def _generate_articles(
    ctx: CLIContext, storage: WikiStorage, titles: Sequence[str]
) -> tuple[tuple[LinkCatalogEntry, ...], list[str]]:
    with _composition(ctx, storage) as composition:
        catalog = tuple(composition.context.link_catalog_entries())
        if not titles:
            return catalog, []

        def validate(corpus: GeneratedCorpus) -> None:
            if set(corpus.pages) != set(titles):
                raise ValueError(f"Selected articles are not generated: {sorted(set(titles) - corpus.pages.keys())}")
            report = validate_wiki_pages(
                corpus.pages,
                expectations=corpus.expectations,
                catalog_entries=catalog,
                planned_titles=tuple(titles),
                known_generated_titles=tuple(titles),
                variant=ctx.variant,
            )
            if report.has_errors:
                raise ValueError(f"Wiki generation validation failed: {report.findings}")

        service = WikiGenerateService(
            context=composition.context,
            link_catalog=catalog,
            lifecycle=load_content_lifecycle(ctx.repo_root / "content-lifecycle.json"),
        )
        result = service.generate_all(page_titles=list(titles), validate=validate)
        if result.failed or set(storage.list_generated_titles()) != set(titles):
            raise ValueError(f"Selected wiki articles could not be generated: {result.errors}")
        return catalog, list(result.warnings)


class _ProjectedReader:
    """Read-only projection for the native semantic audit, never a mutation client."""

    def __init__(self, client: Any, pages: Mapping[str, str]) -> None:
        self.client = client
        self.pages = pages

    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)

    def get_page(self, title: str) -> str | None:
        source: str | None = self.pages[title] if title in self.pages else self.client.get_page(title)
        return source

    def get_pages(self, titles: Sequence[str]) -> dict[str, str | None]:
        live: dict[str, str | None] = self.client.get_pages([title for title in titles if title not in self.pages])
        return {title: self.pages[title] if title in self.pages else live[title] for title in titles}

    def get_title_statuses(self, titles: Sequence[str]) -> dict[str, Any]:
        from erenshor.infrastructure.wiki.client import MediaWikiTitleStatus

        live: dict[str, Any] = self.client.get_title_statuses(titles)
        for title in titles:
            if title in self.pages:
                live[title] = MediaWikiTitleStatus(title, title, None, True)
        return live


def _audit(
    ctx: CLIContext, client: Any, catalog: Sequence[LinkCatalogEntry], pages: Mapping[str, str], planned: Sequence[str]
) -> dict[str, Any]:
    report = LinkAuditService(catalog, client=client).audit(
        generated_pages=pages,
        planned_titles=planned,
        known_generated_titles=planned,
        variant=ctx.variant,
        online=True,
        include_live_pages=False,
    )
    if report.has_errors:
        raise ValueError(f"Wiki semantic audit failed: {report.findings}")
    return report.to_dict()


def _direct_dependencies(
    title: str,
    text: str,
    generated: Mapping[str, Path],
    client: Any,
    selected: Mapping[str, str],
    snapshots: dict[str, MediaWikiPageSnapshot],
) -> set[str]:
    dependencies = set(literal_dependencies(title, text))
    if not title.startswith("Module:"):
        candidates = {dep for dep in transcluded_titles(text) if dep.startswith("Template:")}
        snapshots.update(_snapshots(client, sorted(candidates - snapshots.keys())))
        dependencies.update(dep for dep in candidates if dep in selected or snapshots[dep].source_text is not None)
        # Parsing distinguishes real missing templates from magic words such as PAGENAME.
        dependencies.update(reference.title for reference in client.parse_wikitext(title, text).templates)
    if title == "Module:Erenshor/Data/Items":
        # The index's values name shards dynamically, outside literal loadData calls.
        dependencies.update(name for name in generated if name.startswith(title + "/"))
    dependencies.discard(title)
    return dependencies


def _dependencies(
    title: str,
    text: str,
    *,
    client: Any,
    selected: Mapping[str, str],
    generated: Mapping[str, Path],
    cache: dict[str, MediaWikiPageSnapshot],
    catalog: bool = False,
    edges: dict[tuple[str, str], set[str]] | None = None,
    projection_receipts: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    dependency_edges = edges if edges is not None else {}

    def direct(page: str, source: str) -> set[str]:
        key = (page, _sha(source))
        if key not in dependency_edges:
            dependency_edges[key] = _direct_dependencies(page, source, generated, client, selected, cache)
        return dependency_edges[key]

    pending = set(direct(title, text))
    if catalog:
        pending.add(DATA_LINK_TITLE)
    seen = {title}
    result: dict[str, dict[str, Any]] = {}
    while pending:
        batch = sorted(pending - seen)
        if not batch:
            break
        cache.update(_snapshots(client, [name for name in batch if name not in cache]))
        pending = set()
        for dependency in batch:
            seen.add(dependency)
            snapshot = cache[dependency]
            if dependency in selected:
                source = selected[dependency]
                result[dependency] = {
                    "initial": _base(snapshot),
                    "receipt": (projection_receipts or {}).get(dependency, _id("wiki_repo", dependency)),
                    "content_sha256": _sha(normalize_saved_text(source)),
                }
            else:
                live_source = snapshot.source_text
                if live_source is None:
                    raise ValueError(f"{title} needs missing page {dependency}. Select its owner explicitly")
                source = live_source
                if dependency in generated:
                    required = generated[dependency].read_text(encoding="utf-8")
                    if normalize_saved_text(source) != normalize_saved_text(required):
                        raise ValueError(f"{title} needs changed data {dependency}. Add it to data_titles explicitly")
                result[dependency] = {"initial": _base(snapshot)}
            pending.update(direct(dependency, source) - seen)
    return result


def _render_review(client: Any, title: str, original: str, content: str, provisional: bool) -> dict[str, Any]:
    live = client.parse_wikitext(title, original)
    parsed = client.parse_wikitext(title, content)
    problems = parse_problems(parsed, frozenset(category.title for category in live.categories))
    if problems and not provisional:
        raise ValueError(f"{title} fails wiki render checks: {problems}")
    return {"provisional": provisional, "problems": list(problems), "direct_prewrite_required": True}


def _inputs(ctx: CLIContext) -> list[str]:
    variant = ctx.config.variants[ctx.variant]
    paths = [
        variant.resolved_database(ctx.repo_root),
        ctx.repo_root / "content-lifecycle.json",
        ctx.repo_root / "src/erenshor/application/wiki",
        ctx.repo_root / "src/erenshor/application/wiki_lua",
        ctx.repo_root / "src/erenshor/application/wiki_deploy",
        ctx.repo_root / "src/erenshor/infrastructure/database",
        ctx.repo_root / "src/erenshor/domain",
        ctx.repo_root / "src/erenshor/cli/commands/wiki.py",
        ctx.repo_root / "wiki/modules",
        ctx.repo_root / "wiki/templates",
        ctx.repo_root / "wiki/content",
        variant.maps.resolved_source_dir(ctx.repo_root) / "src/lib/data/zone-positions.json",
    ]
    return [str(path.resolve()) for path in paths if path.exists()]


def _operation(
    ctx: CLIContext,
    kind: str,
    title: str,
    snapshot: MediaWikiPageSnapshot,
    content: str,
    payload: dict[str, Any],
    dependencies: Mapping[str, dict[str, Any]],
    inputs: Sequence[str],
    *,
    predecessor: str | None = None,
) -> dict[str, Any]:
    original = payload["original"]
    payload.update(
        content=content,
        dependency_bases=dict(dependencies),
        guard="checked-revision-and-exact-saved-source",
        diff="\n".join(
            difflib.unified_diff(original.splitlines(), content.splitlines(), "base", "prepared", lineterm="")
        ),
        expected_content_sha256=_sha(
            normalize_saved_text(original if payload.get("action") == "unchanged" else content)
        ),
        limitations=[
            "MediaWiki may merge a concurrent edit. Preflight and saved revision/parent/source checks detect "
            "but cannot atomically prevent that race. A mismatch retains the actual write and editor-parent "
            "preimage and stops downstream operations without automatic rollback.",
            "Rollback leaves newly created pages in place. Delete them manually if appropriate.",
        ],
    )
    ids = {base["receipt"] for base in dependencies.values() if "receipt" in base}
    expected: dict[str, Any] = {"initial": _base(snapshot)}
    if predecessor:
        ids.add(predecessor)
        expected.update(receipt=predecessor, content_sha256=_sha(normalize_saved_text(original)))
    return {
        "id": _id(kind, title),
        "kind": kind,
        "target": title,
        "dependencies": sorted(ids),
        "payload": payload,
        "expected_base": expected,
        "recovery": (
            "uv run erenshor wiki rollback-repo-pages --manifest <receipt.manifest>. New pages require manual deletion."
        ),
        "inputs": sorted(set(inputs)),
        "destination": _destination(ctx),
    }


def prepare(ctx: CLIContext, selection: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    """Capture selected pages, project reviewed prose, and generate in isolated storage."""
    summary = selection.get("summary", "").strip()
    if not summary:
        raise ValueError("Wiki publishing requires an explicit summary")
    chosen = WikiSelection.model_validate({key: value for key, value in selection.items() if key != "summary"})
    if not (chosen.article_titles or chosen.repo_titles or chosen.data_titles or chosen.page_edits_file):
        return []
    destination = _destination(ctx)
    prose_file: Path | None = None
    requests: tuple[PageEditRequest, ...] = ()
    if chosen.page_edits_file:
        prose_file = Path(chosen.page_edits_file).resolve()
        wiki_dir = ctx.config.variants[ctx.variant].resolved_wiki(ctx.repo_root).resolve()
        if not prose_file.is_relative_to(wiki_dir):
            raise ValueError("Reviewed prose edits must stay in the selected variant's wiki directory")
        captured_prose = prose_file.read_bytes()
        if hashlib.sha256(captured_prose).hexdigest() != chosen.prose_review_sha256:
            raise ValueError("The prose edit file does not match its separate review digest")
        requests = parse_page_edit_requests(captured_prose, source=str(prose_file))
    workspace = run_dir / "wiki"
    storage = WikiStorage(workspace / "projected")
    generated = _generate_lua(ctx, storage, workspace / "lua")
    missing_data = set(chosen.data_titles) - generated.keys()
    if missing_data:
        raise ValueError(f"Unknown selected generated data pages: {sorted(missing_data)}")
    requested = set(chosen.repo_titles)
    maintained = build_repo_page_manifest(
        ctx.repo_root,
        variant=ctx.variant,
        include_templates=True,
        include_content_pages=True,
    )
    manifest = select_repo_page_manifest(
        maintained,
        requested_titles=requested,
        include_templates=chosen.include_templates,
        include_content_pages=chosen.include_content_pages,
    )
    if requested - {entry.title for entry in manifest.entries}:
        raise ValueError(
            f"Unknown selected repository pages: {sorted(requested - {e.title for e in manifest.entries})}"
        )
    data_entries = tuple(
        RepoWikiPageManifestEntry(
            title=title,
            source_path=str(generated[title].resolve()),
            source_sha256=hashlib.sha256(generated[title].read_bytes()).hexdigest(),
            ownership_class="generated_data",
            upload_stage="generated_data",
            content_model="Scribunto",
        )
        for title in chosen.data_titles
    )
    manifest = RepoWikiPageManifest(entries=data_entries + manifest.entries)
    sources = read_repo_page_sources(manifest, ctx.repo_root)
    reader = create_readonly_mediawiki_client(ctx)
    try:
        cache = _snapshots(reader, list(sources) + chosen.article_titles + [request.title for request in requests])
        for entry in manifest.entries:
            model = cache[entry.title].content_model
            if model is not None and model != entry.content_model:
                raise ValueError(f"{entry.title} has content model {model}, not {entry.content_model}")
        drift = find_drift(
            manifest.entries, sources, cache, deploy_account=destination["account"], accepted=chosen.accept_drift
        )
        if drift:
            raise RepoPageDriftError(drift)
        live_dependencies: dict[str, str | None] = {}
        manifest = prepare_repo_page_checks(manifest, sources, cache, reader, live_dependencies)
        canonical_prose_titles = [cache[request.title].title for request in requests]
        if any(title.partition(":")[0].casefold() == "mediawiki" for title in canonical_prose_titles):
            raise ValueError("Interface pages require their dedicated deployment path, not prose publishing")
        prose_titles = canonical_prose_titles
        if len(prose_titles) != len(set(prose_titles)):
            raise ValueError("The prose edit file names the same wiki page more than once")
        owned = {entry.title for entry in maintained.entries} | set(generated)
        if set(prose_titles) & owned:
            raise ValueError("Prose edits cannot target repository-owned or bot-owned pages")
        for request, canonical_title in zip(requests, canonical_prose_titles, strict=True):
            if request.title != canonical_title:
                raise ValueError(f"Prose edit title {request.title!r} is not canonical. Use {canonical_title!r}")
        prose = plan_page_edits(requests, reader)
        projections = {edit.title: edit for edit in prose}
        for title in chosen.article_titles:
            snapshot = cache[title]
            edit = projections.get(title)
            if edit is not None and (
                snapshot.revision is None
                or snapshot.revision.revision_id != edit.revision.revision_id
                or snapshot.source_text != edit.original
            ):
                raise ValueError(f"{title} changed between the article and prose snapshots")
            if snapshot.revision is not None:
                storage.save_fetched_by_title(
                    title,
                    [],
                    projections[title].content if title in projections else snapshot.source_text or "",
                    snapshot.revision.revision_id,
                )
        catalog, warnings = _generate_articles(ctx, storage, chosen.article_titles)
        catalog_sha = str(build_links_data(catalog)["catalogSha256"])
        rendered: list[dict[str, Any]] = []
        if chosen.render_check:
            render_repo_page_checks(
                manifest,
                sources,
                cache,
                reader,
                catalog={entry.key.casefold(): entry for entry in catalog},
                dry_run=True,
                live_dependencies=live_dependencies,
                report=lambda result: rendered.append(asdict(result)),
            )
        operations: list[dict[str, Any]] = []
        edges: dict[tuple[str, str], set[str]] = {}
        common_inputs = _inputs(ctx) + [str(path.resolve()) for path in generated.values()]
        for entry in manifest.entries:
            deps = _dependencies(
                entry.title,
                sources[entry.title],
                client=reader,
                selected=sources,
                generated=generated,
                cache=cache,
                edges=edges,
            )
            inputs = [*common_inputs, str((ctx.repo_root / entry.source_path).resolve())]
            operation = _operation(
                ctx,
                "wiki_repo",
                entry.title,
                cache[entry.title],
                sources[entry.title],
                {
                    "original": cache[entry.title].source_text or "",
                    "summary": summary,
                    "manifest_entry": asdict(entry),
                    "render_check": chosen.render_check,
                    "render": [result for result in rendered if result.get("title") == entry.title],
                    "accept_drift": entry.title in chosen.accept_drift,
                    "include_templates": chosen.include_templates,
                    "include_content_pages": chosen.include_content_pages,
                    "action": repo_page_action(cache[entry.title], sources[entry.title]),
                },
                deps,
                inputs,
            )
            operation["dependencies"] = sorted(
                set(operation["dependencies"])
                | {
                    _id("wiki_repo", earlier.title)
                    for earlier in manifest.entries
                    if stage_rank(earlier.upload_stage) < stage_rank(entry.upload_stage)
                }
            )
            operations.append(operation)
        prose_sources = {**sources, **{title: edit.content for title, edit in projections.items()}}
        prose_receipts = {
            **{title: _id("wiki_repo", title) for title in sources},
            **{title: _id("wiki_prose", title) for title in projections},
        }
        for edit in sorted(prose, key=lambda edit: (edit.title.casefold(), edit.title)):
            snapshot = _snapshots(reader, [edit.title])[edit.title]
            if (
                snapshot.revision is None
                or snapshot.revision.revision_id != edit.revision.revision_id
                or snapshot.source_text != edit.original
            ):
                raise ValueError(f"{edit.title} changed while prose was prepared")
            deps = _dependencies(
                edit.title,
                edit.content,
                client=reader,
                selected=prose_sources,
                generated=generated,
                cache=cache,
                edges=edges,
                projection_receipts=prose_receipts,
            )
            provisional = any("receipt" in base for base in deps.values())
            render = _render_review(reader, edit.title, edit.original, edit.content, provisional)
            operations.append(
                _operation(
                    ctx,
                    "wiki_prose",
                    edit.title,
                    snapshot,
                    edit.content,
                    {
                        "original": edit.original,
                        "summary": edit.summary,
                        "render": render,
                        "prose_review_sha256": chosen.prose_review_sha256,
                        "page_edits_file": str(prose_file),
                    },
                    deps,
                    [*common_inputs, str(prose_file)],
                )
            )
        article_plan = plan_article_deploy(storage, page_titles=chosen.article_titles)
        if article_plan.stale:
            raise ValueError(f"Article preparation has unguarded bases: {article_plan.stale}")
        projected_pages = {article.title: article.generated_text for article in article_plan.articles}
        audit = (
            _audit(
                ctx,
                _ProjectedReader(reader, {**prose_sources, **projected_pages}),
                catalog,
                projected_pages,
                chosen.article_titles,
            )
            if projected_pages
            else {}
        )
        review = build_article_report(
            article_plan,
            storage,
            {title: _base(cache[title])["revision_id"] for title in chosen.article_titles},
            LinkTargets(catalog),
        ).to_json()
        article_summary = summary
        if article_plan.articles:
            database = ctx.config.variants[ctx.variant].resolved_database(ctx.repo_root)
            article_summary = f"{summary} (game build {recorded_build_id(database)})"
        article_sources = {
            **prose_sources,
            **{
                article.title: (
                    (storage.read_fetched_by_title(article.title) or "")
                    if article.action == "unchanged"
                    else article.generated_text
                )
                for article in article_plan.articles
            },
        }
        article_receipts = {
            **prose_receipts,
            **{title: _id("wiki_article", title) for title in projected_pages},
        }
        for article in article_plan.articles:
            title = article.title
            deps = _dependencies(
                title,
                article.generated_text,
                client=reader,
                selected=article_sources,
                generated=generated,
                cache=cache,
                catalog=True,
                edges=edges,
                projection_receipts=article_receipts,
            )
            for dependency, base in deps.items():
                if dependency in projections and dependency in projected_pages:
                    base["prior"] = {
                        "initial": base["initial"],
                        "receipt": _id("wiki_prose", dependency),
                        "content_sha256": _sha(normalize_saved_text(projections[dependency].content)),
                    }
            catalog_source = sources.get(DATA_LINK_TITLE, cache[DATA_LINK_TITLE].source_text)
            if extract_catalog_sha256(catalog_source) != catalog_sha:
                raise ValueError(f"{title} needs changed {DATA_LINK_TITLE}. Add it to data_titles explicitly")
            original = storage.read_fetched_by_title(title) or ""
            provisional = any("receipt" in base for base in deps.values())
            render = _render_review(reader, title, original, article.generated_text, provisional)
            operations.append(
                _operation(
                    ctx,
                    "wiki_article",
                    title,
                    cache[title],
                    article.generated_text,
                    {
                        "original": original,
                        "summary": article_summary,
                        "action": article.action,
                        "catalog_sha256": catalog_sha,
                        "audit": audit,
                        "planned_article_titles": chosen.article_titles,
                        "render": render,
                        "review": review,
                        "generation_warnings": warnings,
                        "kept_roots": storage.get_metadata_by_titles([title])[title].kept_roots,
                        "stable_keys": storage.get_metadata_by_titles([title])[title].stable_keys,
                    },
                    deps,
                    common_inputs,
                    predecessor=_id("wiki_prose", title) if title in projections else None,
                )
            )
        for operation in operations:
            native_root = workspace / "deploys" / hashlib.sha256(operation["id"].encode()).hexdigest()
            operation["payload"]["native_manifest"] = str(native_root / "manifest.json")
            operation["payload"]["local_outputs"] = [
                str(native_root / "manifest.json"),
                str(native_root / "attempts"),
                str(native_root / "previous"),
            ]
            operation["payload"]["preparation_outputs"] = [str(workspace / "lua"), str(workspace / "projected")]
            if prose_file is not None and str(prose_file) in operation["inputs"]:
                # Keep the separate approval authoritative when the coordinator pins inputs.
                operation["input_sha256"] = {str(prose_file): chosen.prose_review_sha256}
        if prose_file is not None and hashlib.sha256(prose_file.read_bytes()).hexdigest() != chosen.prose_review_sha256:
            raise ValueError("The prose edit file changed during preparation after its separate review")
        return operations
    finally:
        reader.close()


def _expected(base: Mapping[str, Any], receipts: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    predecessor = base.get("receipt")
    if predecessor is None or predecessor not in receipts:
        if "prior" in base:
            return _expected(base["prior"], receipts)
        return dict(base["initial"])
    receipt = receipts[predecessor]
    if receipt.get("content_sha256") != base["content_sha256"]:
        raise ValueError(f"Predecessor content does not match the approved projection: {predecessor}")
    return {
        "revision_id": receipt["new_revision"],
        "content_sha256": base["content_sha256"],
        "content_model": receipt.get("content_model"),
    }


def _assert_base(title: str, snapshot: MediaWikiPageSnapshot, expected: Mapping[str, Any]) -> None:
    actual = _base(snapshot)
    # Saved text is normalized by MediaWiki after edits, but fixed preimages stay byte exact.
    if actual != expected:
        raise ValueError(f"{title} changed after review: expected {expected}, found {actual}")


def _check_with_client(
    operation: dict[str, Any],
    payload: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    client: Any,
    *,
    snapshots: Mapping[str, MediaWikiPageSnapshot] | None = None,
) -> Mapping[str, MediaWikiPageSnapshot]:
    titles = [operation["target"], *payload["dependency_bases"]]
    snapshots = _snapshots(client, titles) if snapshots is None else snapshots
    _assert_base(operation["target"], snapshots[operation["target"]], _expected(operation["expected_base"], receipts))
    for title, base in payload["dependency_bases"].items():
        _assert_base(title, snapshots[title], _expected(base, receipts))
    return snapshots


def check(
    ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> None:
    """Reject changed destinations, fixed revisions, and receipt-bound dependency states."""
    if operation["destination"] != _destination(ctx):
        raise ValueError("Wiki destination or bot account changed after review")
    reader = create_readonly_mediawiki_client(ctx)
    try:
        _check_with_client(operation, payload, receipts, reader)
    finally:
        reader.close()


def check_many(
    ctx: CLIContext,
    operations: list[tuple[dict[str, Any], dict[str, Any]]],
    receipts: dict[str, dict[str, Any]],
) -> None:
    """Check selected targets and dependencies with one shared snapshot read."""
    if not operations:
        return
    destination = _destination(ctx)
    for operation, _ in operations:
        if operation["destination"] != destination:
            raise WikiBatchGuardError("Wiki destination or bot account changed after review", operation["id"])
    titles = sorted(
        {title for operation, payload in operations for title in (operation["target"], *payload["dependency_bases"])}
    )
    reader = create_readonly_mediawiki_client(ctx)
    try:
        snapshots = _snapshots(reader, titles)
        for operation, payload in operations:
            try:
                _check_with_client(operation, payload, receipts, reader, snapshots=snapshots)
            except ValueError as error:
                raise WikiBatchGuardError(str(error), operation["id"]) from error
    finally:
        reader.close()


def _regenerate(
    ctx: CLIContext, title: str, snapshot: MediaWikiPageSnapshot, payload: dict[str, Any], root: Path
) -> None:
    if snapshot.revision is None or snapshot.source_text != normalize_saved_text(payload["original"]):
        raise ValueError(f"{title}: real refetch does not equal the approved prose projection")
    with tempfile.TemporaryDirectory(prefix="refetch-", dir=root) as temporary:
        storage = WikiStorage(Path(temporary))
        storage.save_fetched_by_title(title, [], snapshot.source_text, snapshot.revision.revision_id)
        _generate_articles(ctx, storage, [title])
        if storage.read_generated_by_title(title) != payload["content"]:
            raise ValueError(f"{title}: regenerated article differs from the reviewed candidate")


def execute(
    ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Apply one frozen page through its owning publisher and retain its native manifest."""
    from erenshor.cli.commands.wiki import _create_mediawiki_client

    title = operation["target"]
    manifest_path = Path(payload["native_manifest"])
    operation_root = manifest_path.parent
    try:
        check(ctx, operation, payload, receipts)
        unresolved = [dependency for dependency in operation["dependencies"] if dependency not in receipts]
        if unresolved:
            raise ValueError(f"Wiki operation has incomplete dependencies: {unresolved}")
        if manifest_path.exists():
            previous = read_repo_page_manifest(manifest_path)
            if any(
                entry.pending_mutation
                or entry.requires_rollback
                or entry.pending_acknowledged_revision_id is not None
                or entry.new_revision_id is not None
                or entry.deploy_action in ("created", "edited")
                for entry in previous.entries
            ):
                raise SurfaceUncertainError(
                    "The native manifest already records a write. Reconcile it instead of retrying",
                    {"manifest": str(manifest_path)},
                )
            read_repo_page_sources(previous, ctx.repo_root)
            archive_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            archive = operation_root / "previous" / f"{archive_hash}.json"
            if not archive.exists():
                write_repo_page_manifest(previous, archive)
        attempts = operation_root / "attempts"
        attempts.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="attempt-", dir=attempts))
        client = _create_mediawiki_client(ctx)
    except SurfaceUncertainError:
        raise
    except Exception as error:
        raise WikiGuardError(str(error), manifest_path) from error
    mutation_started = False
    try:
        snapshots = _check_with_client(operation, payload, receipts, client)
        snapshot = snapshots[title]
        account = operation["destination"]["account"]
        client.get_page_snapshots([title], assertion="bot", assert_user=account)
        predecessor = operation["expected_base"].get("receipt")
        if predecessor:
            if predecessor not in receipts:
                raise ValueError(f"Missing prose predecessor receipt: {predecessor}")
            _regenerate(ctx, title, snapshot, payload, root)
        catalog: tuple[LinkCatalogEntry, ...] = ()
        if operation["kind"] == "wiki_article" or payload.get("render_check"):
            with tempfile.TemporaryDirectory(prefix="catalog-", dir=root) as temporary:
                catalog, _ = _generate_articles(ctx, WikiStorage(Path(temporary)), [])
        if operation["kind"] == "wiki_article":
            if extract_catalog_sha256(client.get_page(DATA_LINK_TITLE)) != payload["catalog_sha256"]:
                raise ValueError("The live semantic-link catalog differs from the approved catalog")
            _audit(ctx, client, catalog, {title: payload["content"]}, payload["planned_article_titles"])
        if operation["kind"] == "wiki_repo":
            entry = RepoWikiPageManifestEntry(**payload["manifest_entry"])
            source = root / "source" / Path(entry.source_path).name
            source.parent.mkdir()
            durable_write_text(source, payload["content"])
            entry = replace(entry, source_path=relpath(source, ctx.repo_root))
            manifest = RepoWikiPageManifest(
                entries=(entry,),
                api_url=client.api_url,
                variant=ctx.variant,
                wiki_root=str(ctx.config.variants[ctx.variant].resolved_wiki(ctx.repo_root)),
            )
            mutation_started = True
            repo_result = deploy_repo_pages(
                manifest=manifest,
                repo_root=ctx.repo_root,
                client=client,
                summary=payload["summary"],
                assertion="bot",
                assert_user=account,
                rollback_root=root / "rollback",
                checkpoint=lambda native: write_repo_page_manifest(native, manifest_path),
                include_templates=payload["include_templates"],
                include_generated_data=True,
                include_content_pages=payload["include_content_pages"],
                accept_drift=[title] if payload["accept_drift"] else (),
                render_check=payload["render_check"],
                catalog={entry.key.casefold(): entry for entry in catalog},
                expected_snapshots={title: snapshot},
            )
            write_repo_page_manifest(build_deployed_manifest(manifest, repo_result), manifest_path)
        elif operation["kind"] == "wiki_prose":
            _render_review(client, title, payload["original"], payload["content"], False)
            if snapshot.revision is None:
                raise ValueError(f"Reviewed prose page disappeared: {title}")
            mutation_started = True
            prose_result = apply_guarded_edits(
                [
                    GuardedPageEdit(
                        title, payload["summary"], payload["content"], payload["original"], snapshot.revision
                    )
                ],
                repo_root=ctx.repo_root,
                run_dir=root,
                client=client,
                variant=ctx.variant,
                wiki_root=ctx.config.variants[ctx.variant].resolved_wiki(ctx.repo_root),
                assert_user=account,
                checkpoint=lambda native: write_repo_page_manifest(native, manifest_path),
            )
            if prose_result.failed:
                raise ValueError(f"Prose write refused: {prose_result.stopped or prose_result.conflicts}")
        elif operation["kind"] == "wiki_article":
            storage = WikiStorage(root / "article")
            if snapshot.revision is not None:
                storage.save_fetched_by_title(
                    title, payload["stable_keys"], snapshot.source_text or "", snapshot.revision.revision_id
                )
            storage.save_generated_by_title(
                title, payload["stable_keys"], payload["content"], kept_roots=tuple(payload["kept_roots"])
            )
            source = storage.generated_path(title)
            durable_write_text(source, source.read_text(encoding="utf-8"))
            plan = plan_article_deploy(storage, page_titles=[title])
            if not plan.writes:
                write_repo_page_manifest(
                    RepoWikiPageManifest(
                        entries=(),
                        api_url=client.api_url,
                        variant=ctx.variant,
                        wiki_root=str(ctx.config.variants[ctx.variant].resolved_wiki(ctx.repo_root)),
                    ),
                    manifest_path,
                )
            else:
                mutation_started = True
                article_result = deploy_articles(
                    plan,
                    client=client,
                    storage=storage,
                    repo_root=ctx.repo_root,
                    rollback_root=root / "rollback",
                    summary=payload["summary"],
                    checkpoint=lambda native: write_repo_page_manifest(native, manifest_path),
                    assert_user=account,
                    variant=ctx.variant,
                    wiki_root=ctx.config.variants[ctx.variant].resolved_wiki(ctx.repo_root),
                )
                write_repo_page_manifest(article_result.manifest, manifest_path)
                if article_result.failed:
                    raise ValueError(
                        f"Article write refused: {article_result.stopped or article_result.conflicts}, "
                        f"{article_result.blocked}"
                    )
        else:
            raise ValueError(f"Unknown wiki operation kind: {operation['kind']}")
        native = read_repo_page_manifest(manifest_path)
        written = next((entry for entry in native.entries if entry.title == title), None)
        new_revision = (
            written.new_revision_id if written and written.new_revision_id else _base(snapshot)["revision_id"]
        )
        receipt = {
            "target": title,
            "new_revision": new_revision,
            "old_revision": _base(snapshot)["revision_id"],
            "content_sha256": payload["expected_content_sha256"],
            "content_model": snapshot.content_model
            or (payload.get("manifest_entry", {}).get("content_model", "wikitext")),
            "manifest": str(manifest_path),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "predecessor": predecessor,
        }
        return receipt
    except SurfaceUncertainError:
        raise
    except BaseException as error:
        if not mutation_started and isinstance(error, Exception):
            raise WikiGuardError(str(error), manifest_path) from error
        for candidate in (manifest_path, root / "manifest.json"):
            if not candidate.exists():
                continue
            native = read_repo_page_manifest(candidate)
            if any(entry.pending_mutation for entry in native.entries):
                raise SurfaceUncertainError(
                    str(error),
                    {"manifest": str(candidate), "entries": [asdict(entry) for entry in native.entries]},
                ) from error
            if any(
                entry.requires_rollback
                or entry.new_revision_id is not None
                or entry.pending_acknowledged_revision_id is not None
                for entry in native.entries
            ):
                raise WikiWriteError(str(error), candidate, native.entries) from error
        from erenshor.infrastructure.wiki.client import MediaWikiEditError, MediaWikiNetworkError

        if isinstance(error, (MediaWikiNetworkError, KeyboardInterrupt)):
            raise SurfaceUncertainError(str(error), {"manifest": str(manifest_path)}) from error
        if isinstance(error, (ValueError, MediaWikiEditError)):
            raise WikiGuardError(str(error), manifest_path) from error
        raise
    finally:
        client.close()


def reconcile(
    ctx: CLIContext,
    operation: dict[str, Any],
    payload: dict[str, Any],
    receipt: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
) -> None:
    """Require exact provider revision and bytes, allowing only the approved same-page successor."""
    reconcile_many(ctx, [(operation, payload, receipt)], receipts)


def reconcile_many(
    ctx: CLIContext,
    operations: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
    receipts: dict[str, dict[str, Any]],
) -> None:
    """Reconcile native recovery evidence and completed pages in one snapshot batch."""
    if not operations:
        return
    reader = create_readonly_mediawiki_client(ctx)
    try:
        snapshots = _snapshots(reader, sorted({operation["target"] for operation, _, _ in operations}))
        for operation, payload, receipt in operations:
            _reconcile_snapshot(ctx, operation, payload, receipt, receipts, snapshots[operation["target"]])
    finally:
        reader.close()


def _reconcile_snapshot(
    ctx: CLIContext,
    operation: dict[str, Any],
    payload: dict[str, Any],
    receipt: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
    snapshot: MediaWikiPageSnapshot,
) -> None:
    if operation["destination"] != _destination(ctx):
        raise ValueError("Wiki destination or bot account changed after review")
    if (
        receipt.get("target") != operation["target"]
        or receipt.get("content_sha256") != payload["expected_content_sha256"]
    ):
        raise ValueError("Wiki receipt does not describe the approved page bytes")
    manifest = Path(receipt["manifest"])
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != receipt["manifest_sha256"]:
        raise ValueError("Native wiki manifest changed after its receipt")
    native = read_repo_page_manifest(manifest)
    read_repo_page_sources(native, ctx.repo_root)
    entries = [entry for entry in native.entries if entry.title == operation["target"]]
    if len(entries) != len(native.entries) or len(entries) > 1:
        raise ValueError("Native wiki manifest does not describe this one-page operation")
    if entries:
        entry = entries[0]
        if entry.source_sha256 != _sha(payload["content"]):
            raise ValueError("Native wiki source hash differs from the approved bytes")
        if entry.rollback_text_source is not None:
            rollback_text = (ctx.repo_root / entry.rollback_text_source).read_bytes().decode("utf-8")
            original = payload["original"]
            if operation["expected_base"].get("receipt"):
                original = normalize_saved_text(original)
            if rollback_text != original:
                raise ValueError("Native wiki rollback text differs from the approved preimage")
        if entry.new_revision_id is not None:
            if entry.new_revision_id != receipt["new_revision"]:
                raise ValueError("Native wiki revision differs from its receipt")
        elif entry.deploy_action != "unchanged":
            raise ValueError("Native wiki manifest records no completed page")
    elif payload.get("action") != "unchanged":
        raise ValueError("Native wiki manifest omits a selected page write")
    expected = receipt
    if operation["kind"] == "wiki_prose":
        successor = receipts.get(_id("wiki_article", operation["target"]))
        if successor is not None:
            if (
                successor.get("predecessor") != operation["id"]
                or successor.get("old_revision") != receipt["new_revision"]
            ):
                raise ValueError("Article receipt does not match its approved prose predecessor")
            expected = successor
    if (
        _base(snapshot)["revision_id"] != expected["new_revision"]
        or snapshot.source_text is None
        or _sha(snapshot.source_text) != expected["content_sha256"]
        or snapshot.content_model != expected["content_model"]
    ):
        raise ValueError(f"Completed wiki page changed after its receipt: {operation['target']}")
