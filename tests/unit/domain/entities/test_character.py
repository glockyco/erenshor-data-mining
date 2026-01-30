"""Tests for Character entity stable_key field."""

from erenshor.domain.entities.character import Character


class TestCharacterStableKey:
    """Tests for Character.stable_key field."""

    def test_prefab_character_stable_key(self):
        """Prefab characters can have stable_key set from database."""
        character = Character(
            stable_key="character:dire wolf",
            object_name="Dire Wolf",
            npc_name="A Dire Wolf",
            is_prefab=1,
            scene="Forest",
            x=100.5,
            y=20.3,
            z=50.7,
        )

        assert character.stable_key == "character:dire wolf"

    def test_non_prefab_character_stable_key(self):
        """Non-prefab characters have stable_key set from database."""
        character = Character(
            stable_key="character:town guard:azure:123.45:67.89:234.56",
            object_name="Town Guard",
            npc_name="Guard Captain",
            is_prefab=0,
            scene="Azure",
            x=123.45,
            y=67.89,
            z=234.56,
        )

        assert character.stable_key == "character:town guard:azure:123.45:67.89:234.56"

    def test_stable_key_required(self):
        """stable_key is required and must be provided."""
        character = Character(
            stable_key="character:wandering merchant",
            object_name="Wandering Merchant",
            npc_name="A Merchant",
            is_prefab=None,
            scene="Braxonian",
            x=50.0,
            y=10.0,
            z=75.0,
        )

        assert character.stable_key == "character:wandering merchant"

    def test_stable_key_independent_of_coordinates(self):
        """stable_key is set independently from coordinates."""
        character = Character(
            stable_key="character:mysterious npc:unknown:100.00:200.00:300.00",
            object_name="Mysterious NPC",
            npc_name="???",
            is_prefab=0,
            scene=None,
            x=100.0,
            y=200.0,
            z=300.0,
        )

        assert character.stable_key == "character:mysterious npc:unknown:100.00:200.00:300.00"

    def test_stable_key_independent_of_missing_coordinates(self):
        """stable_key is set independently, coordinates don't affect it."""
        character = Character(
            stable_key="character:static npc:temple:0.00:0.00:0.00",
            object_name="Static NPC",
            npc_name="Statue",
            is_prefab=0,
            scene="Temple",
            x=None,
            y=None,
            z=None,
        )

        assert character.stable_key == "character:static npc:temple:0.00:0.00:0.00"

    def test_stable_key_format_preserved(self):
        """stable_key format is preserved as set."""
        character = Character(
            stable_key="character:precise npc:workshop:1.20:3.46:10.00",
            object_name="Precise NPC",
            npc_name="Engineer",
            is_prefab=0,
            scene="Workshop",
            x=1.2,
            y=3.456789,
            z=10.0,
        )

        assert character.stable_key == "character:precise npc:workshop:1.20:3.46:10.00"

    def test_stable_key_allows_none_object_name(self):
        """stable_key field allows None object_name (validated at database level)."""
        character = Character(
            stable_key="character:unnamed",
            object_name=None,
            npc_name="Unnamed",
            is_prefab=1,
        )

        assert character.stable_key == "character:unnamed"

    def test_prefab_stable_key_format(self):
        """Prefab character stable_key format."""
        character = Character(
            stable_key="character:skeleton",
            object_name="Skeleton",
            npc_name="A Skeleton",
            is_prefab=1,
            scene="Dungeon",
            x=99.99,
            y=88.88,
            z=77.77,
        )

        # Prefab stable_key is set from database
        assert character.stable_key == "character:skeleton"

    def test_different_characters_different_keys(self):
        """Different characters have different stable_keys."""
        char1 = Character(
            stable_key="character:guard:city:10.00:20.00:30.00",
            object_name="Guard",
            npc_name="Guard #1",
            is_prefab=0,
            scene="City",
            x=10.0,
            y=20.0,
            z=30.0,
        )

        char2 = Character(
            stable_key="character:guard:city:40.00:50.00:60.00",
            object_name="Guard",
            npc_name="Guard #2",
            is_prefab=0,
            scene="City",
            x=40.0,
            y=50.0,
            z=60.0,
        )

        assert char1.stable_key != char2.stable_key
        assert char1.stable_key == "character:guard:city:10.00:20.00:30.00"
        assert char2.stable_key == "character:guard:city:40.00:50.00:60.00"
