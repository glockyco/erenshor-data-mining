"""Parse the supported subset of the game's TextMeshPro markup."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Tone(StrEnum):
    NORMAL = "normal"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    DAMAGE = "damage"
    MUTED = "muted"
    EMPHASIS = "emphasis"
    MAGIC = "magic"
    ELEMENTAL = "elemental"
    VOID = "void"
    POISON = "poison"
    VALUE = "value"
    GOLD = "gold"
    BLESSED = "blessed"
    ASCENDED = "ascended"


_COLORS = {
    "white": Tone.NORMAL,
    "#ffffff": Tone.NORMAL,
    "green": Tone.POSITIVE,
    "#008000": Tone.POSITIVE,
    "#00ff00": Tone.POSITIVE,
    "#16ec00": Tone.POSITIVE,
    "#50c878": Tone.POISON,
    "red": Tone.DAMAGE,
    "#ff0000": Tone.NEGATIVE,
    "grey": Tone.MUTED,
    "gray": Tone.MUTED,
    "#808080": Tone.MUTED,
    "yellow": Tone.EMPHASIS,
    "#ffff00": Tone.EMPHASIS,
    "#8080ff": Tone.MAGIC,
    "#b030b0": Tone.VOID,
    "#ffa500": Tone.ELEMENTAL,
    "#606b80": Tone.MUTED,
    "#c3c8d9": Tone.NORMAL,
    "#9fbdc5": Tone.NORMAL,
    "#fff7a0": Tone.VALUE,
    "#cfa54b": Tone.GOLD,
    "#00faff": Tone.BLESSED,
    "#fc88ff": Tone.ASCENDED,
}
_TOKEN = re.compile(r"</?[a-zA-Z][^<>\r\n]*>|\r\n|\n|\r")


@dataclass(frozen=True, slots=True)
class Span:
    text: str
    tone: Tone
    italic: bool = False


Lines = tuple[tuple[Span, ...], ...]


def _tone(color: str, fail: str) -> Tone:
    token = color.lower()
    if re.fullmatch(r"#[0-9a-f]{8}", token):
        token = token[:7]
    if token not in _COLORS:
        raise ValueError(f"{fail}: unsupported TMP color {color!r}")
    return _COLORS[token]


def parse_tmp(
    text: str,
    *,
    source: str,
    stable_key: str,
    field: str,
    color: str = "FFFFFFFF",
    face_color: str = "FFFFFFFF",
    italic: bool = False,
) -> Lines:
    """Keep blank lines and ordered styled text, rejecting unsupported tags."""
    context = f"{stable_key} {source}.{field} ({text!r})"
    base_color = color if face_color.upper() == "FFFFFFFF" else face_color
    tone = _tone(f"#{base_color}", context) if text else Tone.NORMAL
    lines: list[list[Span]] = [[]]
    stack: list[tuple[str, Tone, bool]] = []
    cursor = 0

    def append(value: str) -> None:
        if re.search(r"</?[a-zA-Z]", value):
            raise ValueError(f"{context}: malformed TMP token {value!r}")
        if value:
            line = lines[-1]
            if line and line[-1].tone == tone and line[-1].italic == italic:
                line[-1] = Span(line[-1].text + value, tone, italic)
            else:
                line.append(Span(value, tone, italic))

    for match in _TOKEN.finditer(text):
        append(text[cursor : match.start()])
        token = match[0]
        cursor = match.end()
        if token in ("\r\n", "\n", "\r", "<br>"):
            lines.append([])
        elif token.startswith("<color="):
            stack.append(("color", tone, italic))
            tone = _tone(token[7:-1], context)
        elif token == "<i>":
            stack.append(("i", tone, italic))
            italic = True
        elif token in ("</color>", "</i>") and stack and stack[-1][0] == token[2:-1]:
            _, tone, italic = stack.pop()
        else:
            raise ValueError(f"{context}: unsupported or mismatched TMP token {token!r}")
    append(text[cursor:])
    if any(tag != "color" for tag, _, _ in stack):
        raise ValueError(f"{context}: unclosed TMP italic span")
    return tuple(tuple(line) for line in lines)
