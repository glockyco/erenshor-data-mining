"""Generated data views: one checked data module for each view.

A view is a list that spans entities, such as a vendor's stock. Its data module
maps the stable key of each entity whose page shows the view to that entity's
rows. Rows hold stable keys and plain values. A native identity reference carries
its label and optional page when it may lack an article. Page-backed references
still require a matching entry in ``Module:Erenshor/Data/Links``.

Each view declares its fields once. The declaration opens the module as a
comment, so the description editors read cannot drift from the rows, and
generation checks every row against it.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from erenshor.application.wiki_lua.lua_writer import module_text

FieldType = Literal["key", "keys", "reference", "references", "text", "integer", "number", "boolean"]

_TYPE_NAMES: Mapping[FieldType, str] = {
    "key": "stable key",
    "keys": "list of stable keys",
    "reference": "native identity with a label and optional page",
    "references": "list of native identities with labels and optional pages",
    "text": "text",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
}
_MARKUP = re.compile(r"\[\[|\]\]|\{\{|\}\}|[<>]")
_LINE_BREAK = re.compile(r"[\r\n]")


class ViewDataError(ValueError):
    """Raised when a view's rows break its declaration."""


@dataclass(frozen=True)
class ViewField:
    """One field of a view row: its name in the row, its type, and its meaning."""

    name: str
    type: FieldType
    meaning: str
    optional: bool = False


@dataclass(frozen=True)
class DataView:
    """A generated data module of rows keyed by the entity whose page shows them."""

    module: str
    description: str
    entity: str
    fields: tuple[ViewField, ...]

    @property
    def title(self) -> str:
        return f"Module:Erenshor/Data/{self.module}"


def view_module_text(
    view: DataView,
    rows_by_entity: Mapping[str, Sequence[Mapping[str, object]]],
    known_keys: Collection[str],
    *,
    reference_catalog: Mapping[str, Mapping[str, object]] | None = None,
    entity_keys: Collection[str] | None = None,
) -> str:
    """Return the module text of a view after checking every row against its declaration."""
    for entity_key, rows in rows_by_entity.items():
        if entity_key not in (known_keys if entity_keys is None else entity_keys):
            raise ViewDataError(f"{view.title}: {view.entity} key {entity_key!r} is not in the link catalog")
        for index, row in enumerate(rows, start=1):
            _check_row(view, entity_key, index, row, known_keys, reference_catalog)
    data = {entity_key: list(rows) for entity_key, rows in sorted(rows_by_entity.items())}
    return _header(view) + module_text(data)


def _check_row(
    view: DataView,
    entity_key: str,
    index: int,
    row: Mapping[str, object],
    known_keys: Collection[str],
    reference_catalog: Mapping[str, Mapping[str, object]] | None,
) -> None:
    where = f"{view.title}: row {index} of {entity_key}"
    if "way" in row:
        where += f" way {row['way']}"
    declared = {field.name: field for field in view.fields}
    for name in row:
        if name not in declared:
            raise ViewDataError(f"{where}: field {name!r} is not declared")
    for field in view.fields:
        value = row.get(field.name)
        if value is None:
            if not field.optional:
                raise ViewDataError(f"{where}: field {field.name!r} is missing")
            continue
        problem = _value_problem(field.type, value, known_keys, reference_catalog)
        if problem is not None:
            raise ViewDataError(f"{where}: field {field.name!r} {problem}")


def _value_problem(
    field_type: FieldType,
    value: object,
    known_keys: Collection[str],
    reference_catalog: Mapping[str, Mapping[str, object]] | None,
) -> str | None:
    if field_type in {"reference", "references"}:
        return _reference_values_problem(field_type, value, known_keys, reference_catalog)
    if field_type == "keys":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return f"must be a {_TYPE_NAMES[field_type]}, not {value!r}"
        return next((problem for item in value if (problem := _key_problem(item, known_keys))), None)
    if not _has_type(field_type, value):
        return f"must be {_TYPE_NAMES[field_type]}, not {type(value).__name__} {value!r}"
    if field_type == "key":
        return _key_problem(str(value), known_keys)
    return _text_problem(str(value)) if field_type == "text" else None


def native_reference(key: str, catalog: Mapping[str, Mapping[str, object]], *, kind: str) -> dict[str, object]:
    """Retain a native identity and omit its page only when it has none."""
    if not key.startswith(kind + ":"):
        raise ViewDataError(f"Native {kind} reference has the wrong kind: {key!r}")
    if key not in catalog:
        raise ViewDataError(f"unknown native {kind} {key!r}")
    entry = catalog[key]
    reference: dict[str, object] = {"key": key, "name": entry.get("name")}
    if entry.get("page") is not None:
        reference["page"] = entry["page"]
    return reference


def _reference_values_problem(
    field_type: FieldType,
    value: object,
    known_keys: Collection[str],
    catalog: Mapping[str, Mapping[str, object]] | None,
) -> str | None:
    if field_type == "reference":
        return _reference_problem(value, known_keys, catalog)
    if not isinstance(value, list):
        return f"must be a {_TYPE_NAMES[field_type]}, not {value!r}"
    return next((problem for item in value if (problem := _reference_problem(item, known_keys, catalog))), None)


def _reference_problem(
    value: object,
    known_keys: Collection[str],
    catalog: Mapping[str, Mapping[str, object]] | None,
) -> str | None:
    if not isinstance(value, Mapping):
        return "must be a native identity reference"
    key = value.get("key")
    if not isinstance(key, str) or catalog is None or key not in catalog:
        return f"holds unknown native identity {key!r}"
    entry = catalog[key]
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        return f"native identity {key!r} has no label"
    if problem := _text_problem(name):
        return problem
    expected: dict[str, object] = {"key": key, "name": name}
    if entry.get("page") is not None:
        if problem := _key_problem(key, known_keys):
            return problem
        expected["page"] = entry["page"]
    return None if value == expected else f"does not match native identity {key!r}"


def _has_type(field_type: FieldType, value: object) -> bool:
    # bool is an int in Python, so it is excluded from both number types.
    if field_type in ("key", "text"):
        return isinstance(value, str)
    if field_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, bool)


def _key_problem(key: str, known_keys: Collection[str]) -> str | None:
    return None if key in known_keys else f"holds {key!r}, which is not in the link catalog"


def _text_problem(text: str) -> str | None:
    if _LINE_BREAK.search(text):
        return f"holds a line break: {text!r}"
    if _MARKUP.search(text):
        return f"holds wiki markup: {text!r}"
    return None


def _header(view: DataView) -> str:
    lines = [
        f"-- {view.title}",
        "-- Generated by `erenshor wiki generate-lua`. The bot overwrites every edit of this page.",
        f"-- {view.description}",
        f"-- Keys are {view.entity} stable keys. Each maps to a list of rows with these fields:",
        *(
            f"--   {field.name} ({_TYPE_NAMES[field.type]}{', optional' if field.optional else ''}): {field.meaning}"
            for field in view.fields
        ),
    ]
    return "\n".join(lines) + "\n"
