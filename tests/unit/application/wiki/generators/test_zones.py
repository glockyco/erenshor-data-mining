"""Unit tests for the zone page generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.generators.pages.zones import ZonePageGenerator
from erenshor.domain.entities.zone import Zone


def _make_zone(scene_name: str, wiki_page_name: str) -> Zone:
    """Build a minimal Zone entity for testing."""
    return Zone(
        stable_key=f"zone:{scene_name}",
        scene_name=scene_name,
        zone_name=wiki_page_name,
        is_dungeon=0,
        raid_capable=False,
        use_zone_as_temp_bind="",
        display_name=wiki_page_name,
        wiki_page_name=wiki_page_name,
        image_name="",
        is_wiki_generated=1,
        is_map_visible=1,
        achievement="",
    )


@pytest.fixture
def mock_context(tmp_path: Path) -> Mock:
    """Generator context with one zone and its map position."""
    ctx = Mock(spec=GeneratorContext)
    zone_repo = Mock()
    zone_repo.get_all_zones.return_value = [_make_zone("Soluna", "Soluna's Landing")]
    zone_repo.get_zone_connections.return_value = ["Loomingwood Forest", "Malaroth's Nesting Grounds"]
    ctx.zone_repo = zone_repo
    zone_positions_path = tmp_path / "zone-positions.json"
    zone_positions_path.write_text('{"Soluna": {}}', encoding="utf-8")
    ctx.zone_positions_path = zone_positions_path
    return ctx


class TestZonePositionsInput:
    """Zone pages are not generated without the map positions their links need."""

    @pytest.mark.parametrize(
        ("content", "error", "message"),
        [
            (None, FileNotFoundError, "zone-positions.json not found"),
            ("{not json", ValueError, "zone-positions.json is unreadable"),
            ('["Soluna"]', ValueError, "must map scene names to positions"),
        ],
    )
    def test_missing_or_malformed_positions_stop_generation(
        self, mock_context: Mock, tmp_path: Path, content: str | None, error: type[Exception], message: str
    ) -> None:
        positions = tmp_path / "zone-positions.json"
        if content is None:
            positions.unlink()
        else:
            positions.write_text(content, encoding="utf-8")

        with pytest.raises(error, match=message):
            ZonePageGenerator(mock_context)

    def test_zone_with_position_links_its_map(self, mock_context: Mock) -> None:
        (page,) = ZonePageGenerator(mock_context).generate_pages()

        assert "|maplink={{MapLink|zone=Soluna}}\n" in page.content
        assert "|connects=[[Loomingwood Forest]], [[Malaroth's Nesting Grounds]]\n" in page.content

    def test_zone_absent_from_positions_has_no_map_link(self, mock_context: Mock, tmp_path: Path) -> None:
        (tmp_path / "zone-positions.json").write_text('{"Elsewhere": {}}', encoding="utf-8")

        (page,) = ZonePageGenerator(mock_context).generate_pages()

        assert "MapLink" not in page.content
