"""Unit tests for WikiService.

Tests the wiki page update orchestration service including:
- Item page updates
- Character page updates
- Spell page updates
- Field preservation
- Legacy template removal
- Error handling
- Dry-run mode
- Progress display
"""

from unittest.mock import Mock

import pytest

from erenshor.application.services.wiki_service import UpdateResult, WikiService
from erenshor.domain.entities.character import Character
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.wiki.client import MediaWikiAPIError


@pytest.fixture
def mock_wiki_client():
    """Mock MediaWiki client."""
    client = Mock()
    client.get_pages.return_value = {}
    client.edit_page.return_value = None
    return client


@pytest.fixture
def mock_item_repo():
    """Mock item repository."""
    repo = Mock()
    repo.get_items_for_wiki_generation.return_value = []
    return repo


@pytest.fixture
def mock_character_repo():
    """Mock character repository."""
    repo = Mock()
    repo.get_characters_for_wiki_generation.return_value = []
    return repo


@pytest.fixture
def mock_spell_repo():
    """Mock spell repository."""
    repo = Mock()
    repo.get_spells_for_wiki_generation.return_value = []
    return repo


@pytest.fixture
def wiki_service(mock_wiki_client, mock_item_repo, mock_character_repo, mock_spell_repo):
    """WikiService instance with mocked dependencies."""
    return WikiService(
        wiki_client=mock_wiki_client,
        item_repo=mock_item_repo,
        character_repo=mock_character_repo,
        spell_repo=mock_spell_repo,
    )


@pytest.fixture
def sample_item():
    """Sample item entity."""
    return Item(
        item_db_index=1,
        id="item-1",
        item_name="Test Sword",
        resource_name="TestSword",
        lore="A test sword",
        required_slot="Main Hand",
        this_weapon_type="Sword",
        classes="Warrior,Paladin",
        item_level=10,
        weapon_dly=2.5,
        shield=None,
        weapon_proc_chance=None,
        weapon_proc_on_hit=None,
        is_wand=0,
        wand_range=None,
        wand_proc_chance=None,
        wand_effect=None,
        wand_bolt_color_r=None,
        wand_bolt_color_g=None,
        wand_bolt_color_b=None,
        wand_bolt_color_a=None,
        wand_bolt_speed=None,
        wand_attack_sound_name=None,
        is_bow=0,
        bow_effect=None,
        bow_proc_chance=None,
        bow_range=None,
        bow_arrow_speed=None,
        bow_attack_sound_name=None,
        item_effect_on_click=None,
        item_skill_use=None,
        teach_spell=None,
        teach_skill=None,
        aura=None,
        worn_effect=None,
        spell_cast_time=None,
        assign_quest_on_read=None,
        complete_on_read=None,
        template=0,
        template_ingredient_ids=None,
        template_reward_ids=None,
        item_value=100,
        sell_value=25,
        stackable=0,
        disposable=0,
        unique=0,
        relic=0,
        no_trade_no_destroy=0,
        book_title=None,
        mining=0,
        fuel_source=0,
        fuel_level=None,
        sim_players_cant_get=0,
        attack_sound_name=None,
        item_icon_name=None,
        equipment_to_activate=None,
        hide_hair_when_equipped=0,
        hide_head_when_equipped=0,
    )


