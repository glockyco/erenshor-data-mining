"""Tests for page normalization."""

import pytest

from erenshor.application.wiki.generators.page_normalizer import PageNormalizer


class TestPageNormalizer:
    """Test PageNormalizer class."""

    @pytest.fixture
    def normalizer(self) -> PageNormalizer:
        """Create PageNormalizer instance."""
        return PageNormalizer()

    def test_extract_single_category(self, normalizer: PageNormalizer) -> None:
        """Test extracting single category tag."""
        wikitext = "[[Category:Weapons]]\n{{Item|name=Sword}}"
        categories = normalizer._extract_categories(wikitext)
        assert categories == ["[[Category:Weapons]]"]

    def test_extract_multiple_categories(self, normalizer: PageNormalizer) -> None:
        """Test extracting multiple category tags."""
        wikitext = "[[Category:Weapons]]\n[[Category:Items]]\n{{Item|name=Sword}}"
        categories = normalizer._extract_categories(wikitext)
        assert categories == ["[[Category:Weapons]]", "[[Category:Items]]"]

    def test_extract_categories_from_middle(self, normalizer: PageNormalizer) -> None:
        """Test extracting categories scattered throughout page."""
        wikitext = "[[Category:A]]\nContent\n[[Category:B]]\nMore content\n[[Category:C]]"
        categories = normalizer._extract_categories(wikitext)
        assert categories == ["[[Category:A]]", "[[Category:B]]", "[[Category:C]]"]

    def test_extract_deduplicates_categories(self, normalizer: PageNormalizer) -> None:
        """Test duplicate categories are deduplicated during extraction."""
        wikitext = "[[Category:Items]]\n[[Category:Items]]\n[[Category:Weapons]]"
        categories = normalizer._extract_categories(wikitext)
        assert categories == ["[[Category:Items]]", "[[Category:Weapons]]"]

    def test_extract_no_categories(self, normalizer: PageNormalizer) -> None:
        """Test extracting from page with no categories."""
        wikitext = "{{Item|name=Sword}}"
        categories = normalizer._extract_categories(wikitext)
        assert categories == []

    def test_remove_categories(self, normalizer: PageNormalizer) -> None:
        """Test removing all category tags from wikitext."""
        wikitext = "[[Category:Weapons]]\n[[Category:Items]]\n{{Item|name=Sword}}"
        result = normalizer._remove_categories(wikitext)
        assert result == "{{Item|name=Sword}}"

    def test_remove_categories_preserves_content(self, normalizer: PageNormalizer) -> None:
        """Test removing categories doesn't affect other content."""
        wikitext = "[[Category:A]]\nLine 1\n[[Category:B]]\nLine 2"
        result = normalizer._remove_categories(wikitext)
        assert result == "Line 1\nLine 2"

    def test_normalize_empty_lines_two_to_one(self, normalizer: PageNormalizer) -> None:
        """Test normalizing two empty lines to one."""
        wikitext = "Line 1\n\n\nLine 2"
        result = normalizer._normalize_empty_lines(wikitext)
        assert result == "Line 1\n\nLine 2"

    def test_normalize_empty_lines_many_to_one(self, normalizer: PageNormalizer) -> None:
        """Test normalizing many empty lines to one."""
        wikitext = "Line 1\n\n\n\n\n\nLine 2"
        result = normalizer._normalize_empty_lines(wikitext)
        assert result == "Line 1\n\nLine 2"

    def test_normalize_empty_lines_preserves_single(self, normalizer: PageNormalizer) -> None:
        """Test single empty line is preserved."""
        wikitext = "Line 1\n\nLine 2"
        result = normalizer._normalize_empty_lines(wikitext)
        assert result == "Line 1\n\nLine 2"

    def test_normalize_no_empty_lines(self, normalizer: PageNormalizer) -> None:
        """Test content with no empty lines is unchanged."""
        wikitext = "Line 1\nLine 2\nLine 3"
        result = normalizer._normalize_empty_lines(wikitext)
        assert result == "Line 1\nLine 2\nLine 3"

    def test_normalize_categories_at_top(self, normalizer: PageNormalizer) -> None:
        """Test categories are placed at top of page."""
        wikitext = "Content\n[[Category:Weapons]]\n[[Category:Items]]"
        result = normalizer.normalize(wikitext)
        lines = result.split("\n")
        assert lines[0] == "[[Category:Items]]"
        assert lines[1] == "[[Category:Weapons]]"
        assert lines[2] == ""  # Empty line after categories
        assert lines[3] == "Content"

    def test_normalize_sorts_categories(self, normalizer: PageNormalizer) -> None:
        """Test categories are sorted alphabetically."""
        wikitext = "[[Category:Z]]\n[[Category:A]]\n[[Category:M]]\nContent"
        result = normalizer.normalize(wikitext)
        lines = result.split("\n")
        assert lines[0] == "[[Category:A]]"
        assert lines[1] == "[[Category:M]]"
        assert lines[2] == "[[Category:Z]]"

    def test_normalize_removes_legacy_categories(self, normalizer: PageNormalizer) -> None:
        """Test legacy categories are filtered out."""
        wikitext = "[[Category:The Bone Pits]]\n[[Category:Enemies]]\nContent"
        result = normalizer.normalize(wikitext)
        assert "[[Category:The Bone Pits]]" not in result
        assert "[[Category:Enemies]]" in result

    def test_normalize_adds_empty_line_after_categories(self, normalizer: PageNormalizer) -> None:
        """Test empty line is added after category block."""
        wikitext = "[[Category:Items]]{{Item|name=Sword}}"
        result = normalizer.normalize(wikitext)
        assert result == "[[Category:Items]]\n\n{{Item|name=Sword}}\n"

    def test_normalize_no_categories_no_empty_line(self, normalizer: PageNormalizer) -> None:
        """Test no empty line added when there are no categories."""
        wikitext = "{{Item|name=Sword}}"
        result = normalizer.normalize(wikitext)
        assert result == "{{Item|name=Sword}}\n"

    def test_normalize_merges_old_and_new_categories(self, normalizer: PageNormalizer) -> None:
        """Test merging categories from old and new wikitext."""
        old_wikitext = "[[Category:Manual]]\nManual content"
        new_wikitext = "[[Category:Generated]]\nGenerated content"
        result = normalizer.normalize(old_wikitext, new_wikitext)
        assert "[[Category:Generated]]" in result
        assert "[[Category:Manual]]" in result

    def test_normalize_merge_deduplicates(self, normalizer: PageNormalizer) -> None:
        """Test merging deduplicates categories present in both old and new."""
        old_wikitext = "[[Category:Items]]\n[[Category:Manual]]\nContent"
        new_wikitext = "[[Category:Items]]\n[[Category:Generated]]\nContent"
        result = normalizer.normalize(old_wikitext, new_wikitext)
        # Items should appear only once
        assert result.count("[[Category:Items]]") == 1
        assert "[[Category:Generated]]" in result
        assert "[[Category:Manual]]" in result

    def test_normalize_real_world_character_page(self, normalizer: PageNormalizer) -> None:
        """Test normalizing real character page with scattered categories."""
        wikitext = """[[Category:Enemies]]
[[Category:Port Azure]]
{{Enemy
|name=Guard
|level=10
}}

Some manual content here.

[[Category:Vendors]]"""
        result = normalizer.normalize(wikitext)
        lines = result.split("\n")
        # All categories at top, sorted
        assert lines[0] == "[[Category:Enemies]]"
        assert lines[1] == "[[Category:Port Azure]]"
        assert lines[2] == "[[Category:Vendors]]"
        assert lines[3] == ""  # Empty line
        # Content follows
        assert "{{Enemy" in result
        assert "Some manual content here." in result

    def test_normalize_removes_excessive_spacing(self, normalizer: PageNormalizer) -> None:
        """Test normalizing removes excessive empty lines."""
        wikitext = """[[Category:Items]]


{{Item|name=Sword}}



Some description.


More content."""
        result = normalizer.normalize(wikitext)
        # Should not have more than 1 consecutive empty line anywhere
        assert "\n\n\n" not in result
        assert "[[Category:Items]]" in result
        # Verify content sections have max 1 empty line between them
        assert "Some description.\n\nMore content." in result
        assert "{{Item|name=Sword}}\n\nSome description." in result
        # Verify ends with newline
        assert result.endswith("\n")

    def test_normalize_preserves_one_empty_line_between_sections(self, normalizer: PageNormalizer) -> None:
        """Test one empty line between sections is preserved."""
        wikitext = """[[Category:Items]]

{{Item|name=Sword}}

Description paragraph."""
        result = normalizer.normalize(wikitext)
        lines = result.split("\n")
        # Categories
        assert lines[0] == "[[Category:Items]]"
        assert lines[1] == ""  # Empty after categories
        # Template
        assert "{{Item|name=Sword}}" in result
        # Should have single empty line between template and description
        assert "\n\nDescription paragraph." in result

    def test_normalize_complex_merge_scenario(self, normalizer: PageNormalizer) -> None:
        """Test complex scenario with old manual categories and new generated ones."""
        old_wikitext = """[[Category:Manual Category]]
[[Category:Zone A]]


{{Enemy
|name=Boss
}}

Manually written lore section.

[[Category:Another Manual]]"""
        new_wikitext = """[[Category:Zone A]]
[[Category:Zone B]]
[[Category:Enemies]]
{{Enemy
|name=Boss
|updated=true
}}"""
        result = normalizer.normalize(old_wikitext, new_wikitext)
        lines = result.split("\n")

        # All unique categories, sorted
        assert lines[0] == "[[Category:Another Manual]]"
        assert lines[1] == "[[Category:Enemies]]"
        assert lines[2] == "[[Category:Manual Category]]"
        assert lines[3] == "[[Category:Zone A]]"
        assert lines[4] == "[[Category:Zone B]]"
        assert lines[5] == ""  # Empty line after categories

        # Zone A should appear only once (was in both)
        assert result.count("[[Category:Zone A]]") == 1

        # Manual content preserved
        assert "Manually written lore section." in result

    def test_legacy_categories_constant(self, normalizer: PageNormalizer) -> None:
        """Test LEGACY_CATEGORIES contains expected values."""
        assert "[[Category:The Bone Pits]]" in normalizer.LEGACY_CATEGORIES

    def test_normalize_always_ends_with_newline(self, normalizer: PageNormalizer) -> None:
        """Test normalized pages always end with newline."""
        # Page with categories
        result1 = normalizer.normalize("[[Category:Items]]\nContent")
        assert result1.endswith("\n")

        # Page without categories
        result2 = normalizer.normalize("Content only")
        assert result2.endswith("\n")

        # Empty page
        result3 = normalizer.normalize("")
        assert result3 == ""

        # Page already ending with newline
        result4 = normalizer.normalize("Content\n")
        assert result4.endswith("\n")
        # Should have exactly one trailing newline
        assert not result4.endswith("\n\n")
