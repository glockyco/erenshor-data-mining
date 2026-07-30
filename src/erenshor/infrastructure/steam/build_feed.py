"""Resolve Steam build publication times from SteamDB's build RSS feed.

The Steam appmanifest ``LastUpdated`` field records when the local Steam client
last downloaded a build, not when Valve published it. For build 24362350, the
measured drift was 7.5 hours: the local value was
2026-07-24T05:24:35Z while the authoritative publish time was
2026-07-23T21:53:44Z. This undocumented SteamDB endpoint may omit old builds or
be unavailable, so a NULL result is an expected outcome rather than an error.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

_FEED_URL = "https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
_BUILD_GUID = re.compile(r"build#(\d+)")
_BUILD_DESCRIPTION_SUFFIX = re.compile(r"\s*(?:\(\s*)?SteamDB Build (\d+)\s*\)?\s*$")


@dataclass(frozen=True)
class Build:
    """One SteamDB build-feed item."""

    build_id: str
    published_at: datetime
    notes_title: str | None
    url: str


def _text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(item: ET.Element, name: str) -> str:
    for child in item:
        if _local_name(child.tag) == name:
            return _text(child)
    return ""


def _notes_title(description: str, build_id: str) -> str | None:
    match = _BUILD_DESCRIPTION_SUFFIX.search(description)
    if match is None or match.group(1) != build_id:
        title = description.strip()
    else:
        title = description[: match.start()].strip()
    return title or None


def parse_build_feed(xml: str) -> list[Build]:
    """Parse build entries from RSS XML, sorted newest first.

    Invalid XML, empty documents, and individual items without a valid build
    guid or publication date are ignored so one bad feed item does not discard
    usable build records.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []

    builds: list[Build] = []
    for item in root.iter():
        if _local_name(item.tag) != "item":
            continue
        guid_match = _BUILD_GUID.fullmatch(_child_text(item, "guid"))
        if guid_match is None:
            continue
        pub_date = _child_text(item, "pubDate")
        if not pub_date:
            continue
        try:
            published_at = parsedate_to_datetime(pub_date)
        except (TypeError, ValueError, OverflowError):
            continue
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        else:
            published_at = published_at.astimezone(UTC)
        build_id = guid_match.group(1)
        builds.append(
            Build(
                build_id=build_id,
                published_at=published_at,
                notes_title=_notes_title(_child_text(item, "description"), build_id),
                url=_child_text(item, "link"),
            )
        )
    builds.sort(key=lambda build: build.published_at, reverse=True)
    return builds


def fetch_build_feed(app_id: str, *, timeout: float = 15.0) -> list[Build]:
    """Fetch and parse SteamDB's undocumented build feed for ``app_id``."""
    response = httpx.get(
        _FEED_URL.format(app_id=app_id),
        headers={"User-Agent": _USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_build_feed(response.text)


def resolve_build_published_at(builds: list[Build], build_id: str) -> datetime | None:
    """Return the publication time for an exact build-id match, if present."""
    return next((build.published_at for build in builds if build.build_id == build_id), None)
