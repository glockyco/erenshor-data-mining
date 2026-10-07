"""The wiki file titles of pictures: a subject and a role.

A picture's title is ``<subject> <role>.png``. The subject is the entity's
image name without the characters that MediaWiki forbids in file names, so
every title can hold a file. The role says what the picture shows and whose
it is: the bot uploads icons and renders, and editors upload screenshots.
"""

from __future__ import annotations

from typing import Literal

__all__ = [
    "PictureRole",
    "picture_file_title",
    "picture_subject",
]

PictureRole = Literal["icon", "render", "screenshot"]

# Characters that MediaWiki forbids in file names or that wikitext reads as
# syntax inside a file link.
_FORBIDDEN = str.maketrans(dict.fromkeys(":|#<>[]{}"))


def picture_subject(*names: str | None) -> str:
    """Return the subject of an entity's pictures, or ``""`` when every name is empty.

    Callers pass the entity's image name first, then the names that stand in
    for it. The first name that keeps a character after the forbidden ones go
    becomes the subject, with runs of whitespace collapsed.
    """
    for name in names:
        subject = " ".join((name or "").translate(_FORBIDDEN).split())
        if subject:
            return subject
    return ""


def picture_file_title(role: PictureRole, *names: str | None) -> str:
    """Return the file title of an entity's picture in ``role``, or ``""`` without a subject."""
    subject = picture_subject(*names)
    return f"{subject} {role}.png" if subject else ""
