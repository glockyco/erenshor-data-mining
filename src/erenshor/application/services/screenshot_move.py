"""The one-time move of editors' character pictures to their screenshot titles.

Before pictures had role titles, an editor's picture of a character sat at the
character's plain title, ``<image name>.png``, or, for a name with a colon, at
that title without the characters that MediaWiki forbids. Its role title is
``<subject> screenshot.png`` (design D7 of name-pictures-by-role). This plan
moves each such file there with its history, leaves a redirect at the old
title, and points the redirects that named the old title at the file. The run
records its writes like a publication run, so ``images publish --revert``
undoes it. Publication never touches a screenshot title, so nothing else
moves these files. The module goes once the cutover is verified.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from erenshor.application.services.image_publication_run import move, redirect
from erenshor.domain.value_objects.wiki_filename import picture_file_title, picture_subject

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from erenshor.application.services.image_publication import LiveWiki
    from erenshor.application.services.image_publication_run import AdministratorWriter, PublishWriter, RunRecord

__all__ = ["ScreenshotMove", "ScreenshotPlan", "execute_screenshot_moves", "plan_screenshot_moves"]


@dataclass(frozen=True, slots=True)
class ScreenshotMove:
    """An editor's file that moves to a character's screenshot title, with the redirects that follow it."""

    source: str
    title: str
    sha1: str
    uploader: str
    redirects: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScreenshotPlan:
    """The moves, and the old titles that hold an editor's file that cannot move, with the reason."""

    moves: tuple[ScreenshotMove, ...]
    skipped: tuple[tuple[str, str], ...]


def plan_screenshot_moves(
    characters: Iterable[tuple[str | None, str | None]], live: LiveWiki, owners: Collection[str]
) -> ScreenshotPlan:
    """Plan the move of every editor's file that a character's plain title shows.

    Args:
        characters: The image name and display name of each character.
        live: The listing of the wiki.
        owners: The project's accounts, whose files publication moves instead.
    """
    named_by: dict[str, list[str]] = defaultdict(list)
    for source, target in live.redirects.items():
        named_by[target].append(source)
    moves: dict[str, ScreenshotMove] = {}
    skipped: dict[str, str] = {}
    for names in sorted({names for names in characters if picture_subject(*names)}, key=lambda n: picture_subject(*n)):
        name = next(name for name in names if picture_subject(name))
        subject = picture_subject(name)
        title = f"File:{picture_file_title('screenshot', name)}"
        for plain in dict.fromkeys((f"File:{name}.png", f"File:{subject}.png")):
            file = live.shown(plain)
            if file is None or file.user in owners or file.title in moves or file.title in skipped:
                continue
            if live.has_page(title):
                skipped[file.title] = f"{title} is taken"
                continue
            moves[file.title] = ScreenshotMove(
                source=file.title,
                title=title,
                sha1=file.sha1,
                uploader=file.user or "(hidden)",
                redirects=tuple(sorted(named_by.get(file.title, ()))),
            )
    return ScreenshotPlan(
        moves=tuple(sorted(moves.values(), key=lambda item: item.title)),
        skipped=tuple(sorted(skipped.items())),
    )


def execute_screenshot_moves(
    plan: ScreenshotPlan,
    writer: PublishWriter,
    administrator: AdministratorWriter | None,
    record: RunRecord,
    summary: str,
) -> None:
    """Move each file with the administrator account, then point the redirects that named its old title at it.

    Raises:
        ValueError: If the plan moves files and no administrator is given.
    """
    if plan.moves and administrator is None:
        raise ValueError("Moving files needs the administrator account")
    for item in plan.moves:
        assert administrator is not None
        if move(item.source, item.title, item.sha1, writer, administrator, record, summary):
            for title in item.redirects:
                redirect(title, item.title, item.source, writer, record, summary)
