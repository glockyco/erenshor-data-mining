"""Pytest configuration and fixtures for tests.

This module provides comprehensive fixtures for testing the wiki update pipeline
with real components (no mocking):
- Real SQLite database from exported game data
- Real registry system
- Real file I/O for pages
- Real rendering with Jinja2

Database Fixtures:
- integration_db: Uses most recently exported database from variants/ directory
- production_db: Optional full database (skips if missing)

All fixtures create temporary directories and clean up after themselves.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Lazy imports to avoid loading modules that don't exist yet during early testing
# These imports happen inside fixture functions only when actually needed


# === Database Fixtures ===


@pytest.fixture(scope="session")
def integration_db() -> Generator[Path]:
    """Find most recently exported database from any variant.

    This fixture uses real exported databases instead of hand-written fixtures.
    Searches variants/ directory for erenshor-*.sqlite files and returns
    the most recently modified one.

    Returns:
        Path: Path to the most recently exported database

    Raises:
        pytest.skip: If no exported database exists
    """
    variants_dir = Path(__file__).parent.parent / "variants"
    databases = list(variants_dir.glob("*/erenshor-*.sqlite"))

    # Exclude raw exports and backup/temp files — only the processed clean DB has
    # the full schema (stable_key, etc.) that repository tests depend on.
    databases = [db for db in databases if ".pre-" not in db.name and "-raw" not in db.name]

    if not databases:
        pytest.skip("No exported database found. Run 'uv run erenshor extract export' first.")

    # Return most recently modified
    yield max(databases, key=lambda p: p.stat().st_mtime)


@pytest.fixture
def production_db() -> Generator[Path | None]:
    """Optional fixture for testing against production database.

    This fixture looks for a production database in the variants/main directory.
    If not found, the test is skipped. Use this for tests that need to verify
    behavior against real production data.

    Returns:
        Path | None: Path to production database or None if not available
    """
    repo_root = Path(__file__).parent.parent
    prod_db_path = repo_root / "variants" / "main" / "erenshor-main.sqlite"

    if not prod_db_path.exists():
        pytest.skip("Production database not available (run 'erenshor export' first)")

    yield prod_db_path


@pytest.fixture(autouse=True)
def reset_path_resolver() -> Generator[None]:
    """Automatically reset PathResolver singleton before each test.

    This ensures tests don't interfere with each other through shared state.
    The fixture is autouse=True, so it runs for every test automatically.
    """
    try:
        from erenshor.infrastructure.config import paths

        # Only reset if the module has _resolver attribute
        if hasattr(paths, "_resolver"):
            # Store original resolver if any
            original = paths._resolver

            # Reset singleton before test
            paths._resolver = None

            yield

            # Restore original after test (or reset again)
            paths._resolver = original or None
        else:
            yield
    except (ImportError, AttributeError):
        # Module doesn't exist yet or doesn't have _resolver
        yield


@pytest.fixture
def temp_dir() -> Generator[Path]:
    """Create a temporary directory that gets cleaned up after test."""
    dirpath = Path(tempfile.mkdtemp())
    yield dirpath
    shutil.rmtree(dirpath, ignore_errors=True)


@pytest.fixture
def test_registry(temp_dir: Path):
    """Create a fresh WikiRegistry for testing."""
    from erenshor.registry.core import WikiRegistry

    registry_dir = temp_dir / "registry"
    registry_dir.mkdir(parents=True)

    # WikiRegistry creates pages_dir automatically under registry_dir
    return WikiRegistry(registry_dir=registry_dir)


@pytest.fixture
def test_cache_storage(test_registry, temp_dir: Path):
    """Create PageStorage for cached (input) pages."""
    from erenshor.infrastructure.storage.page_storage import PageStorage

    cache_dir = temp_dir / "wiki_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return PageStorage(test_registry, cache_dir)


@pytest.fixture
def test_output_storage(test_registry, temp_dir: Path):
    """Create PageStorage for generated (output) pages."""
    from erenshor.infrastructure.storage.page_storage import PageStorage

    output_dir = temp_dir / "wiki_updated"
    output_dir.mkdir(parents=True, exist_ok=True)
    return PageStorage(test_registry, output_dir)


@pytest.fixture
def test_link_resolver(test_registry):
    """Create RegistryLinkResolver for generating wiki links."""
    from erenshor.registry.links import RegistryLinkResolver

    return RegistryLinkResolver(test_registry)


# Generator fixtures
@pytest.fixture
def item_generator():
    """Create ItemGenerator for testing."""
    from erenshor.application.generators.items import ItemGenerator

    return ItemGenerator()


@pytest.fixture
def character_generator():
    """Create CharacterGenerator for testing."""
    from erenshor.application.generators.characters import CharacterGenerator

    return CharacterGenerator()


@pytest.fixture
def ability_generator():
    """Create AbilityGenerator for testing."""
    from erenshor.application.generators.abilities import AbilityGenerator

    return AbilityGenerator()


@pytest.fixture
def fishing_generator():
    """Create FishingGenerator for testing."""
    from erenshor.application.generators.fishing import FishingGenerator

    return FishingGenerator()


# Transformer fixtures
@pytest.fixture
def item_transformer():
    """Create ItemTransformer for testing."""
    from erenshor.application.transformers.items import ItemTransformer
    from erenshor.application.transformers.merger import FieldMerger
    from erenshor.application.transformers.parser import WikiParser

    return ItemTransformer(WikiParser(), FieldMerger())


@pytest.fixture
def character_transformer():
    """Create CharacterTransformer for testing."""
    from erenshor.application.transformers.characters import CharacterTransformer

    return CharacterTransformer()


@pytest.fixture
def ability_transformer():
    """Create AbilityTransformer for testing."""
    from erenshor.application.transformers.abilities import AbilityTransformer

    return AbilityTransformer()


# Validator fixtures
@pytest.fixture
def item_validator():
    """Create ItemValidator for testing."""
    from erenshor.domain.validation.items import ItemValidator

    return ItemValidator()


@pytest.fixture
def character_validator():
    """Create CharacterValidator for testing."""
    from erenshor.domain.validation.characters import CharacterValidator

    return CharacterValidator()


@pytest.fixture
def ability_validator():
    """Create AbilityValidator for testing."""
    from erenshor.domain.validation.abilities import AbilityValidator

    return AbilityValidator()


# Service fixtures
@pytest.fixture
def item_update_service(
    item_generator,
    item_transformer,
    item_validator,
    test_cache_storage,
    test_output_storage,
    test_registry,
):
    """Create UpdateService for item updates."""
    from erenshor.application.services.update_service import UpdateService

    return UpdateService(
        generator=item_generator,
        transformer=item_transformer,
        validator=item_validator,
        cache_storage=test_cache_storage,
        output_storage=test_output_storage,
        registry=test_registry,
    )


@pytest.fixture
def character_update_service(
    character_generator,
    character_transformer,
    character_validator,
    test_cache_storage,
    test_output_storage,
    test_registry,
):
    """Create UpdateService for character updates."""
    from erenshor.application.services.update_service import UpdateService

    return UpdateService(
        generator=character_generator,
        transformer=character_transformer,
        validator=character_validator,
        cache_storage=test_cache_storage,
        output_storage=test_output_storage,
        registry=test_registry,
    )


@pytest.fixture
def ability_update_service(
    ability_generator,
    ability_transformer,
    ability_validator,
    test_cache_storage,
    test_output_storage,
    test_registry,
):
    """Create UpdateService for ability updates."""
    from erenshor.application.services.update_service import UpdateService

    return UpdateService(
        generator=ability_generator,
        transformer=ability_transformer,
        validator=ability_validator,
        cache_storage=test_cache_storage,
        output_storage=test_output_storage,
        registry=test_registry,
    )


def load_baseline_page(page_name: str) -> str:
    """Load a baseline page fixture for comparison.

    Baseline pages are expected outputs stored in tests/fixtures/baseline_pages/
    """
    baseline_path = Path(__file__).parent / "fixtures" / "baseline_pages" / f"{page_name}.txt"

    if not baseline_path.exists():
        pytest.fail(f"Baseline page not found: {baseline_path}")

    return baseline_path.read_text()


def assert_page_structure_valid(content: str, expected_templates: list[str]) -> None:
    """Assert that page content has valid structure with expected templates.

    This is a lightweight structural check, not a full validation.
    """
    import mwparserfromhell

    try:
        wikicode = mwparserfromhell.parse(content)
    except Exception as exc:
        pytest.fail(f"Failed to parse wikicode: {exc}")

    templates = [t.name.strip() for t in wikicode.filter_templates()]

    for expected in expected_templates:
        if expected not in templates:
            pytest.fail(f"Expected template '{expected}' not found in page. Found templates: {templates}")
