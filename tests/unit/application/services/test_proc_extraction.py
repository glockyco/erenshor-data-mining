"""Tests for proc extraction in ItemEnricher.

Tests the complete proc extraction pipeline including priority order,
proc style determination, and integration with SpellRepository.
"""

from unittest.mock import MagicMock

import pytest

from erenshor.application.enrichers.item_enricher import ItemEnricher, ProcInfo
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.spell import Spell


@pytest.fixture
def mock_item_repo():
    """Create mock item repository."""
    repo = MagicMock()
    repo.get_item_stats.return_value = []
    repo.get_item_classes.return_value = []
    return repo


@pytest.fixture
def mock_spell_repo():
    """Create mock spell repository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def enricher(mock_item_repo, mock_spell_repo):
    """Create item enricher with mocked repositories."""
    from unittest.mock import Mock

    mock_character_repo = Mock()
    mock_character_repo.get_vendors_selling_item.return_value = []
    mock_character_repo.get_characters_dropping_item.return_value = []

    mock_quest_repo = Mock()
    mock_quest_repo.get_quests_rewarding_item.return_value = []
    mock_quest_repo.get_quests_requiring_item.return_value = []

    # Mock item repository source methods
    mock_item_repo.get_items_producing_item.return_value = []
    mock_item_repo.get_items_requiring_item.return_value = []
    mock_item_repo.get_crafting_recipe.return_value = None

    return ItemEnricher(
        item_repo=mock_item_repo,
        spell_repo=mock_spell_repo,
        character_repo=mock_character_repo,
        quest_repo=mock_quest_repo,
    )


class TestProcExtraction:
    """Test proc extraction from items."""

    def test_weapon_proc_on_hit_weapon_style_attack(self, enricher, mock_spell_repo):
        """Test WeaponProcOnHit on weapon (not shield) uses Attack style."""
        # Setup spell mock
        mock_spell_repo.get_spell_by_stable_key.return_value = Spell(
            spell_db_index=1,
            id="1",
            resource_name="ARC - Ethereal Rend",
            stable_key="spell:arc - ethereal rend",
            spell_name="Ethereal Rend",
            spell_desc="Rend your target with ethereal energy.",
        )

        item = Item(
            id="1",
            resource_name="HAND - 6 - Lamplighter's Spark",
            stable_key="item:hand - 6 - lamplighter's spark",
            item_name="Lamplighter's Spark",
            required_slot="PrimaryOrSecondary",
            weapon_proc_on_hit_stable_key="spell:arc - ethereal rend",
            weapon_proc_chance=2.0,
            shield=0,
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.stable_key == "spell:arc - ethereal rend"
        assert result.proc.description == "Rend your target with ethereal energy."
        assert result.proc.proc_chance == "2"
        assert result.proc.proc_style == "Attack"

    def test_weapon_proc_on_hit_shield_style_bash(self, enricher, mock_spell_repo):
        """Test WeaponProcOnHit on shield uses Bash style."""
        # Setup spell mock
        mock_spell_repo.get_spell_by_stable_key.return_value = Spell(
            spell_db_index=1,
            id="1",
            resource_name="GEN - Stun",
            stable_key="spell:gen - stun",
            spell_name="Stun",
            spell_desc="Briefly stun your target, rendering it helpless.",
        )

        item = Item(
            id="1",
            resource_name="SECONDARY - 1 - Old Buckler",
            stable_key="item:secondary - 1 - old buckler",
            item_name="Old Buckler",
            required_slot="Secondary",
            weapon_proc_on_hit_stable_key="spell:gen - stun",
            weapon_proc_chance=75.0,
            shield=1,
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.stable_key == "spell:gen - stun"
        assert result.proc.description == "Briefly stun your target, rendering it helpless."
        assert result.proc.proc_chance == "75"
        assert result.proc.proc_style == "Bash"

    def test_weapon_proc_on_hit_armor_style_cast(self, enricher, mock_spell_repo):
        """Test WeaponProcOnHit on armor uses Cast style."""
        # Setup spell mock
        mock_spell_repo.get_spell_by_stable_key.return_value = Spell(
            spell_db_index=1,
            id="1",
            resource_name="GEN - Some Proc",
            stable_key="spell:gen - some proc",
            spell_name="Some Proc",
            spell_desc="A proc on armor.",
        )

        item = Item(
            id="1",
            resource_name="CHEST - 10 - Magic Armor",
            stable_key="item:chest - 10 - magic armor",
            item_name="Magic Armor",
            required_slot="Chest",
            weapon_proc_on_hit_stable_key="spell:gen - some proc",
            weapon_proc_chance=10.0,
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.proc_style == "Cast"

    def test_wand_effect_uses_attack_style(self, enricher, mock_spell_repo):
        """Test WandEffect uses Attack style."""
        mock_spell_repo.get_spell_by_stable_key.return_value = Spell(
            spell_db_index=1,
            id="1",
            resource_name="ARC - Fireball",
            stable_key="spell:arc - fireball",
            spell_name="Fireball",
            spell_desc="Launch a fireball.",
        )

        item = Item(
            id="1",
            resource_name="WAND - 1 - Fire Wand",
            stable_key="item:wand - 1 - fire wand",
            item_name="Fire Wand",
            required_slot="Primary",
            wand_effect_stable_key="spell:arc - fireball",
            wand_proc_chance=100.0,
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.stable_key == "spell:arc - fireball"
        assert result.proc.proc_style == "Attack"
        assert result.proc.proc_chance == "100"

    def test_bow_effect_uses_attack_style(self, enricher, mock_spell_repo):
        """Test BowEffect uses Attack style."""
        mock_spell_repo.get_spell_by_stable_key.return_value = Spell(
            spell_db_index=1,
            id="1",
            resource_name="GEN - Poison Arrow",
            stable_key="spell:gen - poison arrow",
            spell_name="Poison Arrow",
            spell_desc="Poison the target.",
        )

        item = Item(
            id="1",
            resource_name="BOW - 1 - Poison Bow",
            stable_key="item:bow - 1 - poison bow",
            item_name="Poison Bow",
            required_slot="Primary",
            bow_effect_stable_key="spell:gen - poison arrow",
            bow_proc_chance=50.0,
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.stable_key == "spell:gen - poison arrow"
        assert result.proc.proc_style == "Attack"
        assert result.proc.proc_chance == "50"

    def test_worn_effect_uses_worn_style_no_chance(self, enricher, mock_spell_repo):
        """Test WornEffect uses Worn style with no proc chance."""
        mock_spell_repo.get_spell_by_stable_key.return_value = Spell(
            spell_db_index=1,
            id="1",
            resource_name="GEN - Regen Aura",
            stable_key="spell:gen - regen aura",
            spell_name="Regeneration Aura",
            spell_desc="Regenerate health while worn.",
        )

        item = Item(
            id="1",
            resource_name="RING - 10 - Regen Ring",
            stable_key="item:ring - 10 - regen ring",
            item_name="Regeneration Ring",
            required_slot="Finger",
            worn_effect_stable_key="spell:gen - regen aura",
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.stable_key == "spell:gen - regen aura"
        assert result.proc.proc_style == "Worn"
        assert result.proc.proc_chance == ""  # No chance for worn effects

    def test_item_effect_on_click_uses_activatable_style_no_chance(self, enricher, mock_spell_repo):
        """Test ItemEffectOnClick uses Activatable style with no proc chance."""
        mock_spell_repo.get_spell_by_stable_key.return_value = Spell(
            spell_db_index=1,
            id="1",
            resource_name="DRU - Tangle",
            stable_key="spell:dru - tangle",
            spell_name="Tangle",
            spell_desc="Immobilize a target for a short time.",
        )

        item = Item(
            id="1",
            resource_name="NECK - 9 - Ogre Tooth Necklace",
            stable_key="item:neck - 9 - ogre tooth necklace",
            item_name="A Grassland Sap Necklace",
            required_slot="Neck",
            item_effect_on_click_stable_key="spell:dru - tangle",
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.stable_key == "spell:dru - tangle"
        assert result.proc.description == "Immobilize a target for a short time."
        assert result.proc.proc_style == "Activatable"
        assert result.proc.proc_chance == ""  # No chance for activatable

    def test_proc_priority_weapon_proc_over_item_effect(self, enricher, mock_spell_repo):
        """Test WeaponProcOnHit takes priority over ItemEffectOnClick."""
        stun_spell = Spell(
            spell_db_index=1,
            id="1",
            resource_name="GEN - Stun",
            stable_key="spell:gen - stun",
            spell_name="Stun",
            spell_desc="Stun the target.",
        )

        # Setup mock to return appropriate spell
        mock_spell_repo.get_spell_by_stable_key.return_value = stun_spell

        item = Item(
            id="1",
            resource_name="TEST",
            stable_key="item:test",
            item_name="Test Item",
            required_slot="Primary",
            weapon_proc_on_hit_stable_key="spell:gen - stun",
            weapon_proc_chance=10.0,
            item_effect_on_click_stable_key="spell:dru - tangle",  # Should be ignored
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.stable_key == "spell:gen - stun"  # WeaponProcOnHit wins
        assert result.proc.proc_style == "Attack"

    def test_proc_priority_wand_effect_over_item_effect(self, enricher, mock_spell_repo):
        """Test WandEffect takes priority over ItemEffectOnClick."""
        fireball = Spell(
            spell_db_index=1,
            id="1",
            resource_name="ARC - Fireball",
            stable_key="spell:arc - fireball",
            spell_name="Fireball",
            spell_desc="Launch a fireball.",
        )

        mock_spell_repo.get_spell_by_stable_key.return_value = fireball

        item = Item(
            id="1",
            resource_name="TEST",
            stable_key="item:test",
            item_name="Test Wand",
            required_slot="Primary",
            wand_effect_stable_key="spell:arc - fireball",
            wand_proc_chance=100.0,
            item_effect_on_click_stable_key="spell:dru - tangle",  # Should be ignored
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.stable_key == "spell:arc - fireball"  # WandEffect wins

    def test_no_proc_when_no_proc_fields(self, enricher, mock_spell_repo):
        """Test items with no proc fields return None."""
        item = Item(
            id="1",
            resource_name="SWORD - 1 - Plain Sword",
            stable_key="item:sword - 1 - plain sword",
            item_name="Plain Sword",
            required_slot="Primary",
        )

        result = enricher.enrich(item)

        assert result.proc is None

    def test_no_proc_when_chance_is_zero(self, enricher, mock_spell_repo):
        """Test items with proc chance of 0 return None."""
        item = Item(
            id="1",
            resource_name="TEST",
            stable_key="item:test",
            item_name="Test",
            required_slot="Primary",
            weapon_proc_on_hit_stable_key="spell:gen - stun",
            weapon_proc_chance=0.0,  # Zero chance = no proc
        )

        result = enricher.enrich(item)

        assert result.proc is None

    def test_no_proc_when_spell_not_found(self, enricher, mock_spell_repo):
        """Test graceful handling when spell doesn't exist."""
        # Spell not found
        mock_spell_repo.get_spell_by_stable_key.return_value = None

        item = Item(
            id="1",
            resource_name="TEST",
            stable_key="item:test",
            item_name="Test",
            required_slot="Primary",
            weapon_proc_on_hit_stable_key="spell:invalid - spell",
            weapon_proc_chance=10.0,
        )

        result = enricher.enrich(item)

        assert result.proc is None

    def test_proc_chance_converted_to_int_string(self, enricher, mock_spell_repo):
        """Test proc chance is converted from float to int string."""
        mock_spell_repo.get_spell_by_stable_key.return_value = Spell(
            spell_db_index=1,
            id="1",
            resource_name="GEN - Test",
            stable_key="spell:gen - test",
            spell_name="Test",
            spell_desc="Test.",
        )

        item = Item(
            id="1",
            resource_name="TEST",
            stable_key="item:test",
            item_name="Test",
            required_slot="Primary",
            weapon_proc_on_hit_stable_key="spell:gen - test",
            weapon_proc_chance=75.5,  # Float value
        )

        result = enricher.enrich(item)

        assert result.proc is not None
        assert result.proc.proc_chance == "75"  # Converted to int string


class TestProcInfoDataclass:
    """Test ProcInfo dataclass."""

    def test_proc_info_initialization(self):
        """Test ProcInfo can be initialized with all fields."""
        proc = ProcInfo(
            stable_key="spell:gen - stun",
            description="Stun the target.",
            proc_chance="75",
            proc_style="Bash",
        )

        assert proc.stable_key == "spell:gen - stun"
        assert proc.description == "Stun the target."
        assert proc.proc_chance == "75"
        assert proc.proc_style == "Bash"

    def test_proc_info_stores_raw_data(self):
        """Test ProcInfo stores raw data, not formatted strings."""
        proc = ProcInfo(
            stable_key="spell:gen - stun",
            description="Stun the target.",
            proc_chance="75",
            proc_style="Bash",
        )

        # Should be raw strings, not formatted wiki markup
        assert "{{" not in proc.stable_key
        assert "[[" not in proc.stable_key
        assert proc.stable_key == "spell:gen - stun"  # Just the stable key
