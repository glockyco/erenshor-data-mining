"""Every test file sits in a directory that a test task runs.

`erenshor test` runs `tests/unit`, `tests/contract`, `tests/data`, and
`tests/system/wiki` (`src/erenshor/cli/commands/test.py`). The canaries in
`tests/integration` probe live services and run only on request. A test file
anywhere else never runs, so a failure in it stays hidden.
"""

from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
RUN_ROOTS = ("unit", "contract", "data", "system/wiki", "integration")


def test_every_test_file_is_in_a_directory_that_a_task_runs() -> None:
    stray = sorted(
        str(path.relative_to(TESTS.parent))
        for path in TESTS.rglob("test_*.py")
        if not any(path.is_relative_to(TESTS / root) for root in RUN_ROOTS)
    )
    assert not stray, f"test files that no test task runs: {stray}"
