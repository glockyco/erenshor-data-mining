"""Unit tests for wiki generator base classes."""

from erenshor.application.wiki.generators.base import GeneratedPage, PageMetadata


class TestPageMetadata:
    """Test PageMetadata dataclass."""

    def test_create_with_defaults(self):
        """Test creating metadata with default values."""
        metadata = PageMetadata(summary="Test edit")

        assert metadata.summary == "Test edit"
        assert metadata.minor is False
        assert metadata.tags == []

    def test_create_with_all_fields(self):
        """Test creating metadata with all fields."""
        metadata = PageMetadata(
            summary="Minor update",
            minor=True,
            tags=["automated", "bot-edit"],
        )

        assert metadata.summary == "Minor update"
        assert metadata.minor is True
        assert metadata.tags == ["automated", "bot-edit"]


class TestGeneratedPage:
    """Test GeneratedPage dataclass."""

    def test_create_page(self):
        """Test creating a generated page."""
        metadata = PageMetadata(summary="Update item data")
        page = GeneratedPage(
            title="Iron Sword",
            content="{{Item|name=Iron Sword}}",
            metadata=metadata,
        )

        assert page.title == "Iron Sword"
        assert page.content == "{{Item|name=Iron Sword}}"
        assert page.metadata.summary == "Update item data"
        assert page.metadata.minor is False
