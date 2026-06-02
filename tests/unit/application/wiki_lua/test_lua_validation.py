from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from erenshor.application.wiki_lua.validation import LuaValidationError, validate_lua_module


class FakeTools:
    def __init__(self, tools: dict[str, str]) -> None:
        self.tools = tools
        self.commands: list[list[str]] = []

    def which(self, name: str) -> str | None:
        return self.tools.get(name)

    def run(self, command: list[str]) -> CompletedProcess[str]:
        self.commands.append(command)
        return CompletedProcess(command, 0, stdout="", stderr="")


def test_validates_with_luac_when_available(tmp_path: Path) -> None:
    module = tmp_path / "Items.lua"
    module.write_text("return {}\n", encoding="utf-8")
    tools = FakeTools({"luac": "/usr/bin/luac", "stylua": "/bin/stylua"})

    result = validate_lua_module(module, which=tools.which, run=tools.run)

    assert result.tool == "luac"
    assert tools.commands == [["/usr/bin/luac", "-p", str(module)]]


def test_falls_back_to_stylua_lua51_verification(tmp_path: Path) -> None:
    module = tmp_path / "Items.lua"
    module.write_text("return {}\n", encoding="utf-8")
    tools = FakeTools({"stylua": "/repo/node_modules/.bin/stylua"})

    result = validate_lua_module(module, which=tools.which, run=tools.run)

    assert result.tool == "stylua"
    assert tools.commands == [["/repo/node_modules/.bin/stylua", "--syntax", "Lua51", "--verify", str(module)]]


def test_uses_pnpm_stylua_when_stylua_is_not_on_path(tmp_path: Path) -> None:
    module = tmp_path / "Items.lua"
    module.write_text("return {}\n", encoding="utf-8")
    tools = FakeTools({"pnpm": "/opt/homebrew/bin/pnpm"})

    result = validate_lua_module(module, which=tools.which, run=tools.run)

    assert result.tool == "stylua"
    assert tools.commands == [
        ["/opt/homebrew/bin/pnpm", "exec", "stylua", "--syntax", "Lua51", "--verify", str(module)]
    ]


def test_reports_missing_lua_validation_tool(tmp_path: Path) -> None:
    module = tmp_path / "Items.lua"
    module.write_text("return {}\n", encoding="utf-8")
    tools = FakeTools({})

    with pytest.raises(LuaValidationError, match="luac or StyLua"):
        validate_lua_module(module, which=tools.which, run=tools.run)


def test_reports_validator_failures(tmp_path: Path) -> None:
    module = tmp_path / "Items.lua"
    module.write_text("return {\n", encoding="utf-8")

    def failing_run(command: list[str]) -> CompletedProcess[str]:
        return CompletedProcess(command, 1, stdout="", stderr="syntax error")

    with pytest.raises(LuaValidationError, match="syntax error"):
        validate_lua_module(module, which=lambda name: "/usr/bin/luac" if name == "luac" else None, run=failing_run)
