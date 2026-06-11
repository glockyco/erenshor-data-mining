"""Every code-fact reference in the codebase must name a real spec id,
and every assert-mode spec must be referenced by at least one consumer."""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPECS = REPO_ROOT / "src" / "tools" / "CodeFacts" / "specs" / "erenshor-facts.json"
REF = re.compile(r"(?:#|--)\s*code-fact:\s*([a-z0-9_.]+)")
SCAN_ROOTS = ["src/erenshor", "wiki/modules"]


def _references() -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for root in SCAN_ROOTS:
        for path in (REPO_ROOT / root).rglob("*"):
            if path.suffix not in {".py", ".lua"}:
                continue
            for m in REF.finditer(path.read_text(errors="ignore")):
                refs.setdefault(m.group(1), []).append(str(path.relative_to(REPO_ROOT)))
    return refs


def test_all_references_resolve_and_asserts_are_consumed() -> None:
    spec_ids = {f["id"]: f["mode"] for f in json.loads(SPECS.read_text())["facts"]}
    refs = _references()
    unknown = set(refs) - set(spec_ids)
    assert not unknown, f"code-fact comments referencing unknown spec ids: {unknown}"
    unconsumed_asserts = {i for i, mode in spec_ids.items() if mode == "assert" and i not in refs}
    assert not unconsumed_asserts, (
        f"assert specs with no consumer reference: {unconsumed_asserts} "
        "(tag the re-implementing code with a code-fact comment)"
    )
