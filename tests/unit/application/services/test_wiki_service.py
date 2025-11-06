"""Unit tests for WikiService.

Tests the wiki service orchestration including:
- Initialization with dependencies
- Delegation to specialized services
- Three-stage workflow (fetch, generate, deploy)
- OperationResult handling
"""

from unittest.mock import Mock

import pytest

from erenshor.application.services.wiki_page import OperationResult
from erenshor.application.services.wiki_service import WikiService
from erenshor.domain.entities.item import Item


@pytest.fixture
def mock_wiki_client():
    """Mock MediaWiki client."""
    client = Mock()
    client.get_pages.return_value = {}
    client.edit_page.return_value = None
    client.get_recent_changes.return_value = {}
    return client


@pytest.fixture
def mock_item_repo():
    """Mock item repository."""
    repo = Mock()
    repo.get_items_for_wiki_generation.return_value = []
    repo.get_item_stats.return_value = []
    repo.get_item_classes.return_value = []
    # Source enrichment methods
    repo.get_items_producing_item.return_value = []
    repo.get_items_requiring_item.return_value = []
    repo.get_crafting_recipe.return_value = None
    return repo


@pytest.fixture
def mock_character_repo():
    """Mock character repository."""
    repo = Mock()
    repo.get_characters_for_wiki_generation.return_value = []
    # Source enrichment methods
    repo.get_vendors_selling_item.return_value = []
    repo.get_characters_dropping_item.return_value = []
    return repo


@pytest.fixture
def mock_spell_repo():
    """Mock spell repository."""
    repo = Mock()
    repo.get_spells_for_wiki_generation.return_value = []
    return repo


@pytest.fixture
def mock_skill_repo():
    """Mock skill repository."""
    repo = Mock()
    repo.get_skills_for_wiki_generation.return_value = []
    return repo


@pytest.fixture
def mock_storage(tmp_path):
    """Mock wiki storage."""
    from erenshor.application.services.wiki_storage import WikiStorage

    return WikiStorage(tmp_path / "wiki")


@pytest.fixture
def mock_registry_resolver():
    """Mock registry resolver."""
    resolver = Mock()
    # Default behavior: return entity name as page title
    resolver.resolve_page_title.side_effect = lambda key, name: name
    return resolver


@pytest.fixture
def mock_faction_repo():
    """Mock faction repository."""
    repo = Mock()
    repo.get_faction_modifiers_for_character.return_value = []
    return repo


@pytest.fixture
def mock_spawn_repo():
    """Mock spawn point repository."""
    repo = Mock()
    repo.get_spawns_for_character.return_value = []
    return repo


@pytest.fixture
def mock_loot_repo():
    """Mock loot table repository."""
    repo = Mock()
    repo.get_loot_for_character.return_value = []
    return repo


@pytest.fixture
def wiki_service(
    mock_wiki_client,
    mock_storage,
    mock_item_repo,
    mock_character_repo,
    mock_spell_repo,
    mock_skill_repo,
    mock_faction_repo,
    mock_spawn_repo,
    mock_loot_repo,
    mock_registry_resolver,
):
    """WikiService instance with mocked dependencies."""
    from unittest.mock import Mock

    mock_quest_repo = Mock()
    mock_quest_repo.get_quests_rewarding_item.return_value = []
    mock_quest_repo.get_quests_requiring_item.return_value = []

    return WikiService(
        wiki_client=mock_wiki_client,
        storage=mock_storage,
        item_repo=mock_item_repo,
        character_repo=mock_character_repo,
        spell_repo=mock_spell_repo,
        skill_repo=mock_skill_repo,
        faction_repo=mock_faction_repo,
        spawn_repo=mock_spawn_repo,
        loot_repo=mock_loot_repo,
        quest_repo=mock_quest_repo,
        registry_resolver=mock_registry_resolver,
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
        required_slot="Primary",
        this_weapon_type="Sword",
        item_level=10,
        weapon_dly=2.5,
        is_quest_item=0,
        sell_price=100,
        rarity="Common",
        hp=None,
        mana=None,
        ac=None,
        str=None,
        dex=None,
        end=None,
        agi=None,
        wis=None,
        int=None,
        cha=None,
        mr=None,
        er=None,
        vr=None,
        pr=None,
        damage=10,
        damage_variance=2,
        attack_roll_bonus=0,
        crit_roll_bonus=0,
        worn_effect=None,
        equipped_effect_intensity=None,
    )


