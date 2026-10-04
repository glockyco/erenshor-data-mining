"""Generated articles and repository templates call only repository templates."""

from __future__ import annotations

import re
from pathlib import Path

from erenshor.application.wiki.semantic_validation import GENERATED_TEMPLATES, SEMANTIC_LINK_TEMPLATES

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "wiki" / "templates"
JINJA_DIR = REPO_ROOT / "src" / "erenshor" / "application" / "wiki" / "generators" / "templates"

# A template call such as "{{Name|" or "{{Name}}". Parameters ("{{{name}}}") and parser
# functions ("{{#if:") do not match.
_TEMPLATE_CALL = re.compile(r"(?<!\{)\{\{(?!\{)\s*([^{}|#:\n][^{}|\n]*?)\s*(?:\||\}\})")
# Jinja templates write a template call as {{ "{{" }}Name.
_JINJA_TEMPLATE_CALL = re.compile(r'\{\{ "\{\{" \}\}([^|{}\n]+)')
_NOINCLUDE = re.compile(r"<noinclude>.*?</noinclude>", re.DOTALL)


def _repository_templates() -> set[str]:
    return {path.relative_to(TEMPLATES_DIR).with_suffix("").as_posix() for path in TEMPLATES_DIR.rglob("*.wiki")}


def _called_template(raw_name: str) -> str | None:
    """Return the template that a call names, or None for a magic word or parser function."""
    name = raw_name.strip()
    if name.startswith("Template:"):
        return name.removeprefix("Template:")
    if ":" in name or name.upper() == name:
        return None
    return name


def test_generated_articles_call_only_repository_templates() -> None:
    called = set(GENERATED_TEMPLATES) | set(SEMANTIC_LINK_TEMPLATES)
    for path in JINJA_DIR.glob("*.jinja2"):
        called.update(
            match.group(1).strip() for match in _JINJA_TEMPLATE_CALL.finditer(path.read_text(encoding="utf-8"))
        )

    unowned = sorted(called - _repository_templates())

    assert not unowned, "Generation calls templates that the repository does not own:\n" + "\n".join(unowned)


def test_repository_templates_call_only_repository_templates() -> None:
    owned = _repository_templates()
    unowned: list[str] = []
    for path in sorted(TEMPLATES_DIR.rglob("*.wiki")):
        if path.name == "doc.wiki":
            continue
        rendered_text = _NOINCLUDE.sub("", path.read_text(encoding="utf-8"))
        for match in _TEMPLATE_CALL.finditer(rendered_text):
            name = _called_template(match.group(1))
            if name is not None and name not in owned:
                unowned.append(f"{path.relative_to(REPO_ROOT)} calls Template:{name}")

    assert not unowned, "Repository templates call templates that the repository does not own:\n" + "\n".join(unowned)
