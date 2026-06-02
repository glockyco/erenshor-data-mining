from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import FakeItemRepository, make_item

from erenshor.application.wiki_lua.generation import generate_lua_data_modules
from erenshor.application.wiki_lua.validation import LuaValidationResult


def test_generates_and_validates_lua_data_modules(tmp_path: Path) -> None:
    item = make_item()
    item_repo = FakeItemRepository(items=[item], stats={}, classes={})
    validated_paths: list[Path] = []

    def record_validation(path: Path) -> LuaValidationResult:
        validated_paths.append(path)
        return LuaValidationResult(path=path, tool="stylua")

    result = generate_lua_data_modules(item_repo=item_repo, output_root=tmp_path, validate=record_validation)

    items_path = tmp_path / "Erenshor" / "Data" / "Items.lua"
    assert result.written_paths == [items_path]
    assert result.validation_tools == {items_path: "stylua"}
    assert validated_paths == [items_path]
    assert "return {" in items_path.read_text(encoding="utf-8")
