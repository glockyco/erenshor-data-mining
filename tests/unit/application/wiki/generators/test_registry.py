"""Unit tests for wiki generator registry."""

from unittest.mock import Mock

import pytest

from erenshor.application.wiki.generators.base import GeneratedPage, PageGenerator, PageMetadata
from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.generators.registry import GeneratorRegistration, get_generators_by_name


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
            factory=MockItemGenerator,
            description="Item pages",
        ),
        GeneratorRegistration(
            name="characters",
            factory=MockCharacterGenerator,
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
        """Without a filter, every registered generator runs in registry order."""
        generators = get_generators_by_name(mock_context)

        assert [type(generator) for generator in generators] == [MockItemGenerator, MockCharacterGenerator]

    def test_get_filtered_generators(self, mock_context, mock_registry):
        """A filter selects only the named generators."""
        generators = get_generators_by_name(mock_context, ["characters"])

        assert [type(generator) for generator in generators] == [MockCharacterGenerator]

    def test_invalid_generator_name(self, mock_context, mock_registry):
        """Test error when requesting unknown generator."""
        with pytest.raises(ValueError, match=r"Unknown generator.*invalid_name"):
            get_generators_by_name(mock_context, ["invalid_name"])

    def test_mixed_valid_invalid_names(self, mock_context, mock_registry):
        """Test error when mixing valid and invalid names."""
        with pytest.raises(ValueError, match=r"Unknown generator.*weapons"):
            get_generators_by_name(mock_context, ["items", "weapons"])
