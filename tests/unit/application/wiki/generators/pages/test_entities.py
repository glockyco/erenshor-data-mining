"""Unit tests for EntityPageGenerator.

Tests the unified entity page generator that handles all entity types
and correctly manages multi-entity pages.
"""

from unittest.mock import Mock

import pytest

from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.generators.pages.entities import EntityPageGenerator
from erenshor.domain.entities import Character, Item, Skill, Spell


@pytest.fixture
def mock_context():
    """Create mock GeneratorContext with all dependencies."""
    context = Mock(spec=GeneratorContext)

    # Mock repositories
    context.item_repo = Mock()
    context.character_repo = Mock()
    context.spell_repo = Mock()
    context.skill_repo = Mock()
    context.stance_repo = Mock()
    context.stance_repo.get_all.return_value = []
    context.faction_repo = Mock()
    context.spawn_repo = Mock()
    context.loot_repo = Mock()
    context.quest_repo = Mock()

    # Mock resolver
    context.resolver = Mock()

    # Mock storage
    context.storage = Mock()

    # Mock class display service (identity mapping)
    class_display = Mock()
    class_display.get_display_name.side_effect = lambda name: name
    class_display.map_class_list.side_effect = lambda names: sorted(names)
    class_display.get_all_display_names.return_value = [
        "Arcanist",
        "Druid",
        "Duelist",
        "Paladin",
        "Stormcaller",
    ]
    class_display.get_all_internal_names.return_value = [
        "Arcanist",
        "Druid",
        "Duelist",
        "Paladin",
        "Stormcaller",
    ]
    context.class_display = class_display

    return context


@pytest.fixture
def mock_item():
    """Create mock Item entity."""
    item = Mock(spec=Item)
    item.stable_key = "item:test_sword"
    item.item_name = "Test Sword"
    return item


@pytest.fixture
def mock_character():
    """Create mock Character entity."""
    character = Mock(spec=Character)
    character.stable_key = "character:goblin"
    character.npc_name = "Goblin Scout"
    return character


@pytest.fixture
def mock_spell():
    """Create mock Spell entity."""
    spell = Mock(spec=Spell)
    spell.stable_key = "spell:fireball_i"
    spell.spell_name = "Fireball I"
    return spell


@pytest.fixture
def mock_skill():
    """Create mock Skill entity."""
    skill = Mock(spec=Skill)
    skill.stable_key = "skill:shield_bash"
    skill.skill_name = "Shield Bash"
    return skill


class TestEntityPageGeneratorInit:
    """Test EntityPageGenerator initialization."""

    def test_init_creates_enrichers(self, mock_context):
        """Verify all enrichers are initialized."""
        generator = EntityPageGenerator(mock_context)

        assert generator.item_enricher is not None
        assert generator.character_enricher is not None
        assert generator.spell_enricher is not None
        assert generator.skill_enricher is not None

    def test_init_creates_section_generators(self, mock_context):
        """Verify all section generators are initialized."""
        generator = EntityPageGenerator(mock_context)

        assert generator.item_generator is not None
        assert generator.character_generator is not None
        assert generator.spell_generator is not None
        assert generator.skill_generator is not None
        assert generator.category_generator is not None

    def test_init_stores_context(self, mock_context):
        """Verify context is stored."""
        generator = EntityPageGenerator(mock_context)
        assert generator.context is mock_context


class TestGetPagesToFetch:
    """Test get_pages_to_fetch method."""

    def test_returns_unique_page_titles(self, mock_context, mock_item, mock_spell):
        """Verify page titles are deduplicated."""
        # Setup: Two entities with same page title
        mock_context.item_repo.get_items_for_wiki_generation.return_value = [mock_item]
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = [mock_spell]
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = []

        # Both resolve to same page title
        mock_context.resolver.resolve_page_title.return_value = "Shared Page"

        generator = EntityPageGenerator(mock_context)
        pages = generator.get_pages_to_fetch()

        # Should only return one page title
        assert pages == ["Shared Page"]

    def test_fetches_from_all_repositories(self, mock_context):
        """Verify all entity repositories are queried."""
        mock_context.item_repo.get_items_for_wiki_generation.return_value = []
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = []
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = []

        generator = EntityPageGenerator(mock_context)
        generator.get_pages_to_fetch()

        # All repos should be called
        mock_context.item_repo.get_items_for_wiki_generation.assert_called_once()
        mock_context.character_repo.get_characters_for_wiki_generation.assert_called_once()
        mock_context.spell_repo.get_spells_for_wiki_generation.assert_called_once()
        mock_context.skill_repo.get_skills_for_wiki_generation.assert_called_once()

    def test_returns_empty_list_when_no_entities(self, mock_context):
        """Verify empty list when no entities."""
        mock_context.item_repo.get_items_for_wiki_generation.return_value = []
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = []
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = []

        generator = EntityPageGenerator(mock_context)
        pages = generator.get_pages_to_fetch()

        assert pages == []


