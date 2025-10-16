"""Integration tests for idempotency (deterministic updates).

This is CRITICAL for wiki updates. Running the same update twice must produce
identical output. This verifies that:
- Content generation is deterministic
- No timestamps or random elements are included
- Parser transformations are stable
- Registry updates are consistent

Per PRD: "Idempotency verified (run twice, identical output)"
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.engine import Engine

from erenshor.application.services.update_service import UpdateService
from erenshor.domain.events import PageUpdated, UpdateComplete
from erenshor.infrastructure.storage.page_storage import PageStorage
from erenshor.registry.core import WikiRegistry


def compute_directory_hash(directory: Path) -> dict[str, str]:
    """Compute SHA256 hash of all files in directory.

    Returns dict mapping filename to hash.
    """
    hashes = {}

    for file_path in sorted(directory.glob("*.txt")):
        content = file_path.read_bytes()
        file_hash = hashlib.sha256(content).hexdigest()
        hashes[file_path.name] = file_hash

    return hashes


def test_item_idempotency(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
    temp_dir: Path,
) -> None:
    """Test that running item updates twice produces identical output."""
    # First run
    events_run1 = list(item_update_service.update_pages(test_engine))
    hashes_run1 = compute_directory_hash(test_output_storage.pages_dir)

    # Copy output to cache for second run (so UpdateService can compare against first run)
    import shutil

    cache_dir = temp_dir / "wiki_cache"
    output_dir = temp_dir / "wiki_updated"
    for file_path in output_dir.glob("*.txt"):
        shutil.copy2(file_path, cache_dir / file_path.name)

    # Second run (same service, same database)
    events_run2 = list(item_update_service.update_pages(test_engine))
    hashes_run2 = compute_directory_hash(test_output_storage.pages_dir)

    # Compare event counts
    updated_run1 = [e for e in events_run1 if isinstance(e, PageUpdated)]
    updated_run2 = [e for e in events_run2 if isinstance(e, PageUpdated)]

    assert (
        len(updated_run1) == len(updated_run2)
    ), f"Different number of updates: run1={len(updated_run1)}, run2={len(updated_run2)}"

    # Compare file hashes
    assert hashes_run1 == hashes_run2, (
        "File contents differ between runs. Updates are NOT idempotent.\n"
        f"Files in run1: {set(hashes_run1.keys())}\n"
        f"Files in run2: {set(hashes_run2.keys())}\n"
        f"Changed files: {set(k for k in hashes_run1 if hashes_run1.get(k) != hashes_run2.get(k))}"
    )

    # Second run should have all "unchanged" (no actual changes)
    complete_run2 = [e for e in events_run2 if isinstance(e, UpdateComplete)]
    if complete_run2:
        complete = complete_run2[0]
        assert complete.unchanged == complete.total, (
            "Second run should mark all pages as unchanged. "
            f"Got unchanged={complete.unchanged}, total={complete.total}"
        )


def test_character_idempotency(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that running character updates twice produces identical output."""
    # First run
    list(character_update_service.update_pages(test_engine))
    hashes_run1 = compute_directory_hash(test_output_storage.pages_dir)

    # Second run
    list(character_update_service.update_pages(test_engine))
    hashes_run2 = compute_directory_hash(test_output_storage.pages_dir)

    assert hashes_run1 == hashes_run2, "Character updates are NOT idempotent"


def test_ability_idempotency(
    test_engine: Engine,
    ability_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that running ability updates twice produces identical output."""
    # First run
    list(ability_update_service.update_pages(test_engine))
    hashes_run1 = compute_directory_hash(test_output_storage.pages_dir)

    # Second run
    list(ability_update_service.update_pages(test_engine))
    hashes_run2 = compute_directory_hash(test_output_storage.pages_dir)

    assert hashes_run1 == hashes_run2, "Ability updates are NOT idempotent"


def test_registry_idempotency(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_registry: WikiRegistry,
) -> None:
    """Test that registry doesn't grow on repeated runs."""
    # First run
    list(item_update_service.update_pages(test_engine))
    page_count_run1 = len(test_registry.pages)

    # Second run
    list(item_update_service.update_pages(test_engine))
    page_count_run2 = len(test_registry.pages)

    assert page_count_run1 == page_count_run2, (
        f"Registry grew from {page_count_run1} to {page_count_run2} pages on second run. "
        "Should be stable."
    )


def test_no_timestamps_in_content(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that generated content contains no timestamps or dates.

    This ensures idempotency - timestamps would cause different output on each run.
    """
    import re

    list(item_update_service.update_pages(test_engine))

    # Check all generated pages for timestamps
    timestamp_pattern = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}")

    for file_path in test_output_storage.pages_dir.glob("*.txt"):
        content = file_path.read_text()

        # Skip checking comments (which might legitimately have timestamps)
        # Only check visible wiki content
        visible_content = "\n".join(
            line for line in content.split("\n") if not line.strip().startswith("<!--")
        )

        matches = timestamp_pattern.findall(visible_content)

        assert not matches, (
            f"Found timestamps in {file_path.name}: {matches}\n"
            "Generated content must not include timestamps for idempotency."
        )


def test_no_random_elements(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test deterministic output by comparing multiple independent runs.

    If any random elements exist, this test will occasionally fail.
    """
    run_outputs = []

    for _ in range(3):
        # Clear output
        for file_path in test_output_storage.pages_dir.glob("*.txt"):
            file_path.unlink()

        # Run update
        list(item_update_service.update_pages(test_engine))

        # Capture output hashes
        hashes = compute_directory_hash(test_output_storage.pages_dir)
        run_outputs.append(hashes)

    # All three runs should be identical
    assert run_outputs[0] == run_outputs[1] == run_outputs[2], (
        "Multiple independent runs produced different output. "
        "Check for random elements or timestamps."
    )


def test_content_change_detection(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that service correctly detects when content actually changes."""
    # First run
    events_run1 = list(item_update_service.update_pages(test_engine))

    # Second run (no changes)
    list(item_update_service.update_pages(test_engine))

    # Third run (manually modify a file to simulate change)
    # Find first generated page
    updated_run1 = [e for e in events_run1 if isinstance(e, PageUpdated)]
    if updated_run1:
        first_page_title = updated_run1[0].page_title
        first_page = test_output_storage.registry.get_page_by_title(first_page_title)
        assert first_page is not None

        if first_page:
            # Manually modify the file
            content = test_output_storage.read(first_page)
            assert content is not None
            modified_content = content + "\n<!-- test modification -->"
            test_output_storage.write(first_page, modified_content)

            # Run again - should regenerate and overwrite our modification
            list(item_update_service.update_pages(test_engine))

            # Verify file was restored to original (without our comment)
            final_content = test_output_storage.read(first_page)
            assert final_content is not None
            assert (
                "<!-- test modification -->" not in final_content
            ), "Generated content should overwrite manual modifications"
