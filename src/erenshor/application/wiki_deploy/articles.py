"""Guarded deployment of generated wiki articles.

Generation merges each article into the live revision that ``wiki fetch``
saved. A write is safe only while the live page is still at that revision:
a newer revision means the merge did not see an edit. The deploy therefore
plans locally, reads the live revisions in batches, parses each changed
article on the wiki, writes it against its fetched revision, and reports
every other page.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol

from erenshor.application.wiki.generators.page_normalizer import PageNormalizer
from erenshor.application.wiki.services.helpers import normalise_generated_page_content
from erenshor.application.wiki_deploy.link_audit_service import TRACKING_CATEGORIES
from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry
from erenshor.application.wiki_deploy.pages import rollback_filename
from erenshor.infrastructure.wiki import (
    MediaWikiAPIError,
    MediaWikiAssertionError,
    MediaWikiEditConflictError,
    MediaWikiEditError,
)
from erenshor.infrastructure.wiki.content import normalize_saved_text

if TYPE_CHECKING:
    from pathlib import Path

    from erenshor.application.wiki.services.storage import WikiStorage
    from erenshor.infrastructure.wiki import MediaWikiPageRevision, MediaWikiPageSnapshot, MediaWikiParse

ArticleAction = Literal["edit", "create", "unchanged"]
_WriteOutcome = Literal["requested", "skipped", "stop"]

_NORMALIZER = PageNormalizer()
_SCRIPT_ERROR = re.compile(r'class="[^"]*\bscribunto-error\b')


class ArticleDeployClient(Protocol):
    """MediaWiki operations required by the article deploy."""

    def get_page_snapshots(
        self,
        titles: Sequence[str],
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> dict[str, MediaWikiPageSnapshot]: ...

    def get_page_categories(self, titles: Sequence[str]) -> dict[str, frozenset[str]]: ...

    def parse_wikitext(self, title: str, text: str) -> MediaWikiParse: ...

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: Literal["user", "bot"] = "bot",
        assert_user: str | None = None,
    ) -> int: ...

    def safe_create_page(
        self,
        title: str,
        content: str,
        start_timestamp: str,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: Literal["user", "bot"] = "bot",
        assert_user: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class PlannedArticle:
    """One generated article and what the deploy does with it.

    ``edit`` writes against ``fetched_revision_id``. ``create`` writes a page
    that had no live revision at generation. ``unchanged`` differs from the
    fetched text only by page normalization, so the deploy does not write it.
    """

    title: str
    action: ArticleAction
    generated_text: str
    fetched_revision_id: int | None


@dataclass(frozen=True, slots=True)
class ArticleIssue:
    """A page that the deploy did not write, with the reason."""

    title: str
    reason: str


@dataclass(frozen=True, slots=True)
class ArticleDeployPlan:
    """The local plan of an article deploy.

    ``stale`` lists pages whose fetched text has no revision, so no write can
    be guarded. They are never written.
    """

    articles: tuple[PlannedArticle, ...]
    stale: tuple[ArticleIssue, ...]

    @property
    def writes(self) -> tuple[PlannedArticle, ...]:
        """Articles that the deploy writes, in plan order."""
        return tuple(article for article in self.articles if article.action != "unchanged")

    def count(self, action: ArticleAction) -> int:
        """Return the number of planned articles with ``action``."""
        return sum(1 for article in self.articles if article.action == action)


@dataclass(frozen=True, slots=True)
class ArticleDeployResult:
    """The outcome of an article deploy.

    ``manifest`` lists every written page in the format that
    ``wiki rollback-repo-pages`` restores. ``unchanged`` lists planned edits
    that MediaWiki saved as no change. ``stopped`` names the error that ended
    the run before the plan was complete.
    """

    manifest: RepoWikiPageManifest
    unchanged: tuple[str, ...]
    conflicts: tuple[ArticleIssue, ...]
    blocked: tuple[ArticleIssue, ...]
    stopped: str | None

    def count(self, action: Literal["edited", "created"]) -> int:
        """Return the number of written pages with ``action``."""
        return sum(1 for entry in self.manifest.entries if entry.deploy_action == action)

    @property
    def failed(self) -> bool:
        """Whether a planned page was not written or the run stopped early."""
        return bool(self.conflicts or self.blocked or self.stopped)


def has_data_change(fetched_text: str, generated_text: str) -> bool:
    """Return whether a generated article differs from its fetched text beyond page normalization.

    Page normalization sorts the categories at the bottom of the page, removes
    extra blank lines, and strips line-end spaces. A write that changes only
    these rearranges the text of the editors and adds no data.
    """
    normalized_fetched = normalise_generated_page_content(_NORMALIZER.normalize(fetched_text))
    return normalize_saved_text(normalized_fetched) != normalize_saved_text(generated_text)


def parse_problems(parse: MediaWikiParse, live_categories: frozenset[str]) -> tuple[str, ...]:
    """Return why a parsed article must not be written, or nothing.

    A script error or a missing template blocks the page. A category without a
    page, or an Erenshor link tracking category, blocks the page only when the
    live page is not in that category already: the write must not make the
    page worse, but it does not have to repair it.
    """
    problems: list[str] = []
    if _SCRIPT_ERROR.search(parse.html):
        problems.append("script error")
    problems.extend(f"missing template {template.title}" for template in parse.templates if not template.exists)
    for category in parse.categories:
        if category.title in live_categories:
            continue
        if not category.exists:
            problems.append(f"category without a page: {category.title}")
        elif category.title in TRACKING_CATEGORIES:
            problems.append(f"new link tracking category: {category.title}")
    return tuple(problems)


def plan_article_deploy(
    storage: WikiStorage,
    *,
    page_titles: Sequence[str] | None = None,
    limit: int | None = None,
) -> ArticleDeployPlan:
    """Plan an article deploy from generated and fetched storage, without network access.

    ``page_titles`` selects generated articles. ``limit`` caps the number of
    articles to write.
    """
    titles = storage.list_generated_titles()
    if page_titles is not None:
        requested = set(page_titles)
        titles = tuple(title for title in titles if title in requested)

    metadata = storage.get_metadata_by_titles(titles)
    articles: list[PlannedArticle] = []
    stale: list[ArticleIssue] = []
    writes = 0
    for title in titles:
        generated_text = storage.read_generated_by_title(title)
        if generated_text is None:
            raise FileNotFoundError(f"Generated wiki content missing for {title!r}")
        fetched_text = storage.read_fetched_by_title(title)
        fetched_revision_id = metadata[title].fetched_revision_id
        action: ArticleAction
        if fetched_text is None:
            action = "create"
        elif fetched_revision_id is None:
            stale.append(ArticleIssue(title, "the fetched text has no revision; fetch and generate it again"))
            continue
        elif has_data_change(fetched_text, generated_text):
            action = "edit"
        else:
            action = "unchanged"

        if action != "unchanged":
            if limit is not None and writes >= limit:
                continue
            writes += 1
        articles.append(PlannedArticle(title, action, generated_text, fetched_revision_id))
    return ArticleDeployPlan(articles=tuple(articles), stale=tuple(stale))


@dataclass
class _DeployState:
    written: list[RepoWikiPageManifestEntry] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[ArticleIssue] = field(default_factory=list)
    blocked: list[ArticleIssue] = field(default_factory=list)
    stopped: str | None = None

    def manifest(self) -> RepoWikiPageManifest:
        return RepoWikiPageManifest(entries=tuple(self.written))


def deploy_articles(
    plan: ArticleDeployPlan,
    *,
    client: ArticleDeployClient,
    storage: WikiStorage,
    repo_root: Path,
    rollback_root: Path,
    summary: str,
    checkpoint: Callable[[RepoWikiPageManifest], None] | None = None,
    write_interval: float = 2.0,
    sleep: Callable[[float], None] | None = None,
    batch_size: int = 50,
) -> ArticleDeployResult:
    """Write the planned articles that are still at their fetched revision.

    Live revisions and categories are read in batches. A page whose live
    revision differs from its fetched revision, or a page planned for creation
    that exists, is a conflict. Each other page is parsed on the wiki first,
    and a page with a parse problem (see ``parse_problems``) or a page that
    MediaWiki refuses is blocked. Conflicts and blocked pages are collected,
    and the run continues. A failed assertion or a transport failure ends the
    run at once, because every later write would fail the same way.

    Before each edit, the live text is saved as rollback text. After each
    write, the manifest is checkpointed and the fetched copy becomes the
    saved text at its new revision.
    """
    pause = time.sleep if sleep is None else sleep
    state = _DeployState()
    writes = plan.writes
    for start in range(0, len(writes), batch_size):
        batch = writes[start : start + batch_size]
        try:
            snapshots = client.get_page_snapshots([article.title for article in batch], assertion="bot")
            live_categories = client.get_page_categories(
                [article.title for article in batch if snapshots[article.title].revision is not None]
            )
        except MediaWikiAPIError as error:
            state.stopped = f"reading live pages failed: {error}"
            break
        for article in batch:
            outcome = _write_article(
                article,
                snapshots[article.title],
                live_categories.get(article.title, frozenset()),
                state=state,
                client=client,
                storage=storage,
                repo_root=repo_root,
                rollback_root=rollback_root,
                summary=summary,
            )
            if outcome == "stop":
                break
            if outcome == "requested":
                if checkpoint is not None:
                    checkpoint(state.manifest())
                pause(write_interval)
        if state.stopped is not None:
            break

    return ArticleDeployResult(
        manifest=state.manifest(),
        unchanged=tuple(state.unchanged),
        conflicts=tuple(state.conflicts),
        blocked=tuple(state.blocked),
        stopped=state.stopped,
    )


def _write_article(
    article: PlannedArticle,
    snapshot: MediaWikiPageSnapshot,
    live_categories: frozenset[str],
    *,
    state: _DeployState,
    client: ArticleDeployClient,
    storage: WikiStorage,
    repo_root: Path,
    rollback_root: Path,
    summary: str,
) -> _WriteOutcome:
    """Write one article if its live page is still the one that generation merged into."""
    title = article.title
    live = snapshot.revision
    conflict = _live_conflict(article, live)
    if conflict is not None:
        state.conflicts.append(ArticleIssue(title, conflict))
        return "skipped"
    try:
        problems = parse_problems(client.parse_wikitext(title, article.generated_text), live_categories)
    except MediaWikiAPIError as error:
        state.stopped = f"{title}: parsing failed: {error}"
        return "stop"
    if problems:
        state.blocked.append(ArticleIssue(title, "; ".join(problems)))
        return "skipped"

    rollback_text_source: str | None = None
    if live is not None:
        rollback_path = rollback_root / rollback_filename(title)
        rollback_path.parent.mkdir(parents=True, exist_ok=True)
        rollback_path.write_text(snapshot.source_text or "", encoding="utf-8")
        rollback_text_source = rollback_path.relative_to(repo_root).as_posix()

    try:
        if live is not None:
            new_revision_id = client.safe_edit_page(
                title=title, content=article.generated_text, base_revision=live, summary=summary, assertion="bot"
            )
        else:
            new_revision_id = client.safe_create_page(
                title=title,
                content=article.generated_text,
                start_timestamp=snapshot.start_timestamp,
                summary=summary,
                assertion="bot",
            )
    except MediaWikiAPIError as error:
        return _record_write_error(state, title, error)

    storage.record_deployed(title, article.generated_text, new_revision_id)
    if live is not None and new_revision_id == live.revision_id:
        state.unchanged.append(title)
        return "requested"
    state.written.append(
        RepoWikiPageManifestEntry(
            title=title,
            source_path=storage.generated_path(title).relative_to(repo_root).as_posix(),
            source_sha256=hashlib.sha256(article.generated_text.encode("utf-8")).hexdigest(),
            ownership_class="article",
            upload_stage="article",
            content_model="wikitext",
            declares_cargo_table=False,
            cargo_tables=(),
            old_revision_id=None if live is None else live.revision_id,
            old_revision_timestamp=None if live is None else live.timestamp,
            new_revision_id=new_revision_id,
            rollback_text_source=rollback_text_source,
            deploy_action="created" if live is None else "edited",
        )
    )
    return "requested"


def _live_conflict(article: PlannedArticle, live: MediaWikiPageRevision | None) -> str | None:
    """Return why the live page is not the page that generation merged into, or None."""
    if article.action == "create":
        if live is None:
            return None
        return f"exists at revision {live.revision_id} but was generated without its live text"
    if live is None:
        return "was deleted after the fetch"
    if live.revision_id != article.fetched_revision_id:
        return (
            f"changed after the fetch: live revision {live.revision_id}, fetched revision {article.fetched_revision_id}"
        )
    return None


def _record_write_error(state: _DeployState, title: str, error: MediaWikiAPIError) -> _WriteOutcome:
    """Record a refused write, or stop the run when the failure is not specific to the page."""
    if isinstance(error, MediaWikiEditConflictError):
        state.conflicts.append(ArticleIssue(title, str(error)))
    elif isinstance(error, MediaWikiEditError) and not isinstance(error, MediaWikiAssertionError):
        state.blocked.append(ArticleIssue(title, str(error)))
    else:
        state.stopped = f"{title}: {error}"
        return "stop"
    return "requested"
