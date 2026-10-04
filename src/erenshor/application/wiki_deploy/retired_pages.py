"""Read-only review of articles created by WoWBot that generation no longer writes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal

from erenshor.infrastructure.wiki.template_parser import TemplateParser

if TYPE_CHECKING:
    from erenshor.application.wiki.lifecycle import ContentLifecycle, LifecyclePage, LifecycleRename
    from erenshor.infrastructure.wiki.client import MediaWikiClient, MediaWikiTitleStatus

RetiredState = Literal["pending notice", "pending redirect", "marked", "redirect", "unexplained"]
_ROOTS = ("Item", "Ability", "Stance", "Character", "Zone")


@dataclass(frozen=True, slots=True)
class RetiredPage:
    title: str
    stable_key: str | None
    current_title: str | None
    expected: str
    state: RetiredState
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RetiredPageReport:
    checked: int
    pages: tuple[RetiredPage, ...]
    reviewed_non_bot: tuple[RetiredPage, ...]

    @property
    def pending(self) -> int:
        return sum(page.state.startswith("pending") for page in (*self.pages, *self.reviewed_non_bot))

    @property
    def unexplained(self) -> int:
        return sum(page.state == "unexplained" for page in (*self.pages, *self.reviewed_non_bot))

    @property
    def has_errors(self) -> bool:
        return self.unexplained > 0


def _stable_keys(parser: TemplateParser, text: str) -> set[str]:
    code = parser.parse(text)
    return {
        key.strip()
        for root in parser.find_templates(code, _ROOTS)
        if (key := parser.get_param(root, "stablekey")) and key.strip()
    }


def _rename_state(
    title: str,
    key: str | None,
    status: MediaWikiTitleStatus,
    rename: LifecycleRename,
    identities: Mapping[str, set[str]],
    target_exists: bool,
) -> RetiredPage:
    expected = "redirect"
    destination = rename.current_title

    def invalid(reason: str) -> RetiredPage:
        return RetiredPage(title, key, destination, expected, "unexplained", reason)

    if key is not None and key != rename.stable_key:
        return invalid("The live stable key differs from the reviewed key.")
    if identities.get(rename.stable_key) != {destination}:
        return invalid("The reviewed key does not identify the generated target.")
    if not target_exists:
        return invalid("The reviewed redirect target is not live.")
    if status.redirect_target is not None:
        if status.redirect_target != destination or not status.exists:
            return invalid("The redirect does not reach the reviewed target.")
        return RetiredPage(title, key, destination, expected, "redirect")
    return RetiredPage(title, key, destination, expected, "pending redirect")


def _notice_state(title: str, key: str | None, source: str, page: LifecyclePage, parser: TemplateParser) -> RetiredPage:
    expected = f"{page.state} notice"

    def invalid(reason: str) -> RetiredPage:
        return RetiredPage(title, key, None, expected, "unexplained", reason)

    notices = parser.find_templates(parser.parse(source), ("Historical Content",))
    if not notices:
        return RetiredPage(title, key, None, expected, "pending notice")
    if len(notices) != 1:
        return invalid("The page has more than one historical notice.")
    notice = notices[0]
    for param, wanted in (
        ("state", page.state),
        ("thing", page.thing),
        ("update", page.update),
        ("url", page.patch_notes_url),
    ):
        actual = parser.get_param(notice, param)
        if (actual or "").strip() != (wanted or ""):
            return invalid(f"The notice has an incorrect {param}.")
    written_date = parser.get_param(notice, "date")
    try:
        notice_date = (
            datetime.strptime(written_date.strip(), "%B %d, %Y").date()
            if written_date and written_date.strip()
            else None
        )
    except ValueError:
        return invalid("The notice has an invalid date.")
    if notice_date != (date.fromisoformat(page.date) if page.date else None):
        return invalid("The notice has an incorrect date.")
    return RetiredPage(title, key, None, expected, "marked")


def _removed_state(
    title: str,
    key: str | None,
    source: str,
    status: MediaWikiTitleStatus,
    page: LifecyclePage,
    destinations: set[str],
    parser: TemplateParser,
) -> RetiredPage:
    expected = f"{page.state} notice"

    def invalid(reason: str) -> RetiredPage:
        return RetiredPage(title, key, None, expected, "unexplained", reason)

    if key is not None and page.stable_key is not None and key != page.stable_key:
        return invalid("The live stable key differs from the reviewed key.")
    if page.state != "removed":
        return invalid("An unobtainable page still needs a generated article.")
    if destinations:
        return invalid("The stable key now belongs to a different generated title.")
    if status.redirect_target is not None:
        return invalid("A removed page must keep its article, not redirect.")
    return _notice_state(title, key, source, page, parser)


def _classify(
    title: str,
    source: str,
    status: MediaWikiTitleStatus,
    lifecycle: ContentLifecycle,
    identities: Mapping[str, set[str]],
    parser: TemplateParser,
    statuses: Mapping[str, MediaWikiTitleStatus],
) -> RetiredPage:
    keys = _stable_keys(parser, source)
    recorded_page = lifecycle.pages.get(title)
    rename = lifecycle.renames.get(title)
    recorded_key = rename.stable_key if rename else recorded_page.stable_key if recorded_page else None
    key = next(iter(keys)) if len(keys) == 1 else recorded_key if not keys else None
    destinations = {target for live_key in keys for target in identities.get(live_key, ()) if target != title}
    current_title = next(iter(destinations)) if len(destinations) == 1 else rename.current_title if rename else None

    if len(keys) > 1:
        return RetiredPage(title, None, None, "review needed", "unexplained", "The page has several stable keys.")
    if rename:
        return _rename_state(title, key, status, rename, identities, statuses[rename.current_title].exists)
    if recorded_page:
        return _removed_state(title, key, source, status, recorded_page, destinations, parser)
    if status.redirect_target is not None:
        current_title = status.redirect_target
    return RetiredPage(
        title, key, current_title, "review needed", "unexplained", "No reviewed disposition exists for this title."
    )


def audit_retired_pages(
    client: MediaWikiClient,
    generated_pages: Mapping[str, str],
    lifecycle: ContentLifecycle,
    creator: str = "WoWBot",
) -> RetiredPageReport:
    """Check every live bot creation and every reviewed old page without writing."""
    parser = TemplateParser()
    identities: dict[str, set[str]] = {}
    for title, source in generated_pages.items():
        for key in _stable_keys(parser, source):
            identities.setdefault(key, set()).add(title)

    created = set(client.list_user_created_pages(creator))
    retired = created - generated_pages.keys()
    reviewed = (set(lifecycle.pages) | set(lifecycle.renames)) - generated_pages.keys()
    candidates = sorted(retired | reviewed, key=lambda title: (title.casefold(), title))
    targets = {lifecycle.renames[title].current_title for title in candidates if title in lifecycle.renames}
    query_titles = sorted(set(candidates) | targets, key=lambda title: (title.casefold(), title))
    statuses = client.get_title_statuses(query_titles)
    if set(statuses) != set(query_titles):
        raise ValueError("Retired page review is incomplete: live title statuses are missing")
    check_titles = [
        title for title in candidates if statuses[title].exists or statuses[title].redirect_target is not None
    ]
    sources = client.get_pages(check_titles)
    if set(sources) != set(check_titles):
        raise ValueError("Retired page review is incomplete: live page sources are missing")

    bot_pages: list[RetiredPage] = []
    other_pages: list[RetiredPage] = []
    for title in candidates:
        live_source = sources.get(title)
        if live_source is None:
            if statuses[title].exists or statuses[title].redirect_target is not None:
                raise ValueError(f"Retired page review is incomplete: source for {title!r} is missing")
            if title in reviewed:
                item = RetiredPage(
                    title, None, None, "reviewed disposition", "unexplained", "The reviewed page is missing."
                )
                (bot_pages if title in created else other_pages).append(item)
            continue
        item = _classify(title, live_source, statuses[title], lifecycle, identities, parser, statuses)
        (bot_pages if title in created else other_pages).append(item)
    return RetiredPageReport(checked=len(created), pages=tuple(bot_pages), reviewed_non_bot=tuple(other_pages))
