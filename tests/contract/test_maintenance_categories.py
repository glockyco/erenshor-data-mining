"""Every maintenance category that a repository module adds has its page and its guide row.

A module that flags a page with a `Pages with ...` category leaves editors with
a red category link and no instructions unless the repository also owns the
hidden category page and the Game Data guide lists the category with its fix.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_CATEGORY = re.compile(r"\[\[Category:(Pages with [^\]|]+)\]\]")


def _maintenance_categories() -> set[str]:
    sources = [*(REPO_ROOT / "wiki" / "modules").rglob("*.lua"), *(REPO_ROOT / "wiki" / "templates").rglob("*.wiki")]
    return {
        name
        for path in sources
        if not path.stem.endswith("testcases")
        for name in _CATEGORY.findall(path.read_text(encoding="utf-8"))
    }


def test_each_maintenance_category_has_a_hidden_page_and_a_guide_row() -> None:
    categories = _maintenance_categories()
    guide = (REPO_ROOT / "wiki" / "content" / "Erenshor Wiki" / "Game Data.wiki").read_text(encoding="utf-8")
    pages = REPO_ROOT / "wiki" / "content" / "Category"

    without_page = sorted(
        name
        for name in categories
        if not (pages / f"{name}.wiki").is_file()
        or "__HIDDENCAT__" not in (pages / f"{name}.wiki").read_text(encoding="utf-8")
    )
    without_row = sorted(name for name in categories if f"[[:Category:{name}]]" not in guide)

    assert len(categories) >= 8
    assert without_page == []
    assert without_row == []