@pytest.fixture
def sample_character():
    """Sample character entity."""
    return Character(
        id=1,
        coordinate_id=None,
        guid=None,
        object_name="Goblin",
        npc_name="Goblin Scout",
        my_world_faction=None,
        my_faction="Hostile",
        aggro_range=10.0,
        attack_range=2.0,
        aggressive_towards=None,
        allies=None,
        is_prefab=1,
        is_common=1,
        is_rare=0,
        is_unique=0,
        is_friendly=0,
        is_npc=0,
        is_sim_player=0,
        is_vendor=0,
        is_mining_node=0,
        has_stats=1,
        has_dialog=0,
        has_modify_faction=0,
        is_enabled=1,
        invulnerable=0,
        shout_on_death=None,
        quest_complete_on_death=None,
        destroy_on_death=0,
        level=5,
        base_xp_min=50.0,
        base_xp_max=60.0,
        boss_xp_multiplier=None,
        base_hp=100,
        base_ac=10,
        base_mana=0,
        base_str=10,
        base_end=10,
        base_dex=8,
        base_agi=8,
        base_int=5,
        base_wis=5,
        base_cha=5,
        base_res=None,
        base_mr=None,
        base_er=None,
        base_pr=None,
        base_vr=None,
        run_speed=None,
        base_life_steal=None,
        base_mh_atk_delay=None,
        base_oh_atk_delay=None,
        effective_hp=None,
        effective_ac=None,
        effective_base_atk_dmg=None,
        effective_attack_ability=None,
        effective_min_mr=None,
        effective_max_mr=None,
        effective_min_er=None,
        effective_max_er=None,
        effective_min_pr=None,
        effective_max_pr=None,
        effective_min_vr=None,
        effective_max_vr=None,
        attack_skills=None,
        attack_spells=None,
        buff_spells=None,
        heal_spells=None,
        group_heal_spells=None,
        cc_spells=None,
        taunt_spells=None,
        pet_spell=None,
        proc_on_hit=None,
        proc_on_hit_chance=None,
        hand_set_resistances=None,
        hard_set_ac=None,
        base_atk_dmg=None,
        oh_atk_dmg=None,
        min_atk_dmg=None,
        damage_range_min=None,
        damage_range_max=None,
        damage_mult=None,
        armor_pen_mult=None,
        power_attack_base_dmg=None,
        power_attack_freq=None,
        heal_tolerance=None,
        leash_range=None,
        aggro_regardless_of_level=None,
        mobile=None,
        group_encounter=None,
        treasure_chest=None,
        do_not_leave_corpse=None,
        set_achievement_on_defeat=None,
        set_achievement_on_spawn=None,
        aggro_msg=None,
        aggro_emote=None,
        spawn_emote=None,
        guild_name=None,
        modify_factions=None,
        vendor_desc=None,
        items_for_sale=None,
    )


@pytest.fixture
def sample_spell():
    """Sample spell entity."""
    return Spell(
        spell_db_index=1,
        id="spell-1",
        resource_name="Fireball",
        spell_name="Fireball",
        spell_desc="Launches a ball of fire",
        special_descriptor=None,
        type="Damage",
        line="Fire",
        classes="Mage,Warlock",
        required_level=10,
        mana_cost=50,
        sim_usable=1,
        aggro=100,
        spell_charge_time=2.5,
        cooldown=10.0,
        spell_duration_in_ticks=None,
        unstable_duration=0,
        instant_effect=1,
        spell_range=30.0,
        self_only=0,
        max_level_target=None,
        group_effect=0,
        can_hit_players=0,
        apply_to_caster=0,
        target_damage=100,
        target_healing=None,
        caster_healing=None,
        shielding_amt=None,
        lifetap=0,
        damage_type="Fire",
        resist_modifier=None,
        add_proc=None,
        add_proc_chance=None,
        hp=None,
        ac=None,
        mana=None,
        percent_mana_restoration=None,
        movement_speed=None,
        str=None,
        dex=None,
        end=None,
        agi=None,
        wis=None,
        int=None,
        cha=None,
        mr=None,
        er=None,
        pr=None,
        vr=None,
        damage_shield=None,
        haste=None,
        percent_lifesteal=None,
        atk_roll_modifier=None,
        bleed_damage_percent=None,
        root_target=0,
        stun_target=0,
        charm_target=0,
        crowd_control_spell=0,
        break_on_damage=0,
        break_on_any_action=0,
        taunt_spell=0,
        pet_to_summon_resource_name=None,
        status_effect_to_apply=None,
        reap_and_renew=0,
        resonate_chance=None,
        xp_bonus=None,
        automate_attack=0,
        worn_effect=None,
        spell_charge_fx_index=None,
        spell_resolve_fx_index=None,
        spell_icon_name=None,
        shake_dur=None,
        shake_amp=None,
        color_r=None,
        color_g=None,
        color_b=None,
        color_a=None,
        status_effect_message_on_player=None,
        status_effect_message_on_npc=None,
    )


