"""Deterministic Lua serialization for Scribunto data modules."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_NEEDS_ESCAPE = re.compile(r'["\\\n\r\t]')
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class LuaSerializationError(TypeError):
    """Raised when a value cannot be represented in mw.loadData output."""


@dataclass(frozen=True)
class LuaReference:
    """An entry of a table that the module defines once, written where the data refers to it."""

    table: str
    key: str


def module_text(value: object, tables: Mapping[str, object] | None = None) -> str:
    """Serialize a value as a Lua module returning that value, after the local tables it refers to."""
    lines = []
    for name, table in (tables or {}).items():
        if _IDENTIFIER.match(name) is None:
            raise LuaSerializationError(f"invalid Lua table name: {name!r}")
        lines.append(f"local {name} = {dumps(table)}\n")
    return "".join(lines) + f"return {dumps(value)}\n"


def shared_module_text(value: object, *, table: str, field: str, key_field: str) -> str:
    """Serialize a module that writes the `field` of the records with one `key_field` value once.

    A value that several records share goes into a local table, and mw.loadData keeps a table that
    the data refers to several times, so each record still reads its `field` directly.
    """
    values: dict[str, object] = {}
    uses: Counter[str] = Counter()

    def collect(node: object) -> None:
        if isinstance(node, Mapping):
            key = node.get(key_field)
            if isinstance(key, str) and node.get(field):
                if values.setdefault(key, node[field]) != node[field]:
                    raise LuaSerializationError(f"{key_field} {key!r} names two different values of {field}")
                uses[key] += 1
            for item in node.values():
                collect(item)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for item in node:
                collect(item)

    def share(node: object) -> object:
        if isinstance(node, Mapping):
            result = {name: share(item) for name, item in node.items()}
            key = node.get(key_field)
            if isinstance(key, str) and uses[key] > 1:
                result[field] = LuaReference(table, key)
            return result
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            return [share(item) for item in node]
        return node

    collect(value)
    shared = {key: values[key] for key in sorted(values) if uses[key] > 1}
    return module_text(share(value) if shared else value, {table: shared} if shared else None)


def dumps(value: object) -> str:
    """Serialize a value to deterministic Lua source."""
    return _serialize(value, depth=0, quoted_keys={})


def _serialize(value: object, depth: int, quoted_keys: dict[str, str]) -> str:
    if isinstance(value, LuaReference):
        if _IDENTIFIER.match(value.table) is None:
            raise LuaSerializationError(f"invalid Lua table name: {value.table!r}")
        return f"{value.table}[{_quote(value.key)}]"
    if isinstance(value, str):
        return _quote(value)
    if value is None:
        serialized = "nil"
    elif isinstance(value, bool):
        serialized = "true" if value else "false"
    elif isinstance(value, int):
        serialized = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise LuaSerializationError(f"cannot serialize non-finite number: {value!r}")
        serialized = repr(value)
    elif isinstance(value, Mapping):
        serialized = _serialize_mapping(value, depth, quoted_keys)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        serialized = _serialize_sequence(value, depth, quoted_keys)
    else:
        raise LuaSerializationError(f"unsupported value for Lua serialization: {type(value).__name__}")
    return serialized


def _serialize_mapping(value: Mapping[Any, Any], depth: int, quoted_keys: dict[str, str]) -> str:
    items: list[tuple[str, object]] = []
    for key, item in value.items():
        if not isinstance(key, str):
            raise LuaSerializationError(f"unsupported table key for Lua serialization: {key!r}")
        if item is not None:
            items.append((key, item))

    if not items:
        return "{}"

    current = "\t" * depth
    child = "\t" * (depth + 1)
    lines = ["{"]
    for key, item in sorted(items, key=lambda entry: entry[0]):
        quoted_key = quoted_keys.get(key)
        if quoted_key is None:
            quoted_key = _quote(key)
            quoted_keys[key] = quoted_key
        lines.append(f"{child}[{quoted_key}] = {_serialize(item, depth + 1, quoted_keys)},")
    lines.append(f"{current}}}")
    return "\n".join(lines)


def _serialize_sequence(value: Sequence[object], depth: int, quoted_keys: dict[str, str]) -> str:
    if not value:
        return "{}"

    current = "\t" * depth
    child = "\t" * (depth + 1)
    lines = ["{"]
    for item in value:
        if item is None:
            raise LuaSerializationError("cannot serialize nil list item")
        lines.append(f"{child}{_serialize(item, depth + 1, quoted_keys)},")
    lines.append(f"{current}}}")
    return "\n".join(lines)


def _quote(value: str) -> str:
    if _NEEDS_ESCAPE.search(value) is None:
        return f'"{value}"'
    # Use the quote that needs fewer escapes. StyLua applies the same rule, so
    # generated modules read like the formatted ones that people maintain.
    quote = "'" if value.count('"') > value.count("'") else '"'
    escaped = (
        value.replace("\\", "\\\\")
        .replace(quote, "\\" + quote)
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f"{quote}{escaped}{quote}"