class TestWikiServiceInit:
    """Tests for WikiService initialization."""

    def test_init_with_dependencies(
        self,
        mock_wiki_client,
        mock_storage,
        mock_item_repo,
        mock_character_repo,
        mock_spell_repo,
        mock_skill_repo,
        mock_faction_repo,
        mock_spawn_repo,
        mock_loot_repo,
        mock_registry_resolver,
    ):
        """Test service initializes with all dependencies."""
        from unittest.mock import Mock

        mock_quest_repo = Mock()

        service = WikiService(
            wiki_client=mock_wiki_client,
            storage=mock_storage,
            item_repo=mock_item_repo,
            character_repo=mock_character_repo,
            spell_repo=mock_spell_repo,
            skill_repo=mock_skill_repo,
            faction_repo=mock_faction_repo,
            spawn_repo=mock_spawn_repo,
            loot_repo=mock_loot_repo,
            quest_repo=mock_quest_repo,
            registry_resolver=mock_registry_resolver,
        )

        # WikiService now delegates to specialized services
        assert service._fetch_service is not None
        assert service._generate_service is not None
        assert service._deploy_service is not None


class TestFetchAll:
    """Tests for fetch_all method."""

    def test_empty_repositories(self, wiki_service):
        """Test handling of empty repositories."""
        result = wiki_service.fetch_all(dry_run=True)

        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0
        assert "No pages to fetch" in result.warnings[0]

    def test_dry_run_mode(self, wiki_service, mock_item_repo, mock_wiki_client, sample_item):
        """Test dry-run mode doesn't call wiki API."""
        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]

        result = wiki_service.fetch_all(dry_run=True)

        # Should not fetch pages in dry-run
        mock_wiki_client.get_pages.assert_not_called()
        assert result.succeeded == 1

    def test_limit_parameter(self, wiki_service, mock_item_repo, sample_item):
        """Test limit parameter restricts processing."""
        # Create items with different names to get different pages
        items = []
        for i in range(10):
            item = Item(
                item_db_index=i,
                id=f"item-{i}",
                item_name=f"Test Sword {i}",  # Different names = different pages
                resource_name=f"TestSword{i}",
                lore="A test sword",
                required_slot="Primary",
                this_weapon_type="Sword",
                item_level=10,
                weapon_dly=2.5,
                is_quest_item=0,
                sell_price=100,
                rarity="Common",
                hp=None,
                mana=None,
                ac=None,
                str=None,
                dex=None,
                end=None,
                agi=None,
                wis=None,
                int=None,
                cha=None,
                mr=None,
                er=None,
                vr=None,
                pr=None,
                damage=10,
                damage_variance=2,
                attack_roll_bonus=0,
                crit_roll_bonus=0,
                worn_effect=None,
                equipped_effect_intensity=None,
            )
            items.append(item)
        mock_item_repo.get_items_for_wiki_generation.return_value = items

        result = wiki_service.fetch_all(dry_run=True, limit=3)

        assert result.total == 3


