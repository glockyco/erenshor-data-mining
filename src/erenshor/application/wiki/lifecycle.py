"""Reviewed lifecycle facts for historical, renamed, and split wiki pages."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast
from urllib.parse import urlsplit

import mwparserfromhell

LifecycleState = Literal["removed", "unobtainable", "unused"]
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


@dataclass(frozen=True, slots=True)
class LifecyclePage:
    title: str
    stable_key: str | None
    state: LifecycleState
    thing: str
    update: str | None
    date: str | None
    patch_notes_url: str | None
    source: str
    chat: bool = False


@dataclass(frozen=True, slots=True)
class LifecycleRename:
    old_title: str
    stable_key: str
    current_title: str
    source: str


@dataclass(frozen=True, slots=True)
class LifecycleSplit:
    old_title: str
    current_titles: tuple[str, ...]
    stable_keys: tuple[str, ...]
    source: str


@dataclass(frozen=True, slots=True)
class ContentLifecycle:
    pages: Mapping[str, LifecyclePage]
    renames: Mapping[str, LifecycleRename]
    splits: Mapping[str, LifecycleSplit]


def _required_string(value: object, entry: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{entry}: {field} must be a nonempty string")
    return value


def _optional_string(value: object, entry: str, field: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, entry, field)


def _record(value: object, entry: str, fields: set[str], optional: frozenset[str] = frozenset()) -> dict[str, object]:
    if not isinstance(value, dict) or not fields <= set(value) <= fields | optional:
        expected = ", ".join(sorted(fields))
        if optional:
            expected += f", and optionally {', '.join(sorted(optional))}"
        raise ValueError(f"{entry}: expected fields {expected}")
    return value


def load_content_lifecycle(path: Path) -> ContentLifecycle:
    """Read reviewed facts and reject malformed or contradictory records."""
    data = json.loads(path.read_text(encoding="utf-8"))
    root = _record(data, str(path), {"pages", "renames", "splits"})
    raw_pages = root["pages"]
    raw_renames = root["renames"]
    raw_splits = root["splits"]
    if not isinstance(raw_pages, dict) or not isinstance(raw_renames, dict) or not isinstance(raw_splits, dict):
        raise ValueError(f"{path}: pages, renames, and splits must be objects")

    pages: dict[str, LifecyclePage] = {}
    for title, value in raw_pages.items():
        entry = f"pages[{title!r}]"
        _required_string(title, entry, "title")
        record = _record(
            value,
            entry,
            {"stable_key", "state", "thing", "update", "date", "patch_notes_url", "source"},
            frozenset({"chat"}),
        )
        state = cast("LifecycleState", record["state"])
        if state not in ("removed", "unobtainable", "unused"):
            raise ValueError(f"{entry}: unknown state {state!r}")
        stable_key = _optional_string(record["stable_key"], entry, "stable_key")
        thing = _required_string(record["thing"], entry, "thing")
        update = _optional_string(record["update"], entry, "update")
        release_date = _optional_string(record["date"], entry, "date")
        if release_date is not None:
            if not _DATE_PATTERN.fullmatch(release_date):
                raise ValueError(f"{entry}: malformed date {release_date!r}")
            try:
                date.fromisoformat(release_date)
            except ValueError as error:
                raise ValueError(f"{entry}: malformed date {release_date!r}") from error
        if update and not release_date:
            raise ValueError(f"{entry}: update requires a date")
        patch_notes_url = _optional_string(record["patch_notes_url"], entry, "patch_notes_url")
        if patch_notes_url:
            parsed = urlsplit(patch_notes_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError(f"{entry}: patch_notes_url must be an https link")
        source = _required_string(record["source"], entry, "source")
        chat = "chat" in record
        if chat and record["chat"] is not True:
            raise ValueError(f"{entry}: chat must be true when present")
        if chat and state != "unused":
            raise ValueError(f"{entry}: chat applies only to unused content")
        pages[title] = LifecyclePage(
            title, stable_key, state, thing, update, release_date, patch_notes_url, source, chat
        )

    renames: dict[str, LifecycleRename] = {}
    for old_title, value in raw_renames.items():
        entry = f"renames[{old_title!r}]"
        _required_string(old_title, entry, "old_title")
        record = _record(value, entry, {"stable_key", "current_title", "source"})
        if old_title in pages:
            raise ValueError(f"{entry}: title is both a page and a rename")
        stable_key = _required_string(record["stable_key"], entry, "stable_key")
        current_title = _required_string(record["current_title"], entry, "current_title")
        if old_title == current_title:
            raise ValueError(f"{entry}: current_title must differ from old title")
        source = _required_string(record["source"], entry, "source")
        renames[old_title] = LifecycleRename(old_title, stable_key, current_title, source)

    splits: dict[str, LifecycleSplit] = {}
    for old_title, value in raw_splits.items():
        entry = f"splits[{old_title!r}]"
        _required_string(old_title, entry, "old_title")
        record = _record(value, entry, {"current_titles", "stable_keys", "source"})
        if old_title in pages or old_title in renames:
            raise ValueError(f"{entry}: title is also a page or rename")
        raw_titles = record["current_titles"]
        raw_keys = record["stable_keys"]
        if not isinstance(raw_titles, list) or not raw_titles:
            raise ValueError(f"{entry}: current_titles must be a nonempty list")
        titles = tuple(_required_string(title, entry, "current_titles") for title in raw_titles)
        if len(set(titles)) != len(titles):
            raise ValueError(f"{entry}: current_titles contains duplicates")
        if not isinstance(raw_keys, list) or len(raw_keys) != len(titles):
            raise ValueError(f"{entry}: stable_keys must match current_titles count")
        keys = tuple(_required_string(key, entry, "stable_keys") for key in raw_keys)
        if old_title in titles:
            raise ValueError(f"{entry}: old title cannot be a current title")
        source = _required_string(record["source"], entry, "source")
        splits[old_title] = LifecycleSplit(old_title, titles, keys, source)

    return ContentLifecycle(MappingProxyType(pages), MappingProxyType(renames), MappingProxyType(splits))


def render_split_disambiguation(split: LifecycleSplit) -> str:
    """Render a former title with links to every current variant."""
    variants = "\n".join(f"* [[{title}]]" for title in split.current_titles)
    return f"{split.old_title} may refer to:\n\n{variants}\n\n__DISAMBIG__\n"


def validate_generated_lifecycle(pages: Mapping[str, Sequence[str]], lifecycle: ContentLifecycle) -> None:
    """Reject reviewed identities that conflict with the complete generation."""
    for title, fact in lifecycle.pages.items():
        keys = pages.get(title)
        if keys is not None and (fact.stable_key is None or fact.stable_key not in keys):
            raise ValueError(f"{title}: recorded lifecycle identity conflicts with generated page")
    for old_title, rename in lifecycle.renames.items():
        if old_title in pages:
            raise ValueError(f"{old_title}: renamed title is still generated")
        if rename.stable_key not in pages.get(rename.current_title, ()):
            raise ValueError(f"{old_title}: {rename.current_title} does not generate {rename.stable_key}")
    for old_title, split in lifecycle.splits.items():
        if old_title in pages:
            raise ValueError(f"{old_title}: split title is still generated")
        for title, key in zip(split.current_titles, split.stable_keys, strict=True):
            if key not in pages.get(title, ()):
                raise ValueError(f"{old_title}: {title} does not generate {key}")


def apply_lifecycle_fields(title: str, stable_keys: Sequence[str], content: str, lifecycle: ContentLifecycle) -> str:
    """Add reviewed fields to matching generated article roots, not their prose."""
    fact = lifecycle.pages.get(title)
    former_names = [
        rename.old_title
        for rename in lifecycle.renames.values()
        if rename.current_title == title and rename.stable_key.startswith("item:") and rename.stable_key in stable_keys
    ]
    if fact is None and not former_names:
        return content
    if fact is not None and (fact.stable_key is None or fact.stable_key not in stable_keys):
        raise ValueError(f"{title}: recorded lifecycle identity conflicts with generated page")
    if fact is not None and fact.chat:
        raise ValueError(f"{title}: the chat flag applies only to pages that generation does not write")

    code = mwparserfromhell.parse(content)
    matched_fact = False
    matched_renames: set[str] = set()
    for template in code.filter_templates(recursive=False):
        name = str(template.name).strip()
        if name not in {"Item", "Ability"} or not template.has("stablekey"):
            continue
        key = str(template.get("stablekey").value).strip()
        if fact is not None and key == fact.stable_key:
            matched_fact = True
            template.add("historical_state", fact.state)
            if name == "Ability":
                template.add("historical_thing", fact.thing)
            if fact.update is not None:
                template.add("historical_update", fact.update)
            if fact.date is not None:
                release_date = date.fromisoformat(fact.date)
                template.add(
                    "historical_date",
                    f"{release_date.strftime('%B')} {release_date.day}, {release_date.year}",
                )
            if fact.patch_notes_url is not None:
                template.add("historical_url", fact.patch_notes_url)
        if name == "Item":
            for rename in lifecycle.renames.values():
                if rename.current_title == title and rename.stable_key == key:
                    matched_renames.add(rename.old_title)
                    template.add("aka", rename.old_title)

    if fact is not None and not matched_fact:
        raise ValueError(f"{title}: no generated Item or Ability root matches {fact.stable_key}")
    if set(former_names) != matched_renames:
        raise ValueError(f"{title}: no generated Item root matches recorded rename")
    return str(code)
