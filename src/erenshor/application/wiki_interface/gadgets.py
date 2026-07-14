"""Declarative ownership and rendering for MediaWiki gadget pages.

The repository owns a small set of pages below ``MediaWiki:Gadget-*``.  This
module keeps their definition line and source-page mapping in one validated
TOML specification rather than making deployment code discover files
implicitly.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Literal, cast

GadgetContentModel = Literal["css", "javascript", "json", "vue"]

_GADGET_ROOT = Path("wiki") / "gadgets"
_SUPPORTED_SUFFIXES = frozenset({".css", ".js", ".json", ".vue"})
_CONTENT_MODELS: dict[str, GadgetContentModel] = {
    ".css": "css",
    ".js": "javascript",
    ".json": "json",
    ".vue": "vue",
}
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_OPTION_PATTERN = re.compile(r"^[^|\[\]\r\n]+$")
_DEFINITION_NAME_PATTERN = re.compile(r"^[ \t]*\*(?!\*)[ \t]*(?P<name>[A-Za-z0-9][A-Za-z0-9_-]*)(?=[ \t]*(?:\[|\||$))")


@dataclass(frozen=True, slots=True)
class GadgetDefinition:
    """One gadget's ordered ResourceLoader options and source filenames."""

    name: str
    options: tuple[str, ...]
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GadgetSpec:
    """Validated, immutable repository gadget specification."""

    gadgets: tuple[GadgetDefinition, ...]
    owned_names: tuple[str, ...]

    @property
    def managed_names(self) -> tuple[str, ...]:
        """Return active gadget names in declaration order."""
        return tuple(gadget.name for gadget in self.gadgets)


@dataclass(frozen=True, slots=True)
class GadgetSourcePage:
    """One source file as a MediaWiki interface page."""

    title: str
    source_path: Path
    content_model: GadgetContentModel


class GadgetSpecError(ValueError):
    """Raised when the gadget specification violates repository invariants."""


