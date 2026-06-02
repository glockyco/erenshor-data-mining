from __future__ import annotations

import pytest

from erenshor.application.wiki_lua.lua_writer import LuaSerializationError, dumps, module_text


def test_serializes_supported_load_data_values_deterministically() -> None:
    data = {
        "zeta": True,
        "alpha": {
            "quote": 'value "with" quotes',
            "slash": "path\\to\\icon",
            "newline": "line one\nline two",
            "braces": "literal { braces }",
            "unicode": "Café Ω",
            "none": None,
        },
        "list": ["first", 2, 3.5, False],
    }

    assert module_text(data) == (
        "return {\n"
        '  ["alpha"] = {\n'
        '    ["braces"] = "literal { braces }",\n'
        '    ["newline"] = "line one\\nline two",\n'
        '    ["quote"] = "value \\"with\\" quotes",\n'
        '    ["slash"] = "path\\\\to\\\\icon",\n'
        '    ["unicode"] = "Café Ω",\n'
        "  },\n"
        '  ["list"] = {\n'
        '    "first",\n'
        "    2,\n"
        "    3.5,\n"
        "    false,\n"
        "  },\n"
        '  ["zeta"] = true,\n'
        "}\n"
    )


def test_rejects_values_that_mw_load_data_cannot_return() -> None:
    with pytest.raises(LuaSerializationError, match="unsupported value"):
        dumps({"bad": object()})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(LuaSerializationError, match="non-finite"):
        dumps(value)


def test_rejects_nil_inside_lists() -> None:
    with pytest.raises(LuaSerializationError, match="nil list item"):
        dumps(["ok", None])
