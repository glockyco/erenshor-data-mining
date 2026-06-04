"""Unit tests for wiki generator registry."""

from unittest.mock import Mock

import pytest

from erenshor.application.wiki.generators.base import GeneratedPage, PageGenerator, PageMetadata
from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.generators.registry import (
    GeneratorRegistration,
    get_generators_by_name,
    list_generators,
)


class MockItemGenerator(PageGenerator):
    """Mock item page generator for testing."""

    def get_pages_to_fetch(self) -> list[str]:
        return ["Item 1", "Item 2"]

    def generate_pages(self):
        yield GeneratedPage(
            title="Item 1",
            content="{{Item|name=Item 1}}",
            metadata=PageMetadata(summary="Update item 1"),
        )


class MockCharacterGenerator(PageGenerator):
    """Mock character page generator for testing."""

    def get_pages_to_fetch(self) -> list[str]:
        return ["Character 1"]

    def generate_pages(self):
        yield GeneratedPage(
            title="Character 1",
            content="{{Character|name=Character 1}}",
            metadata=PageMetadata(summary="Update character 1"),
        )


@pytest.fixture
def mock_context():
    """Create mock generator context."""
    return Mock(spec=GeneratorContext)


@pytest.fixture
def mock_registry(monkeypatch):
    """Mock the WIKI_GENERATORS registry."""
    mock_generators = [
        GeneratorRegistration(
            name="items",
            generator_class=MockItemGenerator,
            description="Item pages",
        ),
        GeneratorRegistration(
            name="characters",
            generator_class=MockCharacterGenerator,
            description="Character pages",
        ),
    ]
    monkeypatch.setattr(
        "erenshor.application.wiki.generators.registry.WIKI_GENERATORS",
        mock_generators,
    )
    return mock_generators


class TestGetGeneratorsByName:
    """Test get_generators_by_name function."""

    def test_get_all_generators(self, mock_context, mock_registry):
        """Test getting all generators when no filter provided."""
        pairs = get_generators_by_name(mock_context)

        assert len(pairs) == 2
        assert isinstance(pairs[0][1], MockItemGenerator)
        assert isinstance(pairs[1][1], MockCharacterGenerator)

    def test_get_filtered_generators(self, mock_context, mock_registry):
        """Test filtering generators by name."""
        pairs = get_generators_by_name(mock_context, ["items"])

        assert len(pairs) == 1
        assert isinstance(pairs[0][1], MockItemGenerator)

    def test_get_multiple_filtered_generators(self, mock_context, mock_registry):
        """Test filtering multiple generators."""
        pairs = get_generators_by_name(mock_context, ["items", "characters"])

        assert len(pairs) == 2
        assert isinstance(pairs[0][1], MockItemGenerator)
        assert isinstance(pairs[1][1], MockCharacterGenerator)

    def test_invalid_generator_name(self, mock_context, mock_registry):
        """Test error when requesting unknown generator."""
        with pytest.raises(ValueError, match=r"Unknown generator.*invalid_name"):
            get_generators_by_name(mock_context, ["invalid_name"])

    def test_mixed_valid_invalid_names(self, mock_context, mock_registry):
        """Test error when mixing valid and invalid names."""
        with pytest.raises(ValueError, match=r"Unknown generator.*weapons"):
            get_generators_by_name(mock_context, ["items", "weapons"])


class TestListGenerators:
    """Test list_generators function."""

    def test_list_all_generators(self, mock_registry):
        """Test listing all registered generators."""
        generators = list_generators()

        assert len(generators) == 2
        assert generators[0] == ("items", "Item pages", True)
        assert generators[1] == ("characters", "Character pages", True)

    def test_empty_registry(self, monkeypatch):
        """Test listing when registry is empty."""
        monkeypatch.setattr(
            "erenshor.application.wiki.generators.registry.WIKI_GENERATORS",
            [],
        )

        generators = list_generators()
        assert generators == []