def load_gadget_spec(repo_root: Path) -> GadgetSpec:
    """Load and validate ``wiki/gadgets/gadgets.toml`` under ``repo_root``."""
    spec_path = repo_root / _GADGET_ROOT / "gadgets.toml"
    try:
        raw = tomllib.loads(spec_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise GadgetSpecError(f"invalid gadget TOML at {spec_path}: {error}") from error

    if set(raw) != {"owned_names", "gadgets"}:
        unexpected = sorted(set(raw) - {"owned_names", "gadgets"})
        missing_keys = sorted({"owned_names", "gadgets"} - set(raw))
        details = []
        if missing_keys:
            details.append(f"missing {', '.join(missing_keys)}")
        if unexpected:
            details.append(f"unknown top-level keys: {', '.join(unexpected)}")
        raise GadgetSpecError("; ".join(details))

    raw_owned_names = raw["owned_names"]
    if not isinstance(raw_owned_names, list) or not all(isinstance(name, str) for name in raw_owned_names):
        raise GadgetSpecError("owned_names must be an array of strings")
    owned_names = tuple(cast("list[str]", raw_owned_names))
    if not owned_names:
        raise GadgetSpecError("owned_names must not be empty")

    raw_gadgets = raw["gadgets"]
    if not isinstance(raw_gadgets, list):
        raise GadgetSpecError("gadgets must be an array of tables")

    definitions: list[GadgetDefinition] = []
    for index, raw_gadget in enumerate(raw_gadgets):
        if not isinstance(raw_gadget, dict):
            raise GadgetSpecError(f"gadgets[{index}] must be a table")
        if set(raw_gadget) != {"name", "options", "sources"}:
            raise GadgetSpecError(f"gadgets[{index}] must contain only name, options, and sources")
        name = raw_gadget["name"]
        options = raw_gadget["options"]
        sources = raw_gadget["sources"]
        if not isinstance(name, str):
            raise GadgetSpecError(f"gadgets[{index}].name must be a string")
        if not isinstance(options, list) or not all(isinstance(option, str) for option in options):
            raise GadgetSpecError(f"gadgets[{index}].options must be an array of strings")
        if not isinstance(sources, list) or not all(isinstance(source, str) for source in sources):
            raise GadgetSpecError(f"gadgets[{index}].sources must be an array of strings")
        definitions.append(
            GadgetDefinition(
                name=name,
                options=tuple(cast("list[str]", options)),
                sources=tuple(cast("list[str]", sources)),
            )
        )

    spec = GadgetSpec(gadgets=tuple(definitions), owned_names=owned_names)
    _validate_spec_structure(spec)
    _validate_files(spec, repo_root)
    return spec


def gadget_source_pages(spec: GadgetSpec, repo_root: Path) -> tuple[GadgetSourcePage, ...]:
    """Map every declared source to its MediaWiki title and content model."""
    _validate_spec_structure(spec)
    _validate_files(spec, repo_root)
    pages: list[GadgetSourcePage] = []
    for gadget in spec.gadgets:
        for source in gadget.sources:
            source_path = _GADGET_ROOT / Path(source)
            suffix = source_path.suffix
            pages.append(
                GadgetSourcePage(
                    title=f"MediaWiki:Gadget-{source_path.as_posix().removeprefix('wiki/gadgets/')}",
                    source_path=source_path,
                    content_model=_CONTENT_MODELS[suffix],
                )
            )
    return tuple(pages)


def render_definition_lines(spec: GadgetSpec) -> tuple[str, ...]:
    """Render canonical ``MediaWiki:Gadgets-definition`` lines."""
    _validate_spec_structure(spec)
    return tuple(f"* {gadget.name}[{'|'.join(gadget.options)}]|{'|'.join(gadget.sources)}" for gadget in spec.gadgets)


def reconcile_definition(existing: str, spec: GadgetSpec) -> str:
    """Replace managed gadget lines while preserving unrelated definition lines."""
    rendered = render_definition_lines(spec)
    owned_names = frozenset(spec.owned_names)
    existing_lines = existing.splitlines(keepends=True)
    owned_indexes = [index for index, line in enumerate(existing_lines) if _definition_line_name(line) in owned_names]

    if owned_indexes:
        first = owned_indexes[0]
        line_ending = _line_ending(existing_lines[first])
        replacement = [f"{line}{line_ending}" for line in rendered]
        result_lines = (
            existing_lines[:first]
            + replacement
            + [line for index, line in enumerate(existing_lines) if index not in owned_indexes and index > first]
        )
    else:
        line_ending = _preferred_line_ending(existing_lines)
        result_lines = list(existing_lines)
        if result_lines and not _has_line_ending(result_lines[-1]):
            result_lines.append(line_ending)
        result_lines.extend(f"{line}{line_ending}" for line in rendered)

    return "".join(result_lines)


def _validate_spec_structure(spec: GadgetSpec) -> None:
    if not isinstance(spec.owned_names, tuple):
        raise GadgetSpecError("owned_names must be a tuple")
    if not spec.owned_names:
        raise GadgetSpecError("owned_names must not be empty")
    owned_names: set[str] = set()
    for name in spec.owned_names:
        if not isinstance(name, str) or not _NAME_PATTERN.fullmatch(name):
            raise GadgetSpecError(f"invalid owned gadget name: {name!r}")
        if name in owned_names:
            raise GadgetSpecError(f"duplicate owned gadget name: {name}")
        owned_names.add(name)

    names: set[str] = set()
    sources: set[str] = set()
    for index, gadget in enumerate(spec.gadgets):
        if not isinstance(gadget, GadgetDefinition):
            raise GadgetSpecError(f"gadgets[{index}] is not a GadgetDefinition")
        if not _NAME_PATTERN.fullmatch(gadget.name):
            raise GadgetSpecError(f"invalid gadget name: {gadget.name!r}")
        if gadget.name in names:
            raise GadgetSpecError(f"duplicate gadget name: {gadget.name}")
        if gadget.name not in owned_names:
            raise GadgetSpecError(f"active gadget is not listed in owned_names: {gadget.name}")
        names.add(gadget.name)
        if not gadget.options:
            raise GadgetSpecError(f"gadget {gadget.name} must declare options")
        if len(set(gadget.options)) != len(gadget.options):
            raise GadgetSpecError(f"gadget {gadget.name} has duplicate options")
        for option in gadget.options:
            if not isinstance(option, str) or not option or not _OPTION_PATTERN.fullmatch(option):
                raise GadgetSpecError(f"invalid option in gadget {gadget.name}: {option!r}")
        if not gadget.sources:
            raise GadgetSpecError(f"gadget {gadget.name} must declare sources")
        for source in gadget.sources:
            relative = _safe_source_path(source)
            normalized = relative.as_posix()
            if normalized in sources:
                raise GadgetSpecError(f"duplicate gadget source: {source}")
            sources.add(normalized)
        if "type=styles" in gadget.options and any(Path(source).suffix != ".css" for source in gadget.sources):
            raise GadgetSpecError(f"gadget {gadget.name} uses type=styles with a non-CSS source")


def _validate_files(spec: GadgetSpec, repo_root: Path) -> None:
    gadget_root = (repo_root / _GADGET_ROOT).resolve()
    declared = {source for gadget in spec.gadgets for source in gadget.sources}
    for source in declared:
        relative = _safe_source_path(source)
        source_path = repo_root / _GADGET_ROOT / relative
        resolved = source_path.resolve()
        try:
            resolved.relative_to(gadget_root)
        except ValueError as error:
            raise GadgetSpecError(f"gadget source escapes wiki/gadgets: {source}") from error
        if not source_path.is_file():
            raise GadgetSpecError(f"gadget source does not exist: {source}")
        if source_path.suffix not in _SUPPORTED_SUFFIXES:
            raise GadgetSpecError(f"unsupported gadget source suffix: {source}")

    owned_files = {
        path.relative_to(repo_root / _GADGET_ROOT).as_posix()
        for path in (repo_root / _GADGET_ROOT).rglob("*")
        if path.is_file() and path.suffix in _SUPPORTED_SUFFIXES
    }
    undeclared = sorted(owned_files - declared)
    if undeclared:
        raise GadgetSpecError(f"gadget source files are not allowlisted: {', '.join(undeclared)}")


def _safe_source_path(source: str) -> Path:
    if not isinstance(source, str) or not source or "\\" in source:
        raise GadgetSpecError(f"gadget source must be a safe relative path: {source!r}")
    relative = Path(source)
    windows = PureWindowsPath(source)
    if (
        relative.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise GadgetSpecError(f"gadget source must be a safe relative path: {source!r}")
    if relative.suffix not in _SUPPORTED_SUFFIXES:
        raise GadgetSpecError(f"unsupported gadget source suffix: {source}")
    return relative


def _definition_line_name(line: str) -> str | None:
    text = line.rstrip("\r\n")
    match = _DEFINITION_NAME_PATTERN.match(text)
    return match.group("name") if match else None


def _has_line_ending(line: str) -> bool:
    return line.endswith(("\n", "\r"))


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[-1]
    return "\n"


def _preferred_line_ending(lines: list[str]) -> str:
    for line in lines:
        if _has_line_ending(line):
            return _line_ending(line)
    return "\n"
