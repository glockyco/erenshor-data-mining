"""The tooltip gadget's classes have rules in the wiki stylesheet."""

from __future__ import annotations

import re
from pathlib import Path

GADGETS = Path(__file__).resolve().parents[2] / "wiki" / "gadgets"


def test_every_class_the_tooltip_script_sets_has_a_style_rule() -> None:
    script = (GADGETS / "item-tooltips.js").read_text(encoding="utf-8")
    stylesheet = (GADGETS / "erenshor.css").read_text(encoding="utf-8")

    assigned = {
        name
        for value in re.findall(r"className = '([^']+)'", script)
        for name in value.split()
        if name.startswith("erenshor-")
    }

    assert assigned, "the script no longer sets any erenshor- class"
    missing = sorted(name for name in assigned if not re.search(rf"\.{re.escape(name)}\b", stylesheet))
    assert missing == []
