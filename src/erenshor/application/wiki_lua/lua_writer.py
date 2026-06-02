"""Deterministic Lua serialization for Scribunto data modules."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


class LuaSerializationError(TypeError):
    """Raised when a value cannot be represented in mw.loadData output."""


def module_text(value: object) -> str:
    """Serialize a value as a Lua module returning that value."""
    return f"return {dumps(value)}\n"


def dumps(value: object) -> str:
    """Serialize a value to deterministic Lua source."""
    return _serialize(value, indent=0)


def _serialize(value: object, indent: int) -> str:
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
    elif isinstance(value, str):
        serialized = _quote(value)
    elif isinstance(value, Mapping):
        serialized = _serialize_mapping(value, indent)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        serialized = _serialize_sequence(value, indent)
    else:
        raise LuaSerializationError(f"unsupported value for Lua serialization: {type(value).__name__}")
    return serialized


def _serialize_mapping(value: Mapping[Any, Any], indent: int) -> str:
    items: list[tuple[str, object]] = []
    for key, item in value.items():
        if not isinstance(key, str):
            raise LuaSerializationError(f"unsupported table key for Lua serialization: {key!r}")
        if item is not None:
            items.append((key, item))

    if not items:
        return "{}"

    current = " " * indent
    child = " " * (indent + 2)
    lines = ["{"]
    for key, item in sorted(items, key=lambda entry: entry[0]):
        lines.append(f"{child}[{_quote(key)}] = {_serialize(item, indent + 2)},")
    lines.append(f"{current}}}")
    return "\n".join(lines)


def _serialize_sequence(value: Sequence[object], indent: int) -> str:
    if not value:
        return "{}"

    current = " " * indent
    child = " " * (indent + 2)
    lines = ["{"]
    for item in value:
        if item is None:
            raise LuaSerializationError("cannot serialize nil list item")
        lines.append(f"{child}{_serialize(item, indent + 2)},")
    lines.append(f"{current}}}")
    return "\n".join(lines)


def _quote(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    )
    return f'"{escaped}"'
