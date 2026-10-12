"""The one-time move of editors' item pictures to their screenshot titles.

Editors uploaded pictures of items under titles that name no role, such as
``Mask Fox.png`` or ``Screenshot 2026-08-25 142237.png``. The item infobox
shows ``<subject> screenshot.png`` (design D6 of show-item-pictures-by-role),
so each such file moves there with its history, leaves a redirect at the old
title, and the redirects that named the old title follow it. A person reviews
the list of title pairs, because an old title need not name its item. The run
records its writes like a publication run, so ``images publish --revert``
undoes it. Publication never touches a screenshot title, so nothing else moves
these files. The module goes once the move is verified.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from erenshor.application.services.image_publication_run import move, redirect

if TYPE_CHECKING:
    from collections.abc import Iterable

    from erenshor.application.services.image_publication import LiveWiki
    from erenshor.application.services.image_publication_run import AdministratorWriter, PublishWriter, RunRecord

# The roles of editors' pictures: a picture in the game, and a picture of a window of the game.
_EDITOR_ROLES = (" screenshot.png", " interface.png")

__all__ = ["ScreenshotMove", "ScreenshotPlan", "execute_screenshot_moves", "plan_screenshot_moves", "read_title_pairs"]


@dataclass(frozen=True, slots=True)
class ScreenshotMove:
    """An editor's file that moves to an item's screenshot title, with the redirects that follow it."""

    source: str
    title: str
    sha1: str
    uploader: str
    redirects: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScreenshotPlan:
    """The moves, and the old titles whose file cannot move, with the reason."""

    moves: tuple[ScreenshotMove, ...]
    skipped: tuple[tuple[str, str], ...]


def read_title_pairs(text: str) -> list[tuple[str, str]]:
    """Read the reviewed list: one ``old title<TAB>screenshot title`` per line, ``#`` starts a comment.

    Raises:
        ValueError: If a line holds no tab, a title is not a file title, or an
            old title or a screenshot title appears twice.
    """
    pairs: list[tuple[str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.startswith("#"):
            continue
        old, tab, new = line.partition("\t")
        if not tab:
            raise ValueError(f"Line {number} holds no tab between the old title and the screenshot title")
        old, new = old.strip(), new.strip()
        for title in (old, new):
            if not title.startswith("File:"):
                raise ValueError(f"Line {number}: {title} is not a file title")
        if not new.endswith(_EDITOR_ROLES):
            raise ValueError(f"Line {number}: {new} is not a screenshot or interface title")
        pairs.append((old, new))
    for side, name in ((0, "old title"), (1, "screenshot title")):
        titles = [pair[side] for pair in pairs]
        repeated = sorted({title for title in titles if titles.count(title) > 1})
        if repeated:
            raise ValueError(f"The list names the {name} {', '.join(repeated)} more than once")
    return pairs


def plan_screenshot_moves(pairs: Iterable[tuple[str, str]], live: LiveWiki, bot: str) -> ScreenshotPlan:
    """Plan the move of the editor's file at each old title to its screenshot title.

    The reviewed list decides which files are editors' pictures, also those
    that a project account uploaded as an editor, such as WoWMuch's mask pictures.

    Args:
        pairs: The reviewed old titles and screenshot titles.
        live: The listing of the wiki.
        bot: The bot account, whose files publication moves instead.
    """
    named_by: dict[str, list[str]] = defaultdict(list)
    for source, target in live.redirects.items():
        named_by[target].append(source)
    moves: list[ScreenshotMove] = []
    skipped: list[tuple[str, str]] = []
    for old, title in pairs:
        file = live.shown(old)
        if file is None:
            skipped.append((old, "no file"))
        elif file.title == title:
            skipped.append((old, f"already moved to {title}"))
        elif file.title != old:
            skipped.append((old, f"redirects to {file.title}, which the list must name instead"))
        elif file.user == bot:
            skipped.append((old, f"the bot {bot} uploaded it, and publication moves its files"))
        elif live.has_page(title):
            skipped.append((old, f"{title} is taken"))
        else:
            moves.append(
                ScreenshotMove(
                    source=old,
                    title=title,
                    sha1=file.sha1,
                    uploader=file.user or "(hidden)",
                    redirects=tuple(sorted(named_by.get(old, ()))),
                )
            )
    return ScreenshotPlan(moves=tuple(sorted(moves, key=lambda item: item.title)), skipped=tuple(sorted(skipped)))


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
