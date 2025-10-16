from __future__ import annotations

from typing import Any, Dict, List

import mwparserfromhell as mw

__all__ = [
    "find_templates",
    "parse",
    "replace_template_with_text",
    "template_params",
]


def parse(text: str) -> Any:  # returns Wikicode
    """Parse wikitext using mwparserfromhell.

    Returns:
        Wikicode object from mwparserfromhell
    """
    return mw.parse(text)


def find_templates(code: Any, names: List[str]) -> List[Any]:
    target = {n.lower() for n in names}
    return [t for t in code.filter_templates() if str(t.name).strip().lower() in target]


def template_params(tmpl: Any) -> Dict[str, str]:
    params: Dict[str, str] = {}
    for p in tmpl.params:
        params[str(p.name).strip()] = str(p.value).strip()
    return params


def replace_template_with_text(code: Any, tmpl: Any, new_text: str) -> str:
    code.replace(tmpl, new_text)
    return str(code)