class TestGenerateAll:
    """Tests for generate_all method."""

    def test_empty_repositories(self, wiki_service):
        """Test handling of empty repositories."""
        result = wiki_service.generate_all(dry_run=True)

        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0
        assert "No pages to generate" in result.warnings[0]

    def test_dry_run_mode(self, wiki_service, mock_item_repo, sample_item):
        """Test dry-run mode doesn't save to storage."""
        from erenshor.domain.entities.item_stats import ItemStats

        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]
        mock_item_repo.get_item_stats.return_value = [
            ItemStats(
                item_resource_name="TestSword",
                quality="Normal",
                weapon_dmg=10,
                hp=0,
                ac=0,
                mana=0,
                strength=0,
                dexterity=0,
                endurance=0,
                agility=0,
                wisdom=0,
                intelligence=0,
                charisma=0,
                magic_resist=0,
                elemental_resist=0,
                void_resist=0,
                poison_resist=0,
                damage=10,
                damage_variance=2,
                attack_roll_bonus=0,
                crit_roll_bonus=0,
                worn_effect=None,
                equipped_effect_intensity=None,
            ),
        ]
        mock_item_repo.get_item_classes.return_value = ["Warrior", "Paladin"]

        result = wiki_service.generate_all(dry_run=True)

        assert result.total == 1
        assert result.succeeded == 1
        assert result.failed == 0

    def test_limit_parameter(self, wiki_service, mock_item_repo, sample_item):
        """Test limit parameter restricts processing."""
        # Create items with different names to get different pages
        items = []
        for i in range(10):
            item = Item(
                item_db_index=i,
                id=f"item-{i}",
                item_name=f"Test Sword {i}",  # Different names = different pages
                resource_name=f"TestSword{i}",
                lore="A test sword",
                required_slot="Primary",
                this_weapon_type="Sword",
                item_level=10,
                weapon_dly=2.5,
                is_quest_item=0,
                sell_price=100,
                rarity="Common",
                hp=None,
                mana=None,
                ac=None,
                str=None,
                dex=None,
                end=None,
                agi=None,
                wis=None,
                int=None,
                cha=None,
                mr=None,
                er=None,
                vr=None,
                pr=None,
                damage=10,
                damage_variance=2,
                attack_roll_bonus=0,
                crit_roll_bonus=0,
                worn_effect=None,
                equipped_effect_intensity=None,
            )
            items.append(item)
        mock_item_repo.get_items_for_wiki_generation.return_value = items

        result = wiki_service.generate_all(dry_run=True, limit=3)

        assert result.total == 3

    def test_page_titles_filter(self, wiki_service, mock_item_repo, sample_item):
        """Test page_titles parameter filters pages."""
        from erenshor.domain.entities.item_stats import ItemStats

        mock_item_repo.get_items_for_wiki_generation.return_value = [sample_item]
        mock_item_repo.get_item_stats.return_value = [
            ItemStats(
                item_resource_name="TestSword",
                quality="Normal",
                weapon_dmg=10,
                hp=0,
                ac=0,
                mana=0,
                strength=0,
                dexterity=0,
                endurance=0,
                agility=0,
                wisdom=0,
                intelligence=0,
                charisma=0,
                magic_resist=0,
                elemental_resist=0,
                void_resist=0,
                poison_resist=0,
                damage=10,
                damage_variance=2,
                attack_roll_bonus=0,
                crit_roll_bonus=0,
                worn_effect=None,
                equipped_effect_intensity=None,
            ),
        ]
        mock_item_repo.get_item_classes.return_value = ["Warrior", "Paladin"]

        result = wiki_service.generate_all(dry_run=True, page_titles=["Test Sword"])

        assert result.total == 1
        assert result.succeeded == 1


class TestDeployAll:
    """Tests for deploy_all method."""

    def test_no_generated_pages(self, wiki_service):
        """Test handling when no pages have been generated."""
        result = wiki_service.deploy_all(dry_run=True)

        assert result.total == 0
        assert "No generated pages found" in result.warnings[0]

    def test_dry_run_mode(self, wiki_service, mock_storage, mock_wiki_client):
        """Test dry-run mode doesn't call wiki API."""
        # Create a generated page in storage
        mock_storage.save_generated_by_title(
            "Test Page",
            ["item:test"],
            "{{Item|title=Test}}",
        )

        result = wiki_service.deploy_all(dry_run=True)

        # Should not edit pages in dry-run
        mock_wiki_client.edit_page.assert_not_called()
        assert result.succeeded == 1


