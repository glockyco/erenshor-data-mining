"""Tests for Character entity stable_key logic."""

import pytest

from erenshor.domain.entities.character import Character


class TestCharacterStableKey:
    """Tests for Character.stable_key property."""

    def test_prefab_character_uses_simple_key(self):
        """Prefab characters use simple object_name format."""
        character = Character(
            id=1,
            object_name="Dire Wolf",
            npc_name="A Dire Wolf",
            is_prefab=1,
            scene="Forest",
            x=100.5,
            y=20.3,
            z=50.7,
        )

        assert character.stable_key == "character:dire wolf"

    def test_non_prefab_character_includes_coordinates(self):
        """Non-prefab characters include scene and coordinates in key."""
        character = Character(
            id=1,
            object_name="Town Guard",
            npc_name="Guard Captain",
            is_prefab=0,
            scene="Azure",
            x=123.45,
            y=67.89,
            z=234.56,
        )

        assert character.stable_key == "character:town guard|azure|123.45|67.89|234.56"

    def test_non_prefab_with_none_is_prefab_field(self):
        """Non-prefab with is_prefab=None defaults to coordinate format."""
        character = Character(
            id=1,
            object_name="Wandering Merchant",
            npc_name="A Merchant",
            is_prefab=None,
            scene="Braxonian",
            x=50.0,
            y=10.0,
            z=75.0,
        )

        # None is falsy, so should use coordinate format
        assert character.stable_key == "character:wandering merchant|braxonian|50.00|10.00|75.00"

    def test_non_prefab_with_missing_scene_uses_unknown(self):
        """Non-prefab without scene uses 'Unknown' placeholder."""
        character = Character(
            id=1,
            object_name="Mysterious NPC",
            npc_name="???",
            is_prefab=0,
            scene=None,
            x=100.0,
            y=200.0,
            z=300.0,
        )

        assert character.stable_key == "character:mysterious npc|unknown|100.00|200.00|300.00"

    def test_non_prefab_with_missing_coordinates_uses_zeros(self):
        """Non-prefab without coordinates uses 0.00 placeholders."""
        character = Character(
            id=1,
            object_name="Static NPC",
            npc_name="Statue",
            is_prefab=0,
            scene="Temple",
            x=None,
            y=None,
            z=None,
        )

        assert character.stable_key == "character:static npc|temple|0.00|0.00|0.00"

    def test_coordinates_formatted_to_two_decimals(self):
        """Coordinates are formatted with exactly 2 decimal places."""
        character = Character(
            id=1,
            object_name="Precise NPC",
            npc_name="Engineer",
            is_prefab=0,
            scene="Workshop",
            x=1.2,
            y=3.456789,
            z=10.0,
        )

        assert character.stable_key == "character:precise npc|workshop|1.20|3.46|10.00"

    def test_stable_key_raises_on_none_object_name(self):
        """stable_key raises ValueError if object_name is None."""
        character = Character(
            id=1,
            object_name=None,
            npc_name="Unnamed",
            is_prefab=1,
        )

        with pytest.raises(ValueError, match="Cannot generate stable_key: object_name is None"):
            _ = character.stable_key

    def test_prefab_ignores_coordinate_data(self):
        """Prefab characters ignore coordinate data even if present."""
        character = Character(
            id=1,
            object_name="Skeleton",
            npc_name="A Skeleton",
            is_prefab=1,
            scene="Dungeon",
            x=99.99,
            y=88.88,
            z=77.77,
        )

        # Prefab = simple key, coordinates ignored
        assert character.stable_key == "character:skeleton"

    def test_different_coordinates_produce_different_keys(self):
        """Same object_name with different coordinates produce unique keys."""
        char1 = Character(
            id=1,
            object_name="Guard",
            npc_name="Guard #1",
            is_prefab=0,
            scene="City",
            x=10.0,
            y=20.0,
            z=30.0,
        )

        char2 = Character(
            id=2,
            object_name="Guard",
            npc_name="Guard #2",
            is_prefab=0,
            scene="City",
            x=40.0,
            y=50.0,
            z=60.0,
        )

        assert char1.stable_key != char2.stable_key
        assert char1.stable_key == "character:guard|city|10.00|20.00|30.00"
        assert char2.stable_key == "character:guard|city|40.00|50.00|60.00"
