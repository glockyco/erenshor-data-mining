"""The Game Data guide states what the generator and the repository do."""

from __future__ import annotations

import re
from pathlib import Path

from erenshor.application.wiki.generators.field_preservation import DEFAULT_PRESERVATION_RULES

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE = REPO_ROOT / "wiki" / "content" / "Erenshor Wiki" / "Game Data.wiki"
TEMPLATES_DIR = REPO_ROOT / "wiki" / "templates"

# The guide states each preservation rule with one fixed label.
RULE_BY_LABEL = {
    "Kept": "preserve",
    "Kept, filled when blank": "prefer_manual",
    "Replaced, kept when the game has no value": "prefer_database",
    "Merged": "merge",
}
_FIELD_ROW = re.compile(r"^\|\s*([A-Za-z]+)\s*\|\|\s*<code>([^<]+)</code>\s*\|\|\s*(.+?)\s*$", re.MULTILINE)
_TEMPLATE_LINK = re.compile(r"\[\[Template:([^|\]]+)")


def _section(heading: str) -> str:
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index(f"== {heading} ==")
    end = text.find("\n== ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_guide_field_table_equals_the_preservation_rules() -> None:
    section = _section("Editing an article that the bot maintains")
    rows = [(match.group(1), match.group(2), match.group(3)) for match in _FIELD_ROW.finditer(section)]
    unknown_labels = sorted({label for _, _, label in rows if label not in RULE_BY_LABEL})
    assert not unknown_labels, f"Labels without a rule: {unknown_labels}"

    stated = {(template, field, RULE_BY_LABEL[label]) for template, field, label in rows}
    expected = {
        (template, field, rule)
        for template, fields in DEFAULT_PRESERVATION_RULES.items()
        for field, rule in fields.items()
        if rule != "override"
    }

    assert stated == expected, (
        f"Rules missing from the guide: {sorted(expected - stated)}\n"
        f"Rows that no rule backs: {sorted(stated - expected)}"
    )


def test_guide_lists_every_repository_template() -> None:
    section = _section("Templates that the project maintains")
    listed = {match.group(1) for match in _TEMPLATE_LINK.finditer(section)}
    owned = {
        path.relative_to(TEMPLATES_DIR).with_suffix("").as_posix()
        for path in TEMPLATES_DIR.rglob("*.wiki")
        if path.name != "doc.wiki"
    }

    assert listed == owned, (
        f"Templates missing from the guide: {sorted(owned - listed)}\n"
        f"Listed templates that do not exist: {sorted(listed - owned)}"
    )
