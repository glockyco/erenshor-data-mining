"""Contracts for dependency-state validation helpers."""

from pathlib import Path

from erenshor.infrastructure.dependency_state import (
    immutable_action_reference_violations,
    locked_nuget_restore_commands,
    nix_updater_ownership_violations,
)
from erenshor.infrastructure.dotnet_projects import MAINTAINED_DOTNET_RESTORE_TARGETS

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_locked_restore_commands_cover_each_lock_graph_with_loader_properties() -> None:
    commands = locked_nuget_restore_commands()
    locked_targets = tuple(target for target in MAINTAINED_DOTNET_RESTORE_TARGETS if target.lock_file is not None)

    assert len(commands) == len(locked_targets)
    assert len(commands) == 19
    for command, target in zip(commands, locked_targets, strict=True):
        assert command[:3] == ("dotnet", "restore", target.project)
        assert command[3:5] == ("--locked-mode", "--force-evaluate")
        assert command[5:] == tuple(f"-p:{name}={value}" for name, value in target.properties)


def test_action_validation_accepts_full_shas_and_local_actions(tmp_path: Path) -> None:
    workflows = tmp_path / ".github/workflows"
    workflows.mkdir(parents=True)
    sha = "a" * 40
    (workflows / "ci.yml").write_text(
        f"""jobs:
  pinned:
    steps:
      - uses: actions/checkout@{sha} # v7
      - uses: ./custom-action
""",
        encoding="utf-8",
    )

    assert immutable_action_reference_violations(tmp_path) == ()


def test_repository_workflows_are_immutable_and_aggregate_dependency_state() -> None:
    assert immutable_action_reference_violations(_REPO_ROOT) == ()
    assert nix_updater_ownership_violations(_REPO_ROOT) == ()

    workflow = (_REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "  dependency-state:\n" in workflow
    assert "[dependency-state, static, security, test-unit, test-contract, test-maps, test-mods]" in workflow
    assert 'needs.dependency-state.result }}" != "success"' in workflow


def test_ci_uses_read_only_permissions_without_unused_coverage_uploads() -> None:
    workflow = (_REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    unit_job = workflow.split("  test-unit:\n", 1)[1].split("  test-contract:\n", 1)[0]

    assert "permissions:\n  contents: read\n" in workflow.split("jobs:", 1)[0]
    assert "id-token" not in workflow
    assert "codecov" not in workflow.lower()
    assert "--coverage" not in unit_job
    assert "coverage.xml" not in unit_job
    assert "path: artifacts/test-reports/unit.json" in unit_job


def test_updater_ownership_reports_competing_or_missing_owners(tmp_path: Path) -> None:
    (tmp_path / "renovate.json").write_text('{"packageRules": []}\n', encoding="utf-8")

    assert nix_updater_ownership_violations(tmp_path) == (
        "Renovate must disable the nix manager",
        "Renovate must reserve npm packageManager assertions for the Nix updater",
        ".github/workflows/update-nix-dependencies.yml is missing",
    )


def test_action_validation_reports_every_mutable_or_missing_reference(tmp_path: Path) -> None:
    workflows = tmp_path / ".github/workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yaml").write_text(
        """jobs:
  mutable:
    steps:
      - uses: actions/checkout@v7
      - uses: owner/action
""",
        encoding="utf-8",
    )

    assert immutable_action_reference_violations(tmp_path) == (
        ".github/workflows/ci.yaml:4: actions/checkout@v7 does not use a full commit SHA",
        ".github/workflows/ci.yaml:5: owner/action has no commit ref",
    )
