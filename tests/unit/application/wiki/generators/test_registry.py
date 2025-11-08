"""Unit tests for wiki generator registry."""

from unittest.mock import Mock

import pytest

from erenshor.application.wiki.generators.base import GeneratedPage, PageGenerator, PageMetadata
from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.generators.registry import (
    GeneratorRegistration,
    detect_conflicts,
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
        generators = get_generators_by_name(mock_context)

        assert len(generators) == 2
        assert isinstance(generators[0], MockItemGenerator)
        assert isinstance(generators[1], MockCharacterGenerator)

    def test_get_filtered_generators(self, mock_context, mock_registry):
        """Test filtering generators by name."""
        generators = get_generators_by_name(mock_context, ["items"])

        assert len(generators) == 1
        assert isinstance(generators[0], MockItemGenerator)

    def test_get_multiple_filtered_generators(self, mock_context, mock_registry):
        """Test filtering multiple generators."""
        generators = get_generators_by_name(mock_context, ["items", "characters"])

        assert len(generators) == 2
        assert isinstance(generators[0], MockItemGenerator)
        assert isinstance(generators[1], MockCharacterGenerator)

    def test_invalid_generator_name(self, mock_context, mock_registry):
        """Test error when requesting unknown generator."""
        with pytest.raises(ValueError, match=r"Unknown generator.*invalid_name"):
            get_generators_by_name(mock_context, ["invalid_name"])

    def test_mixed_valid_invalid_names(self, mock_context, mock_registry):
        """Test error when mixing valid and invalid names."""
        with pytest.raises(ValueError, match=r"Unknown generator.*weapons"):
            get_generators_by_name(mock_context, ["items", "weapons"])


class TestDetectConflicts:
    """Test detect_conflicts function."""

    def test_no_conflicts(self):
        """Test when all pages have unique titles."""
        pages = [
            GeneratedPage(
                title="Page 1",
                content="Content 1",
                metadata=PageMetadata(summary="Update 1"),
            ),
            GeneratedPage(
                title="Page 2",
                content="Content 2",
                metadata=PageMetadata(summary="Update 2"),
            ),
        ]

        conflicts = detect_conflicts(pages)
        assert conflicts == {}

    def test_single_conflict(self):
        """Test detecting a single page title conflict."""
        page1 = GeneratedPage(
            title="Duplicate",
            content="Content 1",
            metadata=PageMetadata(summary="Update 1"),
        )
        page2 = GeneratedPage(
            title="Duplicate",
            content="Content 2",
            metadata=PageMetadata(summary="Update 2"),
        )
        pages = [page1, page2]

        conflicts = detect_conflicts(pages)

        assert len(conflicts) == 1
        assert "Duplicate" in conflicts
        assert conflicts["Duplicate"] == [page1, page2]

    def test_multiple_conflicts(self):
        """Test detecting multiple page title conflicts."""
        pages = [
            GeneratedPage("Title A", "Content 1", PageMetadata("Update 1")),
            GeneratedPage("Title A", "Content 2", PageMetadata("Update 2")),
            GeneratedPage("Title B", "Content 3", PageMetadata("Update 3")),
            GeneratedPage("Title B", "Content 4", PageMetadata("Update 4")),
            GeneratedPage("Title C", "Content 5", PageMetadata("Update 5")),
        ]

        conflicts = detect_conflicts(pages)

        assert len(conflicts) == 2
        assert "Title A" in conflicts
        assert "Title B" in conflicts
        assert "Title C" not in conflicts
        assert len(conflicts["Title A"]) == 2
        assert len(conflicts["Title B"]) == 2

    def test_empty_pages_list(self):
        """Test with empty pages list."""
        conflicts = detect_conflicts([])
        assert conflicts == {}


class TestListGenerators:
    """Test list_generators function."""

    def test_list_all_generators(self, mock_registry):
        """Test listing all registered generators."""
        generators = list_generators()

        assert len(generators) == 2
        assert generators[0] == ("items", "Item pages")
        assert generators[1] == ("characters", "Character pages")

    def test_empty_registry(self, monkeypatch):
        """Test listing when registry is empty."""
        monkeypatch.setattr(
            "erenshor.application.wiki.generators.registry.WIKI_GENERATORS",
            [],
        )

        generators = list_generators()
        assert generators == []
