from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from erenshor.application.wiki_lua.validation import LuaValidationError, validate_lua_modules


def test_luac_rejects_syntax_that_lua_5_1_lacks(tmp_path: Path) -> None:
    valid = tmp_path / "Valid.lua"
    valid.write_text('return {\n\t["key"] = \'value "quoted"\',\n}\n', encoding="utf-8")
    newer = tmp_path / "Newer.lua"
    newer.write_text("return 7 // 2\n", encoding="utf-8")

    validate_lua_modules([valid])
    with pytest.raises(LuaValidationError, match=r"Newer\.lua"):
        validate_lua_modules([valid, newer])


def test_requires_luac(tmp_path: Path) -> None:
    with pytest.raises(LuaValidationError, match=r"needs luac from Lua 5\.1"):
        validate_lua_modules([tmp_path / "Items.lua"], which=lambda name: None)


def test_rejects_a_luac_of_another_lua_version(tmp_path: Path) -> None:
    def run(command: list[str]) -> CompletedProcess[str]:
        return CompletedProcess(command, 0, stdout="Lua 5.4.6  Copyright (C) 1994-2023 Lua.org, PUC-Rio", stderr="")

    with pytest.raises(LuaValidationError, match=r"Lua 5\.4\.6"):
        validate_lua_modules([tmp_path / "Items.lua"], which=lambda name: "/usr/bin/luac", run=run)
