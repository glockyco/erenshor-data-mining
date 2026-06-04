"""Live integration tests for the wiki deploy pipeline.

These exercise deploy, rollback, dependency refresh, and the fail-closed failure
modes (edit conflict, lost create race, assertion failure) against the local
MediaWiki harness in ``wiki-dev/``. They are skipped unless that harness is
reachable at localhost:8088 and Docker is available for bot provisioning and
page cleanup. Bring the harness up with ``wiki-dev/bootstrap.sh``.

maxlag/Retry-After backoff is not exercised here: replication lag cannot be
induced on a single-node dev database without artificial injection, so that
behavior is covered deterministically by the client unit tests.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry
from erenshor.application.wiki_deploy.override_migration import review_article_overrides
from erenshor.application.wiki_deploy.pages import build_deployed_manifest, deploy_repo_pages
from erenshor.application.wiki_deploy.refresh import refresh_embedded_pages
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.infrastructure.wiki import (
    MediaWikiAssertionError,
    MediaWikiClient,
    MediaWikiEditConflictError,
    MediaWikiRequestPolicy,
)

pytestmark = pytest.mark.integration

WIKI_BASE_URL = "http://localhost:8088"
API_URL = f"{WIKI_BASE_URL}/api.php"
BOT_USER = "ErenshorBot"
BOT_PASSWORD = "BotDevPassword-2026"
COMPOSE_FILE = Path(__file__).resolve().parents[2] / "wiki-dev" / "compose.yml"


def _harness_reachable() -> bool:
    try:
        response = httpx.get(
            API_URL,
            params={"action": "query", "meta": "siteinfo", "format": "json"},
            timeout=5.0,
        )
    except (httpx.HTTPError, OSError):
        return False
    if response.status_code != 200:
        return False
    try:
        return "query" in response.json()
    except ValueError:
        return False


def _docker_compose(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        input=stdin.encode() if stdin is not None else None,
        capture_output=True,
        timeout=180,
        check=False,
    )


def _ensure_deploy_bot() -> None:
    result = _docker_compose(
        "exec",
        "-T",
        "mediawiki",
        "php",
        "maintenance/run.php",
        "createAndPromote",
        "--bot",
        "--force",
        BOT_USER,
        BOT_PASSWORD,
    )
    if result.returncode != 0:
        pytest.skip(f"Could not provision deploy bot: {result.stderr.decode(errors='replace')}")


def _delete_pages(titles: list[str]) -> None:
    if not titles:
        return
    _docker_compose(
        "exec",
        "-T",
        "mediawiki",
        "php",
        "maintenance/run.php",
        "deleteBatch.php",
        "-r",
        "integration test cleanup",
        stdin="\n".join(titles) + "\n",
    )


def _page_links(title: str) -> list[str]:
    response = httpx.get(
        API_URL,
        params={
            "action": "query",
            "titles": title,
            "prop": "links",
            "pllimit": "max",
            "format": "json",
            "formatversion": "2",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    pages = response.json()["query"]["pages"]
    return sorted(link["title"] for link in pages[0].get("links", []))


def _module_manifest(title: str, source_path: str, content: str) -> RepoWikiPageManifest:
    return RepoWikiPageManifest(
        entries=(
            RepoWikiPageManifestEntry(
                title=title,
                source_path=source_path,
                source_sha256=hashlib.sha256(content.encode()).hexdigest(),
                ownership_class="lua_module",
                upload_stage="lua_module",
                content_model="Scribunto",
                declares_cargo_table=False,
                cargo_tables=(),
            ),
        )
    )


class _PageScope:
    """Tracks live wiki pages a test owns and gives each a clean slate."""

    def __init__(self) -> None:
        self.titles: list[str] = []

    def claim(self, title: str) -> str:
        _delete_pages([title])
        self.titles.append(title)
        return title


@pytest.fixture(scope="module")
def wiki_client() -> Iterator[MediaWikiClient]:
    if not _harness_reachable():
        pytest.skip(f"Local MediaWiki harness not reachable at {WIKI_BASE_URL}")
    if shutil.which("docker") is None:
        pytest.skip("Docker is required to provision the deploy bot and clean up test pages")

    _ensure_deploy_bot()

    # No inter-request pacing: the local harness has no rate limit and the suite
    # should stay fast. Conflict-safety still comes from baserevid/starttimestamp.
    policy = MediaWikiRequestPolicy(read_delay=0.0, write_delay=0.0)
    client = MediaWikiClient(
        api_url=API_URL,
        bot_username=BOT_USER,
        bot_password=BOT_PASSWORD,
        rate_limit_delay=0.0,
        request_policy=policy,
    )
    client.login()
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def pages(wiki_client: MediaWikiClient) -> Iterator[_PageScope]:
    scope = _PageScope()
    try:
        yield scope
    finally:
        _delete_pages(scope.titles)


def test_deploy_creates_page_then_skips_unchanged(
    wiki_client: MediaWikiClient, pages: _PageScope, tmp_path: Path
) -> None:
    """A first deploy creates the page; an identical redeploy is detected as unchanged."""
    title = pages.claim("Module:ErenshorIT/Items")
    source = "return { it = 1 }\n"
    source_path = "wiki/modules/ErenshorIT/Items.lua"
    (tmp_path / source_path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / source_path).write_text(source, encoding="utf-8")
    manifest = _module_manifest(title, source_path, source)

    first = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=wiki_client,
        summary="Integration deploy",
        assertion="bot",
        assert_user=BOT_USER,
        rollback_root=tmp_path / "rollback",
    )
    assert [entry.status for entry in first.entries] == ["changed"]
    # MediaWiki strips the trailing newline on save.
    assert wiki_client.get_page(title) == "return { it = 1 }"

    second = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=wiki_client,
        summary="Integration redeploy",
        assertion="bot",
        assert_user=BOT_USER,
        rollback_root=tmp_path / "rollback",
    )
    assert [entry.status for entry in second.entries] == ["unchanged"]


def test_deploy_safe_edit_then_rollback_restores_previous_text(
    wiki_client: MediaWikiClient, pages: _PageScope, tmp_path: Path
) -> None:
    """A changed deploy safe-edits the page, and rollback restores the captured prior text."""
    title = pages.claim("Module:ErenshorIT/Rollback")
    source_path = "wiki/modules/ErenshorIT/Rollback.lua"
    (tmp_path / source_path).parent.mkdir(parents=True, exist_ok=True)

    first_source = "return { v = 1 }\n"
    (tmp_path / source_path).write_text(first_source, encoding="utf-8")
    manifest = _module_manifest(title, source_path, first_source)
    deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=wiki_client,
        summary="Integration deploy v1",
        assertion="bot",
        assert_user=BOT_USER,
        rollback_root=tmp_path / "rollback",
    )

    second_source = "return { v = 2 }\n"
    (tmp_path / source_path).write_text(second_source, encoding="utf-8")
    changed = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=wiki_client,
        summary="Integration deploy v2",
        assertion="bot",
        assert_user=BOT_USER,
        rollback_root=tmp_path / "rollback",
    )
    assert [entry.status for entry in changed.entries] == ["changed"]
    assert wiki_client.get_page(title) == "return { v = 2 }"

    deployed_manifest = build_deployed_manifest(manifest, changed)
    rollback_repo_pages(
        manifest=deployed_manifest,
        repo_root=tmp_path,
        client=wiki_client,
        summary="Integration rollback",
        assertion="bot",
        assert_user=BOT_USER,
    )
    assert wiki_client.get_page(title) == "return { v = 1 }"


def test_safe_edit_detects_conflict_on_stale_base_revision(wiki_client: MediaWikiClient, pages: _PageScope) -> None:
    """An edit against a base revision that has since changed fails closed as a conflict."""
    title = pages.claim("Module:ErenshorIT/Conflict")
    start = wiki_client.get_edit_start_timestamp(assertion="bot")
    wiki_client.safe_create_page(
        title=title, content="return { n = 0 }\n", start_timestamp=start, summary="Integration", assertion="bot"
    )

    stale = wiki_client.get_page_revision_metadata(title, assertion="bot")
    assert stale is not None
    # An out-of-band edit advances the revision past the captured base.
    wiki_client.safe_edit_page(
        title=title, content="return { n = 1 }\n", base_revision=stale, summary="Out of band", assertion="bot"
    )

    with pytest.raises(MediaWikiEditConflictError):
        wiki_client.safe_edit_page(
            title=title, content="return { n = 2 }\n", base_revision=stale, summary="Stale", assertion="bot"
        )


def test_safe_create_existing_page_is_conflict(wiki_client: MediaWikiClient, pages: _PageScope) -> None:
    """Creating a page that already exists is surfaced as a conflict, not a generic failure."""
    title = pages.claim("Module:ErenshorIT/Exists")
    first_start = wiki_client.get_edit_start_timestamp(assertion="bot")
    wiki_client.safe_create_page(
        title=title, content="return {}\n", start_timestamp=first_start, summary="Integration", assertion="bot"
    )

    second_start = wiki_client.get_edit_start_timestamp(assertion="bot")
    with pytest.raises(MediaWikiEditConflictError):
        wiki_client.safe_create_page(
            title=title,
            content="return { x = 1 }\n",
            start_timestamp=second_start,
            summary="Duplicate",
            assertion="bot",
        )


def test_safe_edit_fails_closed_on_unexpected_user(wiki_client: MediaWikiClient, pages: _PageScope) -> None:
    """Asserting a different username than the logged-in bot aborts the edit."""
    title = pages.claim("Module:ErenshorIT/Assert")
    start = wiki_client.get_edit_start_timestamp(assertion="bot")
    wiki_client.safe_create_page(
        title=title, content="return {}\n", start_timestamp=start, summary="Integration", assertion="bot"
    )

    base = wiki_client.get_page_revision_metadata(title, assertion="bot")
    assert base is not None
    with pytest.raises(MediaWikiAssertionError):
        wiki_client.safe_edit_page(
            title=title,
            content="return { x = 2 }\n",
            base_revision=base,
            summary="Wrong user",
            assertion="bot",
            assert_user="NotTheDeployBot",
        )


def test_refresh_forces_dependent_link_update(wiki_client: MediaWikiClient, pages: _PageScope) -> None:
    """Refreshing transcluding pages re-runs LinksUpdate so dependent link tables reflect a template change."""
    template = pages.claim("Template:ErenshorITLink")
    user = pages.claim("ErenshorITLinkUser")

    template_start = wiki_client.get_edit_start_timestamp(assertion="bot")
    wiki_client.safe_create_page(
        title=template,
        content="[[ErenshorITTargetA]]",
        start_timestamp=template_start,
        summary="Integration",
        assertion="bot",
    )
    user_start = wiki_client.get_edit_start_timestamp(assertion="bot")
    wiki_client.safe_create_page(
        title=user, content="{{ErenshorITLink}}", start_timestamp=user_start, summary="Integration", assertion="bot"
    )
    assert _page_links(user) == ["ErenshorITTargetA"]

    base = wiki_client.get_page_revision_metadata(template, assertion="bot")
    assert base is not None
    wiki_client.safe_edit_page(
        title=template, content="[[ErenshorITTargetB]]", base_revision=base, summary="Retarget", assertion="bot"
    )

    result = refresh_embedded_pages(
        client=wiki_client,
        dependency_titles=(template,),
        namespaces=(0,),
        assertion="bot",
        assert_user=BOT_USER,
    )

    assert user in result.refreshed
    # The forced link update re-parsed the dependent so its stored links follow the template change.
    assert _page_links(user) == ["ErenshorITTargetB"]


def test_override_review_minimizes_article_params_through_lua(wiki_client: MediaWikiClient, pages: _PageScope) -> None:
    """Override review compares article params against deployed Lua field accessors."""
    title = pages.claim("ErenshorITOverrideItem")
    start_timestamp = wiki_client.get_edit_start_timestamp(assertion="bot")
    wiki_client.safe_create_page(
        title=title,
        content=(
            "{{Item|stablekey=item:ember_longsword|type=Weapon|description=A custom flavor line|image=CustomEmber.png}}"
        ),
        start_timestamp=start_timestamp,
        summary="Integration",
        assertion="bot",
    )

    reviews = review_article_overrides(
        client=wiki_client,
        titles=(title,),
        template_names=("Item",),
        module="Erenshor/Item",
    )

    assert len(reviews) == 1
    [review] = reviews
    assert review.migration.removed_fields == ("type",)
    assert review.migration.preserved_fields == ("description", "image")
    assert "type=Weapon" not in review.migration.minimized_wikitext
    assert "description=A custom flavor line" in review.migration.minimized_wikitext
    assert "image=CustomEmber.png" in review.migration.minimized_wikitext