class TestLegacyTemplateMigration:
    """Tests for legacy template migration during page generation."""

    def test_legacy_character_template_migration_no_duplicates(
        self, wiki_service, mock_storage, mock_character_repo, mock_faction_repo, mock_spawn_repo, mock_loot_repo
    ):
        """Test that {{Character}} → {{Enemy}} migration happens before field preservation.

        This prevents duplicate templates when:
        1. Fetched content has {{Character|...}}
        2. Generated content has {{Enemy|...}}
        3. Legacy migration should happen FIRST, converting Character → Enemy
        4. Then field preservation merges the two Enemy templates
        5. Result: Single Enemy template with preserved fields
        """
        from erenshor.domain.entities.character import Character

        # Create a test character
        character = Character(
            id=1,
            guid="test-guid",
            npc_name="Test Character",
            resource_name="test_character",
            object_name="Test_Character",  # Required for stable_key
            is_prefab=0,
            level=10,
            base_hp=1000,
            base_mana=100,
            base_ac=50,
            base_str=10,
            base_end=10,
            base_dex=10,
            base_agi=10,
            base_int=10,
            base_wis=10,
            base_cha=10,
            is_friendly=1,
            my_faction="GoodHuman",
        )
        mock_character_repo.get_characters_for_wiki_generation.return_value = [character]

        # Mock enrichment repositories to return empty data
        mock_faction_repo.get_faction_display_names.return_value = {}
        mock_spawn_repo.get_spawn_info_for_character.return_value = []
        mock_loot_repo.get_loot_drops_for_character.return_value = []

        # Simulate fetched content with legacy {{Character}} template
        fetched_content = """{{Character
|name=Test Character
|level=5
|health=500
}}

Manual content that should be preserved."""

        # Save fetched content to storage
        mock_storage.save_fetched_by_title(
            "Test Character",
            ["character:test_character"],
            fetched_content,
            ["Test Character"],
        )

        # Generate page (should migrate Character → Enemy, then preserve fields)
        result = wiki_service.generate_all(dry_run=False, page_titles=["Test Character"])

        # Verify generation succeeded
        assert result.succeeded == 1
        assert result.total == 1

        # Read generated content
        generated_content = mock_storage.read_generated_by_title("Test Character")
        assert generated_content is not None

        # Verify NO duplicate Enemy templates (should only have one)
        enemy_count = generated_content.count("{{Enemy")
        assert enemy_count == 1, f"Expected 1 Enemy template, found {enemy_count}"

        # Verify NO Character templates remain
        assert "{{Character" not in generated_content

        # Verify modern field names (not legacy field names)
        assert "|guaranteeddrops=" in generated_content or "|droprates=" in generated_content
        assert "|commondrops=" not in generated_content
        assert "|uncommondrops=" not in generated_content

        # Verify manual content preserved
        assert "Manual content that should be preserved" in generated_content


class TestOperationResult:
    """Tests for OperationResult dataclass."""

    def test_has_warnings(self):
        """Test has_warnings method."""
        result = OperationResult(total=1, succeeded=1, skipped=0, failed=0, warnings=["Warning"], errors=[])
        assert result.has_warnings()

        result_no_warnings = OperationResult(total=1, succeeded=1, skipped=0, failed=0, warnings=[], errors=[])
        assert not result_no_warnings.has_warnings()

    def test_has_errors(self):
        """Test has_errors method."""
        result = OperationResult(total=1, succeeded=0, skipped=0, failed=1, warnings=[], errors=["Error"])
        assert result.has_errors()

        result_no_errors = OperationResult(total=1, succeeded=1, skipped=0, failed=0, warnings=[], errors=[])
        assert not result_no_errors.has_errors()