class TestGeneratePages:
    """Test generate_pages method."""

    def test_generates_single_entity_page(self, mock_context, mock_item):
        """Verify single item generates one page."""
        from erenshor.domain.enriched_data.item import EnrichedItemData

        # Setup
        mock_context.item_repo.get_items_for_wiki_generation.return_value = [mock_item]
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = []
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = []

        mock_context.resolver.resolve_page_title.return_value = "Test Sword"

        generator = EntityPageGenerator(mock_context)

        # Mock enricher to return proper type
        enriched = Mock(spec=EnrichedItemData)
        enriched.item = mock_item
        generator.item_enricher.enrich = Mock(return_value=enriched)
        generator.item_generator.generate_template = Mock(return_value="{{Item}}")
        generator.category_generator.generate_categories = Mock(return_value=["Items"])
        generator.category_generator.format_category_tags = Mock(return_value="[[Category:Items]]")

        # Generate
        pages = list(generator.generate_pages())

        # Verify
        assert len(pages) == 1
        assert pages[0].title == "Test Sword"
        assert "{{Item}}" in pages[0].content
        assert "[[Category:Items]]" in pages[0].content

    def test_groups_entities_by_page_title(self, mock_context, mock_spell, mock_skill):
        """Verify entities with same page title are grouped together."""
        from erenshor.domain.enriched_data.skill import EnrichedSkillData
        from erenshor.domain.enriched_data.spell import EnrichedSpellData

        # Setup: spell and skill with same page title
        mock_context.item_repo.get_items_for_wiki_generation.return_value = []
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = [mock_spell]
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = [mock_skill]

        # Both resolve to same page
        mock_context.resolver.resolve_page_title.return_value = "Aura: Blessing of Stone"

        generator = EntityPageGenerator(mock_context)

        # Mock enrichers to return proper types
        spell_enriched = Mock(spec=EnrichedSpellData)
        skill_enriched = Mock(spec=EnrichedSkillData)
        generator.spell_enricher.enrich = Mock(return_value=spell_enriched)
        generator.skill_enricher.enrich = Mock(return_value=skill_enriched)
        generator.spell_generator.generate_template = Mock(return_value="{{Ability|type=Spell}}")
        generator.skill_generator.generate_template = Mock(return_value="{{Ability|type=Skill}}")
        generator.category_generator.generate_categories = Mock(return_value=["Spells"])
        generator.category_generator.format_category_tags = Mock(return_value="[[Category:Spells]]")

        # Generate
        pages = list(generator.generate_pages())

        # Verify: Only one page with both templates
        assert len(pages) == 1
        assert pages[0].title == "Aura: Blessing of Stone"
        assert "{{Ability|type=Spell}}" in pages[0].content
        assert "{{Ability|type=Skill}}" in pages[0].content

    def test_enriches_entities_before_generation(self, mock_context, mock_item):
        """Verify entities are enriched before template generation."""
        from erenshor.domain.enriched_data.item import EnrichedItemData

        mock_context.item_repo.get_items_for_wiki_generation.return_value = [mock_item]
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = []
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = []

        mock_context.resolver.resolve_page_title.return_value = "Test Item"

        generator = EntityPageGenerator(mock_context)

        # Mock enricher to return proper type
        enriched = Mock(spec=EnrichedItemData)
        enriched.item = mock_item
        generator.item_enricher.enrich = Mock(return_value=enriched)
        generator.item_generator.generate_template = Mock(return_value="{{Item}}")
        generator.category_generator.generate_categories = Mock(return_value=[])
        generator.category_generator.format_category_tags = Mock(return_value="")

        # Generate
        list(generator.generate_pages())

        # Verify enrich was called
        generator.item_enricher.enrich.assert_called_once_with(mock_item)
        # Verify enriched data was passed to generator
        generator.item_generator.generate_template.assert_called_once_with(enriched, "Test Item")

    def test_handles_all_entity_types(self, mock_context, mock_item, mock_character, mock_spell, mock_skill):
        """Verify all entity types are processed correctly."""
        from erenshor.domain.enriched_data.character import EnrichedCharacterData
        from erenshor.domain.enriched_data.item import EnrichedItemData
        from erenshor.domain.enriched_data.skill import EnrichedSkillData
        from erenshor.domain.enriched_data.spell import EnrichedSpellData

        # Setup: One of each entity type, all with different pages
        mock_context.item_repo.get_items_for_wiki_generation.return_value = [mock_item]
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = [mock_character]
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = [mock_spell]
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = [mock_skill]

        # Each resolves to different page
        def resolve_page_title(stable_key):
            return {
                "item:test_sword": "Test Sword",
                "character:goblin": "Goblin Scout",
                "spell:fireball_i": "Fireball I",
                "skill:shield_bash": "Shield Bash",
            }[stable_key]

        mock_context.resolver.resolve_page_title.side_effect = resolve_page_title

        generator = EntityPageGenerator(mock_context)

        # Mock all enrichers to return proper types
        enriched_item = Mock(spec=EnrichedItemData)
        enriched_char = Mock(spec=EnrichedCharacterData)
        enriched_spell = Mock(spec=EnrichedSpellData)
        enriched_skill = Mock(spec=EnrichedSkillData)

        generator.item_enricher.enrich = Mock(return_value=enriched_item)
        generator.character_enricher.enrich = Mock(return_value=enriched_char)
        generator.spell_enricher.enrich = Mock(return_value=enriched_spell)
        generator.skill_enricher.enrich = Mock(return_value=enriched_skill)

        generator.item_generator.generate_template = Mock(return_value="{{Item}}")
        generator.character_generator.generate_template = Mock(return_value="{{Character}}")
        generator.spell_generator.generate_template = Mock(return_value="{{Spell}}")
        generator.skill_generator.generate_template = Mock(return_value="{{Skill}}")

        generator.category_generator.generate_categories = Mock(return_value=[])
        generator.category_generator.format_category_tags = Mock(return_value="")

        # Generate
        pages = list(generator.generate_pages())

        # Verify 4 pages created
        assert len(pages) == 4
        page_titles = {p.title for p in pages}
        assert page_titles == {"Test Sword", "Goblin Scout", "Fireball I", "Shield Bash"}

    def test_page_metadata(self, mock_context, mock_item):
        """Verify generated pages have correct metadata."""
        from erenshor.domain.enriched_data.item import EnrichedItemData

        mock_context.item_repo.get_items_for_wiki_generation.return_value = [mock_item]
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = []
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = []

        mock_context.resolver.resolve_page_title.return_value = "Test Item"

        generator = EntityPageGenerator(mock_context)

        # Mock enricher to return proper type
        enriched = Mock(spec=EnrichedItemData)
        enriched.item = mock_item
        generator.item_enricher.enrich = Mock(return_value=enriched)
        generator.item_generator.generate_template = Mock(return_value="{{Item}}")
        generator.category_generator.generate_categories = Mock(return_value=[])
        generator.category_generator.format_category_tags = Mock(return_value="")

        # Generate
        pages = list(generator.generate_pages())

        # Verify metadata
        assert pages[0].metadata.summary == "Update entity data from game export"
        assert pages[0].metadata.minor is False

    def test_stable_keys_single_entity(self, mock_context, mock_item):
        """Verify stable_keys are populated for single entity page."""
        from erenshor.domain.enriched_data.item import EnrichedItemData

        mock_context.item_repo.get_items_for_wiki_generation.return_value = [mock_item]
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = []
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = []

        mock_context.resolver.resolve_page_title.return_value = "Test Sword"

        generator = EntityPageGenerator(mock_context)

        enriched = Mock(spec=EnrichedItemData)
        enriched.item = mock_item
        generator.item_enricher.enrich = Mock(return_value=enriched)
        generator.item_generator.generate_template = Mock(return_value="{{Item}}")
        generator.category_generator.generate_categories = Mock(return_value=[])
        generator.category_generator.format_category_tags = Mock(return_value="")

        pages = list(generator.generate_pages())

        assert pages[0].stable_keys == ["item:test_sword"]

    def test_stable_keys_multi_entity_page(self, mock_context, mock_spell, mock_skill):
        """Verify stable_keys contains all entities for multi-entity page."""
        from erenshor.domain.enriched_data.skill import EnrichedSkillData
        from erenshor.domain.enriched_data.spell import EnrichedSpellData

        mock_context.item_repo.get_items_for_wiki_generation.return_value = []
        mock_context.character_repo.get_characters_for_wiki_generation.return_value = []
        mock_context.spell_repo.get_spells_for_wiki_generation.return_value = [mock_spell]
        mock_context.skill_repo.get_skills_for_wiki_generation.return_value = [mock_skill]

        mock_context.resolver.resolve_page_title.return_value = "Aura: Blessing of Stone"

        generator = EntityPageGenerator(mock_context)

        spell_enriched = Mock(spec=EnrichedSpellData)
        skill_enriched = Mock(spec=EnrichedSkillData)
        generator.spell_enricher.enrich = Mock(return_value=spell_enriched)
        generator.skill_enricher.enrich = Mock(return_value=skill_enriched)
        generator.spell_generator.generate_template = Mock(return_value="{{Ability|type=Spell}}")
        generator.skill_generator.generate_template = Mock(return_value="{{Ability|type=Skill}}")
        generator.category_generator.generate_categories = Mock(return_value=[])
        generator.category_generator.format_category_tags = Mock(return_value="")

        pages = list(generator.generate_pages())

        assert len(pages[0].stable_keys) == 2
        assert "spell:fireball_i" in pages[0].stable_keys
        assert "skill:shield_bash" in pages[0].stable_keys
