from __future__ import annotations

import pytest

from erenshor.application.wiki_lua.lua_writer import LuaSerializationError, dumps, module_text, shared_module_text


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
        '\t["alpha"] = {\n'
        '\t\t["braces"] = "literal { braces }",\n'
        '\t\t["newline"] = "line one\\nline two",\n'
        '\t\t["quote"] = \'value "with" quotes\',\n'
        '\t\t["slash"] = "path\\\\to\\\\icon",\n'
        '\t\t["unicode"] = "Café Ω",\n'
        "\t},\n"
        '\t["list"] = {\n'
        '\t\t"first",\n'
        "\t\t2,\n"
        "\t\t3.5,\n"
        "\t\tfalse,\n"
        "\t},\n"
        '\t["zeta"] = true,\n'
        "}\n"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('say "hi"', "'say \"hi\"'"),
        ('it\'s "x"', "'it\\'s \"x\"'"),
        ("'a' \"b\"", '"\'a\' \\"b\\""'),
        ("it's", '"it\'s"'),
        ('"a" \'b\' "c"', "'\"a\" \\'b\\' \"c\"'"),
        ("", '""'),
        ("plain ' apostrophe", '"plain \' apostrophe"'),
        ("line\r\n\t\\", '"line\\r\\n\\t\\\\"'),
    ],
)
def test_quotes_strings_with_the_quote_that_needs_fewer_escapes(value: str, expected: str) -> None:
    assert dumps(value) == expected


def test_repeated_escaped_mapping_keys_keep_their_quoted_spelling() -> None:
    assert dumps([{'a"b': "one"}, {'a"b': "two"}]) == (
        '{\n\t{\n\t\t[\'a"b\'] = "one",\n\t},\n\t{\n\t\t[\'a"b\'] = "two",\n\t},\n}'
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


def test_records_with_one_key_refer_to_one_shared_value() -> None:
    records = {
        "a": [{"source": "s", "places": ["x", "y"]}, {"source": None, "places": ["z"]}],
        "b": [{"source": "s", "places": ["x", "y"]}],
    }
    assert shared_module_text(records, table="shared", field="places", key_field="source") == (
        "local shared = {\n"
        '\t["s"] = {\n'
        '\t\t"x",\n'
        '\t\t"y",\n'
        "\t},\n"
        "}\n"
        "return {\n"
        '\t["a"] = {\n'
        "\t\t{\n"
        '\t\t\t["places"] = shared["s"],\n'
        '\t\t\t["source"] = "s",\n'
        "\t\t},\n"
        "\t\t{\n"
        '\t\t\t["places"] = {\n'
        '\t\t\t\t"z",\n'
        "\t\t\t},\n"
        "\t\t},\n"
        "\t},\n"
        '\t["b"] = {\n'
        "\t\t{\n"
        '\t\t\t["places"] = shared["s"],\n'
        '\t\t\t["source"] = "s",\n'
        "\t\t},\n"
        "\t},\n"
        "}\n"
    )


def test_one_key_cannot_name_two_shared_values() -> None:
    records = [{"source": "s", "places": ["x"]}, {"source": "s", "places": ["y"]}]
    with pytest.raises(LuaSerializationError, match="two different values"):
        shared_module_text(records, table="shared", field="places", key_field="source")