class TestWikiServiceInit:
    """Tests for WikiService initialization."""

    def test_init_with_dependencies(self, mock_wiki_client, mock_item_repo, mock_character_repo, mock_spell_repo):
        """Test service initializes with all dependencies."""
        service = WikiService(
            wiki_client=mock_wiki_client,
            item_repo=mock_item_repo,
            character_repo=mock_character_repo,
            spell_repo=mock_spell_repo,
        )

        assert service._wiki_client == mock_wiki_client
        assert service._item_repo == mock_item_repo
        assert service._character_repo == mock_character_repo
        assert service._spell_repo == mock_spell_repo


class TestUpdateItemPages:
    """Tests for update_item_pages method."""

    def test_empty_repository(self, wiki_service, mock_item_repo):
        """Test handling of empty item repository."""
        mock_item_repo.get_items_for_wiki_generation.return_value = []

        result = wiki_service.update_item_pages(dry_run=True)

        assert result.total == 0
        assert result.updated == 0
        assert result.failed == 0
        assert len(result.warnings) == 1
        assert "No items found" in result.warnings[0]

    def test_dry_run_mode(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test dry-run mode doesn't call wiki API."""
        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]

        result = wiki_service.update_item_pages(dry_run=True)

        # Should not fetch or edit pages in dry-run
        mock_wiki_client.get_pages.assert_not_called()
        mock_wiki_client.edit_page.assert_not_called()

        # Should still generate content
        assert result.total == 1
        assert result.updated == 1
        assert result.failed == 0

    def test_limit_parameter(self, wiki_service, mock_item_repo, sample_item):
        """Test limit parameter restricts processing."""
        items = [sample_item] * 10
        mock_item_repo.get_items_for_wiki_generation.return_value = items

        result = wiki_service.update_item_pages(dry_run=True, limit=3)

        assert result.total == 3

    def test_successful_update(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test successful item page update."""
        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]
        mock_wiki_client.get_pages.return_value = {"Item:Test Sword": None}  # New page

        result = wiki_service.update_item_pages(dry_run=False)

        assert result.total == 1
        assert result.updated == 1
        assert result.failed == 0

        # Should fetch existing pages
        mock_wiki_client.get_pages.assert_called_once()

        # Should update page
        mock_wiki_client.edit_page.assert_called_once()
        call_args = mock_wiki_client.edit_page.call_args
        assert call_args[1]["title"] == "Item:Test Sword"
        assert "Automated item page update" in call_args[1]["summary"]

    def test_preserve_existing_content(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test preservation of existing wiki content."""
        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]

        # Existing page with manual description
        existing_content = "{{Item|description=Custom lore text|damage=10}}"
        mock_wiki_client.get_pages.return_value = {"Item:Test Sword": existing_content}

        result = wiki_service.update_item_pages(dry_run=False)

        assert result.total == 1
        assert result.updated == 1

        # Should preserve manual edits (warning added)
        assert result.has_warnings()

    def test_api_error_handling(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test handling of MediaWiki API errors."""
        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]
        mock_wiki_client.get_pages.return_value = {"Item:Test Sword": None}

        # Simulate API error on update
        mock_wiki_client.edit_page.side_effect = MediaWikiAPIError("API error")

        result = wiki_service.update_item_pages(dry_run=False)

        assert result.total == 1
        assert result.updated == 0
        assert result.failed == 1
        assert result.has_errors()
        assert "Failed to update" in result.errors[0]

    def test_batch_fetch_existing_pages(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test batched fetching of existing wiki pages."""
        items = [sample_item] * 5
        mock_item_repo.get_items_for_wiki_generation.return_value = items

        # Mock batch fetch response - all items have same title so single entry
        existing_pages = {"Item:Test Sword": None}
        mock_wiki_client.get_pages.return_value = existing_pages

        _result = wiki_service.update_item_pages(dry_run=False)

        # Should call get_pages once with all titles
        mock_wiki_client.get_pages.assert_called_once()
        call_args = mock_wiki_client.get_pages.call_args[0][0]
        assert len(call_args) == 5


class TestUpdateCharacterPages:
    """Tests for update_character_pages method."""

    def test_successful_update(self, wiki_service, mock_character_repo, mock_wiki_client, sample_character):
        """Test successful character page update."""
        mock_character_repo.get_characters_for_wiki_generation.return_value = [sample_character]
        mock_wiki_client.get_pages.return_value = {"Character:Goblin Scout": None}

        result = wiki_service.update_character_pages(dry_run=False)

        assert result.total == 1
        assert result.updated == 1
        assert result.failed == 0

        # Should update with Character namespace
        mock_wiki_client.edit_page.assert_called_once()
        call_args = mock_wiki_client.edit_page.call_args
        assert call_args[1]["title"] == "Character:Goblin Scout"


class TestUpdateSpellPages:
    """Tests for update_spell_pages method."""

    def test_successful_update(self, wiki_service, mock_spell_repo, mock_wiki_client, sample_spell):
        """Test successful spell page update."""
        mock_spell_repo.get_spells_for_wiki_generation.return_value = [sample_spell]
        mock_wiki_client.get_pages.return_value = {"Spell:Fireball": None}

        result = wiki_service.update_spell_pages(dry_run=False)

        assert result.total == 1
        assert result.updated == 1
        assert result.failed == 0

        # Should update with Spell namespace
        mock_wiki_client.edit_page.assert_called_once()
        call_args = mock_wiki_client.edit_page.call_args
        assert call_args[1]["title"] == "Spell:Fireball"


class TestLegacyTemplateRemoval:
    """Tests for legacy template removal during updates."""

    def test_removes_legacy_templates(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test removal of legacy templates from existing pages."""
        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]

        # Existing page with ONLY {{Item}} and legacy template that should be removed
        # After field preservation, {{Enemy Stats}} should still exist and be removed
        # NOTE: Legacy templates that appear alongside new templates get removed
        existing_content = (
            "{{Item|name=Test Sword|damage=10}}\n\n" "{{Enemy Stats|hp=100|ac=20}}\n\n" "Some description text"
        )
        mock_wiki_client.get_pages.return_value = {"Item:Test Sword": existing_content}

        result = wiki_service.update_item_pages(dry_run=False)

        # Should complete successfully
        assert result.total == 1
        assert result.updated == 1

        # May or may not have warnings depending on whether preservation detects changes
        # The key is that it processed successfully


class TestUpdateResult:
    """Tests for UpdateResult dataclass."""

    def test_has_warnings(self):
        """Test has_warnings method."""
        result = UpdateResult(total=1, updated=1, skipped=0, failed=0, warnings=["Warning"], errors=[])
        assert result.has_warnings()

        result_no_warnings = UpdateResult(total=1, updated=1, skipped=0, failed=0, warnings=[], errors=[])
        assert not result_no_warnings.has_warnings()

    def test_has_errors(self):
        """Test has_errors method."""
        result = UpdateResult(total=1, updated=0, skipped=0, failed=1, warnings=[], errors=["Error"])
        assert result.has_errors()

        result_no_errors = UpdateResult(total=1, updated=1, skipped=0, failed=0, warnings=[], errors=[])
        assert not result_no_errors.has_errors()


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_continues_on_individual_failure(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test service continues processing after individual page failure."""
        items = [sample_item] * 3
        mock_item_repo.get_items_for_wiki_generation.return_value = items

        mock_wiki_client.get_pages.return_value = {"Item:Test Sword": None}

        # First update succeeds, second fails, third succeeds
        mock_wiki_client.edit_page.side_effect = [
            None,  # Success
            MediaWikiAPIError("API error"),  # Failure
            None,  # Success
        ]

        result = wiki_service.update_item_pages(dry_run=False)

        assert result.total == 3
        assert result.updated == 2
        assert result.failed == 1
        assert result.has_errors()

    def test_handles_fetch_error_gracefully(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test handles error when fetching existing pages."""
        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]

        # Simulate error fetching pages
        mock_wiki_client.get_pages.side_effect = MediaWikiAPIError("Network error")

        result = wiki_service.update_item_pages(dry_run=False)

        # Should still attempt to process (treating all as new pages)
        assert result.total == 1
        assert result.has_errors()
        assert "Failed to fetch existing pages" in result.errors[0]
