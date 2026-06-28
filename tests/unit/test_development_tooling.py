from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, cast


def read_root_package() -> dict[str, Any]:
    data = json.loads(Path("package.json").read_text(encoding="utf-8"))
    return cast("dict[str, Any]", data)


def read_map_package() -> dict[str, Any]:
    data = json.loads(Path("src/maps/package.json").read_text(encoding="utf-8"))
    return cast("dict[str, Any]", data)


def test_lefthook_is_the_only_configured_git_hook_runner() -> None:
    package = read_root_package()
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = cast("dict[str, str]", package["scripts"])
    root_dev_dependencies = cast("dict[str, str]", package.get("devDependencies", {}))
    map_dev_dependencies = cast("dict[str, str]", read_map_package().get("devDependencies", {}))

    assert Path("lefthook.yml").is_file()
    assert not Path(".pre-commit-config.yaml").exists()
    assert not Path(".husky").exists()
    assert scripts["prepare"] == "lefthook install --reset-hooks-path"
    assert "lefthook" in root_dev_dependencies
    assert "husky" not in root_dev_dependencies
    assert "lint-staged" not in root_dev_dependencies
    assert "lint-staged" not in package
    assert "lint-staged" not in map_dev_dependencies
    assert cast("dict[str, list[str]]", package["pnpm"])["onlyBuiltDependencies"] == ["lefthook"]
    assert "pre-commit" not in pyproject["dependency-groups"]["dev"]


def test_lefthook_runs_project_area_checks() -> None:
    config = Path("lefthook.yml").read_text(encoding="utf-8")

    assert "git diff --cached --check" in config

    assert "gitleaks protect --staged" in config
    assert "pre-commit:" in config
    assert "commit-msg:" in config
    assert "pre-push:" in config
    assert "uv run ruff format" in config
    assert "uv run ruff check --fix" in config
    assert "uv run mypy src/" in config
    assert "uv run pytest tests/unit -q --tb=short" in config
    assert "pnpm --filter erenshor-maps lint" in config
    assert "src/maps/*.{js,ts,svelte,cjs,mjs,json}" in config
    assert "bash src/mods/run-csharpier.sh" in config
    assert "pnpm exec stylua --check" in config
    assert "pnpm exec commitlint --edit" in config
    assert "uv run pytest tests/integration -v" in config


def test_commitlint_enforces_project_commit_policy() -> None:
    config = Path("commitlint.config.cjs").read_text(encoding="utf-8")

    assert "@commitlint/config-conventional" in config
    assert "body-max-line-length" in config
    assert "footer-max-line-length" in config
    assert "scope-empty" in config
    assert "scope-enum" not in config


def test_lua_tooling_is_configured_for_scribunto_modules() -> None:
    package = read_root_package()
    dev_dependencies = cast("dict[str, str]", package.get("devDependencies", {}))

    assert "@johnnymorganz/stylua-bin" in dev_dependencies
    assert Path(".stylua.toml").read_text(encoding="utf-8").startswith('syntax = "Lua51"')
    luacheck = Path(".luacheckrc").read_text(encoding="utf-8")
    assert "mw" in luacheck
    assert "frame" in luacheck


def test_development_docs_point_to_lefthook_not_pre_commit() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "pnpm exec lefthook install" in readme
    assert "uv run pre-commit install" not in readme
    assert "pre-commit hooks" not in readme
