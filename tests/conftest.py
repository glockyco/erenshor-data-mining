"""Pytest configuration and fixtures for integration tests.

This module provides comprehensive fixtures for testing the wiki update pipeline
with real components (no mocking):
- Real SQLite database with test data
- Real registry system
- Real file I/O for pages
- Real rendering with Jinja2

All fixtures create temporary directories and clean up after themselves.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from erenshor.application.generators.abilities import AbilityGenerator
from erenshor.application.generators.characters import CharacterGenerator
from erenshor.application.generators.fishing import FishingGenerator
from erenshor.application.generators.items import ItemGenerator
from erenshor.application.services.update_service import UpdateService
from erenshor.application.transformers.abilities import AbilityTransformer
from erenshor.application.transformers.characters import CharacterTransformer
from erenshor.application.transformers.items import ItemTransformer
from erenshor.domain.validation.abilities import AbilityValidator
from erenshor.domain.validation.characters import CharacterValidator
from erenshor.domain.validation.items import ItemValidator
from erenshor.infrastructure.config.settings import WikiSettings
from erenshor.infrastructure.storage.page_storage import PageStorage
from erenshor.infrastructure.templates.engine import Renderer
from erenshor.registry.core import WikiRegistry
from erenshor.registry.links import RegistryLinkResolver


@pytest.fixture(autouse=True)
def reset_path_resolver() -> Generator[None, None, None]:
    """Automatically reset PathResolver singleton before each test.

    This ensures tests don't interfere with each other through shared state.
    The fixture is autouse=True, so it runs for every test automatically.
    """
    from erenshor.infrastructure.config import paths

    # Store original resolver if any
    original = paths._resolver

    # Reset singleton before test
    paths._resolver = None

    yield

    # Restore original after test (or reset again)
    paths._resolver = original or None


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a test database from SQL fixture.

    This fixture is session-scoped to avoid recreating the database for every test.
    The database contains minimal but representative data for all content types.
    """
    # Create temp database file
    db_path = tmp_path_factory.mktemp("db") / "test_erenshor.sqlite"

    # Load SQL fixture
    fixture_path = Path(__file__).parent / "fixtures" / "test_erenshor.sql"

    if not fixture_path.exists():
        pytest.skip(f"Test database fixture not found: {fixture_path}")

    # Create database from SQL
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            sql_content = fixture_path.read_text()
            # Execute each statement separately (SQLite doesn't support executescript via SQLAlchemy)
            for statement in sql_content.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
            conn.commit()
    finally:
        engine.dispose()

    return db_path


@pytest.fixture(scope="session")
def test_engine(test_db_path: Path) -> Generator[Engine, None, None]:
    """Create SQLAlchemy engine for test database."""
    engine = create_engine(f"sqlite:///{test_db_path}")
    yield engine
    engine.dispose()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that gets cleaned up after test."""
    dirpath = Path(tempfile.mkdtemp())
    yield dirpath
    shutil.rmtree(dirpath, ignore_errors=True)


@pytest.fixture
def test_registry(temp_dir: Path) -> WikiRegistry:
    """Create a fresh WikiRegistry for testing."""
    registry_dir = temp_dir / "registry"
    registry_dir.mkdir(parents=True)

    # WikiRegistry creates pages_dir automatically under registry_dir
    return WikiRegistry(registry_dir=registry_dir)


@pytest.fixture
def test_cache_storage(test_registry: WikiRegistry, temp_dir: Path) -> PageStorage:
    """Create PageStorage for cached (input) pages."""
    cache_dir = temp_dir / "wiki_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return PageStorage(test_registry, cache_dir)


@pytest.fixture
def test_output_storage(test_registry: WikiRegistry, temp_dir: Path) -> PageStorage:
    """Create PageStorage for generated (output) pages."""
    output_dir = temp_dir / "wiki_updated"
    output_dir.mkdir(parents=True, exist_ok=True)
    return PageStorage(test_registry, output_dir)


@pytest.fixture
def test_settings(test_db_path: Path, temp_dir: Path) -> WikiSettings:
    """Create WikiSettings for testing."""
    return WikiSettings(
        db_path=test_db_path,
        cache_dir=temp_dir / "wiki_cache",
        output_dir=temp_dir / "wiki_updated",
        reports_dir=temp_dir / "reports",
    )


@pytest.fixture
def test_renderer() -> Renderer:
    """Create Renderer with test templates."""
    return Renderer()


@pytest.fixture
def test_link_resolver(test_registry: WikiRegistry) -> RegistryLinkResolver:
    """Create RegistryLinkResolver for generating wiki links."""
    return RegistryLinkResolver(test_registry)


# Generator fixtures
@pytest.fixture
def item_generator(test_renderer: Renderer) -> ItemGenerator:
    """Create ItemGenerator for testing."""
    return ItemGenerator(test_renderer)


@pytest.fixture
def character_generator(test_renderer: Renderer) -> CharacterGenerator:
    """Create CharacterGenerator for testing."""
    return CharacterGenerator(test_renderer)


@pytest.fixture
def ability_generator(test_renderer: Renderer) -> AbilityGenerator:
    """Create AbilityGenerator for testing."""
    return AbilityGenerator(test_renderer)


@pytest.fixture
def fishing_generator(test_renderer: Renderer) -> FishingGenerator:
    """Create FishingGenerator for testing."""
    return FishingGenerator(test_renderer)


# Transformer fixtures
@pytest.fixture
def item_transformer() -> ItemTransformer:
    """Create ItemTransformer for testing."""
    from erenshor.application.transformers.merger import FieldMerger
    from erenshor.application.transformers.parser import WikiParser

    return ItemTransformer(WikiParser(), FieldMerger())


@pytest.fixture
def character_transformer() -> CharacterTransformer:
    """Create CharacterTransformer for testing."""
    return CharacterTransformer()


@pytest.fixture
def ability_transformer() -> AbilityTransformer:
    """Create AbilityTransformer for testing."""
    return AbilityTransformer()


# Validator fixtures
@pytest.fixture
def item_validator() -> ItemValidator:
    """Create ItemValidator for testing."""
    return ItemValidator()


@pytest.fixture
def character_validator() -> CharacterValidator:
    """Create CharacterValidator for testing."""
    return CharacterValidator()


@pytest.fixture
def ability_validator() -> AbilityValidator:
    """Create AbilityValidator for testing."""
    return AbilityValidator()


# Service fixtures
@pytest.fixture
def item_update_service(
    item_generator: ItemGenerator,
    item_transformer: ItemTransformer,
    item_validator: ItemValidator,
    test_cache_storage: PageStorage,
    test_output_storage: PageStorage,
    test_registry: WikiRegistry,
) -> UpdateService:
    """Create UpdateService for item updates."""
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
    character_generator: CharacterGenerator,
    character_transformer: CharacterTransformer,
    character_validator: CharacterValidator,
    test_cache_storage: PageStorage,
    test_output_storage: PageStorage,
    test_registry: WikiRegistry,
) -> UpdateService:
    """Create UpdateService for character updates."""
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
    ability_generator: AbilityGenerator,
    ability_transformer: AbilityTransformer,
    ability_validator: AbilityValidator,
    test_cache_storage: PageStorage,
    test_output_storage: PageStorage,
    test_registry: WikiRegistry,
) -> UpdateService:
    """Create UpdateService for ability updates."""
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
    baseline_path = (
        Path(__file__).parent / "fixtures" / "baseline_pages" / f"{page_name}.txt"
    )

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
            pytest.fail(
                f"Expected template '{expected}' not found in page. "
                f"Found templates: {templates}"
            )
