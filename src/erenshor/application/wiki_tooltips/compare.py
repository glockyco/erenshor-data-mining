"""Compare typed tooltip facts and keep every unmatched line visible."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any

from erenshor.application.wiki_tooltips.tmp import Lines, Span, Tone, parse_tmp

_QUALITY_NAMES = dict(
    zip(
        (1, 11, 12, 13, 14, 15, 2, 3),
        ("Standard", "Improved +1", "Improved +2", "Improved +3", "Improved +4", "Improved +5", "Blessed", "Ascended"),
        strict=True,
    )
)
_TICK_DAMAGE = re.compile(r"^Damage: [0-9]+(?:\.[0-9]+)? / tick$")
_KNOWN = re.compile(r"^YOU ALREADY KNOW THIS (?:SKILL|SPELL)$")
_HINTS = re.compile(r"^\(Hold (?:RIGHT MOUSE|CONTROL|DPAD DOWN) for details\)$")


@dataclass(frozen=True, slots=True)
class ObservedLine:
    source: str
    field: str
    index: int
    spans: tuple[Span, ...]

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)


def normalize_line(spans: tuple[Span, ...]) -> tuple[Span, ...]:
    """Normalize whitespace that HTML collapses, without normalizing tone or text."""
    parts: list[Span] = []
    pending_space = False
    for span in spans:
        for piece in re.findall(r"\s+|\S+", span.text):
            if piece.isspace():
                pending_space = bool(parts)
                continue
            if pending_space:
                last = parts[-1]
                parts[-1] = Span(last.text + " ", last.tone, last.italic)
                pending_space = False
            if parts and (parts[-1].tone, parts[-1].italic) == (span.tone, span.italic):
                last = parts[-1]
                parts[-1] = Span(last.text + piece, last.tone, last.italic)
            else:
                parts.append(Span(piece, span.tone, span.italic))
    return tuple(parts)


def read_game_window(window: dict[str, Any], stable_key: str) -> dict[str, Lines]:
    """Parse all active fields. Leave inactive raw buffers in the capture only."""
    fields: dict[str, Lines] = {}
    for name, field in window["fields"].items():
        if field["active"]:
            fields[name] = parse_tmp(
                field["text"],
                source=window["source"],
                stable_key=stable_key,
                field=name,
                color=field["color"],
                face_color=field["face_color"],
                italic=field["italic"],
            )
    return fields


def viewer_exclusion(line: ObservedLine, *, level_scaled_mana: bool) -> str | None:
    text = line.text
    if line.source == "ItemInfoWindow.DisplayItem":
        if line.field == "ReqLvl" and _KNOWN.fullmatch(text):
            return "viewer book knowledge"
        if line.field == "ClickDesc" and _HINTS.fullmatch(text):
            return "viewer controls"
        if line.field == "Lore" and text == "Use CTRL + CLICK to separate stacks.":
            return "viewer controls"
        if line.field == "OtherTextParent" and re.fullmatch(r"Base DPS: [0-9]+(?:\.[0-9]+)?", text):
            return "viewer Base DPS"
    if (
        line.source == "ItemInfoWindow.LoadSpellDetails"
        and line.field == "SpellDetailsDesc"
        and level_scaled_mana
        and re.fullmatch(r"Mana Regen [+-][0-9]+(?:\.[0-9]+)?", text)
    ):
        return "viewer level scaled Mana Regen"
    return None


def normalize_damage(line: ObservedLine) -> ObservedLine:
    """Apply the approved unit change only on a mechanical damage row."""
    if not _TICK_DAMAGE.fullmatch(line.text):
        return line
    spans = list(line.spans)
    tail = spans[-1]
    if not tail.text.endswith(" / tick"):
        raise ValueError(f"Damage units cross differently styled spans: {line.text}")
    spans[-1] = Span(tail.text.removesuffix(" / tick") + " / 3 sec", tail.tone, tail.italic)
    return ObservedLine(line.source, line.field, line.index, tuple(spans))


def line_differences(
    expected: list[ObservedLine],
    actual: list[ObservedLine],
) -> list[dict[str, Any]]:
    """Compare text and tone together and retain source line and field provenance."""
    matcher = SequenceMatcher(
        a=[normalize_line(line.spans) for line in expected],
        b=[normalize_line(line.spans) for line in actual],
        autojunk=False,
    )
    return [
        {"kind": tag, "game": [asdict(line) for line in expected[a:b]], "wiki": [asdict(line) for line in actual[c:d]]}
        for tag, a, b, c, d in matcher.get_opcodes()
        if tag != "equal"
    ]


def fixed_dps(damage: str, delay: str, slot: str) -> int:
    """Calculate the wiki's declared fixed DPS from captured weapon stats."""
    weapon_slot = slot.removesuffix(" - Relic Item")
    return math.ceil(float(damage) / float(delay) * (2 if weapon_slot.endswith(" - 2-Handed") else 1))


def quality_name(quantity: int) -> str:
    return _QUALITY_NAMES[quantity]


def lines_for(source: str, field: str, lines: Lines) -> list[ObservedLine]:
    return [ObservedLine(source, field, index, spans) for index, spans in enumerate(lines, 1)]


def label(text: str) -> tuple[Span, ...]:
    return (Span(text, Tone.NORMAL),)
