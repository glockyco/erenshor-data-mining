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
    assert "gitleaks git --pre-commit --staged" in config
    assert "pre-commit:" in config
    assert "commit-msg:" in config
    assert "pre-push:" in config
    assert "uv run mypy src/" not in config
    assert "uv run pytest tests/unit -q --tb=short" not in config
    assert "uv run pytest tests/integration -v" not in config

    pre_push = config.split("pre-push:", maxsplit=1)[1]
    pre_push_commands = [
        line.strip()[len("run: ") :] for line in pre_push.splitlines() if line.strip().startswith("run: ")
    ]
    assert pre_push_commands == [
        "scripts/with-dev-env.sh erenshor test unit",
        "scripts/with-dev-env.sh erenshor test contract",
    ]

    assert "scripts/with-dev-env.sh ruff format" in config
    assert "scripts/with-dev-env.sh ruff check --fix" in config
    assert "pnpm --filter erenshor-maps lint" in config
    assert "src/maps/*.{js,ts,svelte,cjs,mjs,json}" in config
    assert "bash src/mods/run-csharpier.sh" in config
    assert "pnpm exec stylua --check" in config
    assert "pnpm exec commitlint --edit" in config


def test_hook_jobs_needing_project_tools_enter_the_dev_shell() -> None:
    """Hooks must not assume the invoking process has the toolchain on PATH.

    Git clients that are not shells run hooks with the bare session PATH, where
    a job calling a dev-shell tool directly aborts the commit or push with exit
    127 for reasons unrelated to the change.
    """
    wrapper = Path("scripts/with-dev-env.sh")
    assert wrapper.is_file()
    assert wrapper.stat().st_mode & 0o111, "wrapper must be executable"

    config = Path("lefthook.yml").read_text(encoding="utf-8")
    dev_shell_tools = (
        "erenshor ",
        "pytest ",
        "ruff ",
        "mypy ",
        "pnpm ",
        "gitleaks ",
        "dotnet ",
        "run-csharpier.sh",
    )
    unwrapped = [
        command
        for line in config.splitlines()
        if line.strip().startswith("run: ")
        for command in [line.strip()[len("run: ") :]]
        if any(tool in command for tool in dev_shell_tools) and not command.startswith("scripts/with-dev-env.sh ")
    ]

    assert unwrapped == [], f"hook jobs bypass the dev shell: {unwrapped}"


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


def test_python_selector_matches_flake_and_ci_minor_version() -> None:
    selector = Path(".python-version").read_text(encoding="utf-8").strip()
    assert selector == "3.14"

    flake = Path("flake.nix").read_text(encoding="utf-8")
    assert "python = pkgs.python314" in flake
    assert "UV_PYTHON = pythonSet.python.interpreter" in flake

    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "DeterminateSystems/determinate-nix-action@61cbfe2efc2d4e7a8a6d56967c3c1058e846c858 # v3.21.9" in ci
    assert "actions/setup-python" not in ci


def test_ci_uses_the_flake_toolchain_for_project_commands() -> None:
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert ci.count("DeterminateSystems/determinate-nix-action@61cbfe2efc2d4e7a8a6d56967c3c1058e846c858") == 7
    assert "actions/setup-python" not in ci
    assert "actions/setup-node" not in ci
    assert "actions/setup-dotnet" not in ci
    assert "pnpm/action-setup" not in ci
    assert "astral-sh/setup-uv" not in ci
    assert "uv sync" not in ci
    assert "uv run" not in ci

    project_tools = ("erenshor ", "pytest ", "pnpm ", "dotnet ")
    unwrapped = [
        line.strip()[len("run: ") :]
        for line in ci.splitlines()
        if line.strip().startswith("run: ")
        and any(tool in line for tool in project_tools)
        and "nix develop --command" not in line
    ]
    assert unwrapped == []


def test_github_workflows_do_not_create_mutable_python_environments() -> None:
    workflows = "\n".join(path.read_text(encoding="utf-8") for path in sorted(Path(".github/workflows").glob("*.yml")))

    assert "actions/setup-python" not in workflows
    assert "astral-sh/setup-uv" not in workflows
    assert "uv sync" not in workflows
    assert "uv run" not in workflows


def test_flake_builds_locked_python_and_bootstraps_mutable_tools() -> None:
    flake = Path("flake.nix").read_text(encoding="utf-8")
    lock = json.loads(Path("flake.lock").read_text(encoding="utf-8"))

    assert "uv2nix.lib.workspace.loadWorkspace" in flake
    assert 'sourcePreference = "wheel"' in flake
    assert 'mkVirtualEnv "erenshor-dev-env" workspace.deps.all' in flake
    assert "lib.fileset.toSource" in flake
    assert 'UV_NO_SYNC = "1"' in flake
    assert "UV_PROJECT_ENVIRONMENT" in flake
    assert 'DOTNET_ROOT = "${dotnetEnvironment}/share/dotnet"' in flake
    assert "LD_LIBRARY_PATH" not in flake
    assert "autoPatchelf" not in flake
    assert "uv sync" not in flake
    assert {"pyproject-build-systems", "pyproject-nix", "uv2nix"} <= lock["nodes"].keys()

    assert "assert assertPnpmVersion pkgs;" in flake
    assert 'name = "erenshor-sync-pnpm-version"' in flake
    assert "nix run .#sync-pnpm-version" in flake
    assert "pnpm install --frozen-lockfile" in flake
    assert "dotnet tool restore" in flake
    assert "apps = forAllSystems" in flake

    readme = Path("README.md").read_text(encoding="utf-8")
    assert "nix run .#bootstrap" in readme


def test_development_docs_point_to_lefthook_not_pre_commit() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "pnpm exec lefthook install" in readme
    assert "uv run pre-commit install" not in readme
    assert "pre-commit hooks" not in readme
