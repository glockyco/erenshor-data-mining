"""Unit tests for ItemSectionGenerator.

Tests item page generation for different item types including weapons, armor,
consumables, and general items.
"""

from unittest.mock import MagicMock

import pytest

from erenshor.application.wiki.generators.sections.categories import CategoryGenerator
from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator
from erenshor.domain.enriched_data.item import EnrichedItemData
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.registry.item_classifier import ItemKind


@pytest.fixture
def enrich_item():
    """Helper to wrap items in EnrichedItemData."""

    def _enrich(
        item: Item,
        stats: list[ItemStats] | None = None,
        classes: list[str] | None = None,
    ) -> EnrichedItemData:
        return EnrichedItemData(item=item, stats=stats or [], classes=classes or [])

    return _enrich


@pytest.fixture
def mock_resolver():
    """Create mock registry resolver."""
    resolver = MagicMock()

    # Make resolver return the item name based on stable_key
    def resolve_display_name(stable_key: str) -> str:
        # Extract name from stable_key (format: "item:name")
        if ":" in stable_key:
            name = stable_key.split(":", 1)[1]
            # Convert underscores to spaces and capitalize each word
            # Handle camelCase by inserting spaces before capitals
            import re

            # Insert space before uppercase letters (for camelCase)
            spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
            # Replace underscores with spaces
            spaced = spaced.replace("_", " ")
            # Capitalize each word
            return " ".join(word.capitalize() for word in spaced.split())
        return "Test Item"

    def resolve_image_name(stable_key: str) -> str:
        # For image names, just capitalize without spaces (like the resource name)
        if ":" in stable_key:
            name = stable_key.split(":", 1)[1]
            return name.capitalize()
        return "Testitem"

    resolver.resolve_display_name.side_effect = resolve_display_name
    resolver.resolve_image_name.side_effect = resolve_image_name
    resolver.ability_link.return_value = "{{AbilityLink|Test Ability}}"
    resolver.item_link.return_value = "{{ItemLink|Test Item}}"
    return resolver


@pytest.fixture
def category_generator(mock_resolver):
    """Create category generator with mock resolver."""
    return CategoryGenerator(mock_resolver)


@pytest.fixture
def generator(mock_resolver, mock_class_display):
    """Create item template generator."""
    return ItemSectionGenerator(mock_resolver, mock_class_display)


class TestItemSectionGenerator:
    """Test suite for ItemSectionGenerator."""

    def test_generate_page_for_general_item(self, generator, enrich_item):
        """Test generating page for general item."""
        item = Item(
            id="1",
            resource_name="TestItem",
            stable_key="item:test item",
            item_name="Test Item",
            lore="A test item",
            required_slot="General",
            item_value=100,
            sell_value=25,
        )
        enriched = enrich_item(item)

        result = generator.generate_template(enriched, "Test Item")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Test Item" in result
        assert "|description=A test item" in result
        assert "|buy=100" in result
        assert "|sell=25" in result

    def test_generate_page_for_weapon(self, generator, enrich_item):
        """Test generating page for weapon with fancy templates."""
        from erenshor.domain.entities.item_stats import ItemStats

        item = Item(
            id="2",
            resource_name="TestSword",
            stable_key="item:test sword",
            item_name="Test Sword",
            lore="A sharp blade",
            required_slot="Primary",
            weapon_dly=2.0,
            classes="Duelist, Paladin",
            item_value=500,
            sell_value=125,
        )
        # Weapons require stats
        stats = [
            ItemStats(
                item_stable_key="TestSword",
                quality="Normal",
                weapon_dmg=10,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            )
        ]
        enriched = enrich_item(item, stats)

        result = generator.generate_template(enriched, "Test Sword")

        # Should contain {{Item}} template with SOURCE FIELDS ONLY (no stats/classes/delay)
        assert "{{Item" in result
        assert "|title=Test Sword" in result
        assert "|buy=500" in result
        assert "|sell=125" in result
        # Verify {{Item}} section does NOT have stat/class/description fields (removed to avoid duplication)
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        # These fields are NOT in {{Item}} anymore - they only appear in tooltips
        assert "|delay=" not in item_section
        assert "|classes=" not in item_section
        assert "|description=" not in item_section
        assert "|relic=" not in item_section

        # Should contain {{Item/Weapon}} template
        assert "{{Item/Weapon" in result

    def test_weapon_with_damage_shows_value(self, generator, enrich_item):
        """Test weapons with damage show actual damage values."""
        from erenshor.domain.entities.item_stats import ItemStats

        item = Item(
            id="100",
            resource_name="HAND - 1 - Copper Sword",
            stable_key="item:hand - 1 - copper sword",
            item_name="Copper Sword",
            required_slot="Primary",
            weapon_dly=1.2,
            item_value=100,
            sell_value=25,
        )

        stats = [
            ItemStats(
                item_stable_key="Copper Sword",
                quality="Normal",
                weapon_dmg=10,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
            ItemStats(
                item_stable_key="Copper Sword",
                quality="Blessed",
                weapon_dmg=11,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
            ItemStats(
                item_stable_key="Copper Sword",
                quality="Godly",
                weapon_dmg=12,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
        ]
        enriched = enrich_item(item, stats)

        result = generator.generate_template(enriched, "Copper Sword")

        # Should show actual damage values in fancy templates
        assert "|damage=10" in result
        assert "|damage=11" in result
        assert "|damage=12" in result
        assert "|delay=1.2" in result

    def test_shield_with_zero_damage_shows_empty(self, generator, enrich_item):
        """Test shields (damage=0) show empty damage/delay fields, not zero."""
        from erenshor.domain.entities.item_stats import ItemStats

        item = Item(
            id="101",
            resource_name="SECONDARY - 1 - Old Buckler",
            stable_key="item:secondary - 1 - old buckler",
            item_name="Old Buckler",
            required_slot="Secondary",
            shield=1,
            weapon_dly=None,
            item_value=27,
            sell_value=18,
        )

        stats = [
            ItemStats(
                item_stable_key="Old Buckler",
                quality="Normal",
                weapon_dmg=0,  # Shields have 0 damage
                hp=0,
                ac=5,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
            ItemStats(
                item_stable_key="Old Buckler",
                quality="Blessed",
                weapon_dmg=0,
                hp=0,
                ac=6,
                mana=0,
                res=1,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
            ItemStats(
                item_stable_key="Old Buckler",
                quality="Godly",
                weapon_dmg=0,
                hp=0,
                ac=7,
                mana=0,
                res=2,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
        ]
        enriched = enrich_item(item, stats)

        result = generator.generate_template(enriched, "Old Buckler")

        # Count damage/delay lines
        damage_lines = [line for line in result.split("\n") if line.startswith("|damage=")]
        delay_lines = [line for line in result.split("\n") if line.startswith("|delay=")]

        # All damage/delay lines should be empty (just |field= with nothing after)
        for line in damage_lines:
            assert line == "|damage=", f"Expected empty damage but got: {line}"

        for line in delay_lines:
            assert line == "|delay=", f"Expected empty delay but got: {line}"

    def test_generate_page_for_armor(self, generator, enrich_item):
        """Test generating page for armor with fancy templates."""
        from erenshor.domain.entities.item_stats import ItemStats

        item = Item(
            id="3",
            resource_name="TestHelmet",
            stable_key="item:test helmet",
            item_name="Test Helmet",
            lore="Protective headgear",
            required_slot="Head",
            classes="Arcanist",
            item_value=300,
            sell_value=75,
        )
        # Armor requires stats
        stats = [
            ItemStats(
                item_stable_key="TestHelmet",
                quality="Normal",
                hp=20,
                ac=5,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            )
        ]

        enriched = enrich_item(item, stats)
        result = generator.generate_template(enriched, "Test Helmet")

        # Should contain {{Item}} template with SOURCE FIELDS ONLY (no stats/classes/description)
        assert "{{Item" in result
        assert "|title=Test Helmet" in result
        assert "|buy=300" in result
        assert "|sell=75" in result
        # Verify {{Item}} section does NOT have stat/class/description fields (removed to avoid duplication)
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|description=" not in item_section  # Field removed (in tooltip only)
        assert "|classes=" not in item_section  # Field removed (in tooltip only)
        assert "|relic=" not in item_section  # Field removed (in tooltip only)

        # Should contain {{Item/Armor}} template
        assert "{{Item/Armor" in result

    def test_generate_page_for_charm(self, generator, enrich_item):
        """Test generating page for charm."""

        item = Item(
            id="4",
            resource_name="TestCharm",
            stable_key="item:test charm",
            item_name="Test Charm",
            lore="Magical charm",
            required_slot="Charm",
            classes="Arcanist, Druid",
        )

        enriched = enrich_item(item)
        result = generator.generate_template(enriched, "Test Charm")

        # Should contain {{Item}} template (fancy charm deferred for now)
        assert "{{Item" in result
        assert "|title=Test Charm" in result

    def test_generate_page_for_consumable(self, generator, enrich_item):
        """Test generating page for consumable."""

        item = Item(
            id="5",
            resource_name="TestPotion",
            stable_key="item:test_potion",
            item_name="Test Potion",
            lore="Restores health",
            required_slot="General",
            item_effect_on_click="HealSpell",
            disposable=1,
            stackable=1,
            item_value=50,
            sell_value=10,
        )

        enriched = enrich_item(item)
        result = generator.generate_template(enriched, "Test Potion")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Test Potion" in result

    def test_generate_page_for_mold(self, generator, enrich_item):
        """Test generating page for mold (crafting template)."""

        item = Item(
            id="6",
            resource_name="TestMold",
            stable_key="item:test_mold",
            item_name="Test Mold",
            lore="Crafting template",
            required_slot="General",
            template=1,
            template_ingredient_ids="1,2,3",
            template_reward_ids="7",
        )

        enriched = enrich_item(item)
        result = generator.generate_template(enriched, "Test Mold")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Test Mold" in result

    def test_generate_page_for_ability_book(self, generator, enrich_item):
        """Test generating page for ability book."""

        item = Item(
            id="7",
            resource_name="TestSpellScroll",
            stable_key="item:test_spell_scroll",
            item_name="Spell Scroll: Fireball",
            lore="Teaches Fireball",
            required_slot="General",
            teach_spell_stable_key="spell:fireball",
        )

        enriched = enrich_item(item)
        result = generator.generate_template(enriched, "Spell Scroll: Fireball")

        # Should contain {{Item}} template
        assert "{{Item" in result
        # Title comes from resolve_display_name(stable_key), not item_name
        assert "|title=Test Spell Scroll" in result

    def test_generate_page_handles_none_values(self, generator, enrich_item):
        """Test that generator handles None values gracefully."""

        item = Item(
            id="8",
            resource_name="MinimalItem",
            stable_key="item:minimal_item",
            item_name="Minimal Item",
            # Most fields are None
            required_slot=None,
            lore=None,
            classes=None,
            item_value=None,
            sell_value=None,
        )

        enriched = enrich_item(item)
        result = generator.generate_template(enriched, "Minimal Item")

        # Should generate valid wikitext even with minimal data
        assert "{{Item" in result
        assert "|title=Minimal Item" in result
        # These fields are removed from {{Item}} (they appear in tooltip templates only)
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|description=" not in item_section
        assert "|classes=" not in item_section
        assert "|relic=" not in item_section

    def test_generate_page_handles_relic_flag(self, generator, enrich_item):
        """Test that relic flag appears in tooltip template (not {{Item}} infobox)."""

        # Relic item
        relic_item = Item(
            id="9",
            resource_name="RelicItem",
            stable_key="item:relic_item",
            item_name="Relic Item",
            relic=1,
        )

        enriched = enrich_item(relic_item)
        result = generator.generate_template(enriched, "Relic Item")
        # relic is NOT in {{Item}} infobox anymore - it only appears in tooltip templates
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|relic=" not in item_section

        # Non-relic item
        normal_item = Item(
            id="10",
            resource_name="NormalItem",
            stable_key="item:normalitem",
            item_name="Normal Item",
            relic=0,
        )

        enriched = enrich_item(normal_item)
        result = generator.generate_template(enriched, "Normal Item")
        # relic is NOT in {{Item}} infobox anymore
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|relic=" not in item_section

    def test_classify_weapon_by_required_slot(self, generator, enrich_item):
        """Test weapon classification by RequiredSlot."""

        # Primary slot weapon
        primary = Item(
            id="11",
            resource_name="Primary",
            stable_key="item:primary",
            item_name="Primary",
            required_slot="Primary",
        )
        assert generator._classify(primary) == "weapon"

        # Secondary slot weapon
        secondary = Item(
            id="12",
            resource_name="Secondary",
            stable_key="item:secondary",
            item_name="Secondary",
            required_slot="Secondary",
        )
        assert generator._classify(secondary) == "weapon"

        # Two-hand weapon (via slot name pattern)
        twohanded = Item(
            id="13",
            resource_name="TwoHand",
            stable_key="item:twohand",
            item_name="TwoHand",
            required_slot="PrimaryOrSecondary",
        )
        assert generator._classify(twohanded) == "weapon"

    def test_classify_armor_by_required_slot(self, generator, enrich_item):
        """Test armor classification by RequiredSlot."""

        armor_slots = ["Head", "Shoulders", "Chest", "Hands", "Legs", "Feet", "Waist", "Neck", "Back"]

        for slot in armor_slots:
            item = Item(
                id=f"armor_{slot}",
                resource_name=slot,
                stable_key=f"item:{slot.lower()}",
                item_name=slot,
                required_slot=slot,
            )
            assert generator._classify(item) == "armor", f"Failed for slot: {slot}"

    def test_classify_consumable(self, generator, enrich_item):
        """Test consumable classification."""

        consumable = Item(
            id="14",
            resource_name="Potion",
            stable_key="item:potion",
            item_name="Potion",
            required_slot="General",
            item_effect_on_click_stable_key="HealSpell",
            disposable=1,
        )
        assert generator._classify(consumable) == ItemKind.CONSUMABLE

    def test_classify_mold(self, generator, enrich_item):
        """Test mold classification."""

        mold = Item(
            id="15",
            resource_name="Mold",
            stable_key="item:mold",
            item_name="Mold",
            template=1,
        )
        assert generator._classify(mold) == ItemKind.MOLD

    def test_classify_ability_book(self, generator, enrich_item):
        """Test spell book and skill book classification."""

        spell_scroll = Item(
            id="16",
            resource_name="SpellScroll",
            stable_key="item:spellscroll",
            item_name="Spell Scroll",
            teach_spell_stable_key="Fireball",
        )
        assert generator._classify(spell_scroll) == ItemKind.SPELL_SCROLL

        skill_book = Item(
            id="17",
            resource_name="SkillBook",
            stable_key="item:skillbook",
            item_name="Skill Book",
            teach_skill_stable_key="Mining",
        )
        assert generator._classify(skill_book) == ItemKind.SKILL_BOOK

    def test_classify_aura(self, generator, enrich_item):
        """Test aura classification."""

        aura = Item(
            id="18",
            resource_name="Aura",
            stable_key="item:aura",
            item_name="Aura",
            required_slot="Aura",
        )
        assert generator._classify(aura) == ItemKind.AURA

    def test_build_item_template_context(self, generator, enrich_item):
        """Test building template context from item."""

        item = Item(
            id="19",
            resource_name="TestItem",
            stable_key="item:test_item",
            item_name="Test Item",
            lore="Test description",
            item_value=100,
            sell_value=25,
            relic=1,
        )

        enriched = enrich_item(item, classes=["Arcanist", "Duelist"])
        context = generator._build_item_infobox_context(enriched, page_title="Test Item")

        # {{Item}} infobox only has source fields - no description, classes, or relic
        assert context["title"] == "Test Item"
        assert context["buy"] == "100"
        assert context["sell"] == "25"
        # These fields are NOT in the infobox context anymore
        assert "description" not in context
        assert "classes" not in context
        assert "relic" not in context

    def test_long_name_font_adjustment(self, generator, enrich_item):
        """Test that general items don't apply font adjustment (only fancy templates do)."""

        # Short name - no font adjustment
        short_item = Item(
            id="20",
            resource_name="ShortItem",
            stable_key="item:short_name",
            item_name="Short Name",
            required_slot="General",
        )
        enriched = enrich_item(short_item)
        short_result = generator.generate_template(enriched, "Short Name")
        assert "|title=Short Name" in short_result
        assert '<span style="font-size:' not in short_result

        # Long name (>24 chars) - general items don't apply font adjustment
        # Font adjustment is only applied in fancy templates (weapons/armor/charms)
        long_item = Item(
            id="21",
            resource_name="LongItem",
            stable_key="item:this_is_a_very_long_item_name_that_exceeds_24_characters",
            item_name="This is a very long item name that exceeds 24 characters",
            required_slot="General",
        )
        enriched = enrich_item(long_item)
        long_result = generator.generate_template(enriched, "This Is A Very Long Item Name That Exceeds 24 Characters")
        # General items use plain title, no font adjustment
        assert "|title=This Is A Very Long Item Name That Exceeds 24 Characters" in long_result
        assert '<span style="font-size:' not in long_result

    def test_item_type_display_consumable(self, generator, enrich_item):
        """Test item type display for consumables."""

        consumable = Item(
            id="22",
            resource_name="Potion",
            stable_key="item:potion",
            item_name="Health Potion",
            required_slot="General",
            item_effect_on_click_stable_key="Heal",
            disposable=1,
        )

        enriched = enrich_item(consumable)
        result = generator.generate_template(enriched, "Health Potion")
        assert "[[Consumables|Consumable]]" in result

    def test_item_type_display_quest_item(self, generator, enrich_item):
        """Test item type display for quest items."""

        quest_item = Item(
            id="23",
            resource_name="QuestLetter",
            stable_key="item:questletter",
            item_name="Quest Letter",
            required_slot="General",
            complete_on_read_stable_key="SomeQuest",
        )

        enriched = enrich_item(quest_item)
        result = generator.generate_template(enriched, "Quest Letter")
        assert "[[Quest Items|Quest Item]]" in result

    def test_complete_on_read_support(self, generator, enrich_item):
        """Test CompleteOnRead field marks item as quest item."""

        # Item with CompleteOnRead should be marked as quest item
        quest_completion_item = Item(
            id="25",
            resource_name="QuestNote",
            stable_key="item:questnote",
            item_name="Quest Note",
            required_slot="General",
            complete_on_read_stable_key="CompleteQuest_123",
        )

        enriched = enrich_item(quest_completion_item)
        result = generator.generate_template(enriched, "Quest Note")
        # Should have Quest Item type
        assert "[[Quest Items|Quest Item]]" in result

        # Item without CompleteOnRead should not be marked as quest item (unless has other quest markers)
        normal_item = Item(
            id="26",
            resource_name="NormalNote",
            stable_key="item:normalnote",
            item_name="Normal Note",
            required_slot="General",
            complete_on_read_stable_key=None,
        )

        enriched = enrich_item(normal_item)
        result = generator.generate_template(enriched, "Normal Note")
        # Should not have Quest Item type
        assert "[[Quest Items|Quest Item]]" not in result


class TestFancyTemplateGeneration:
    """Test fancy template generation for weapons and armor."""

    def test_weapon_with_stats_generates_fancy_weapon_templates(self, generator, enrich_item):
        """Test weapon with stats generates {{Item}} + {{Item/Weapon}} templates."""

        weapon = Item(
            id="100",
            resource_name="TestSword",
            stable_key="item:test sword",
            item_name="Test Sword",
            lore="A sharp blade",
            required_slot="Primary",
            weapon_dly=2.0,
            classes="Duelist, Paladin",
        )

        stats = [
            ItemStats(
                item_stable_key="TestSword",
                quality="Normal",
                weapon_dmg=10,
                hp=0,
                ac=0,
                mana=0,
                strength=5,
                endurance=None,
                dexterity=3,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
            ItemStats(
                item_stable_key="TestSword",
                quality="Blessed",
                weapon_dmg=12,
                hp=0,
                ac=0,
                mana=0,
                strength=6,
                endurance=None,
                dexterity=4,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
            ItemStats(
                item_stable_key="TestSword",
                quality="Godly",
                weapon_dmg=14,
                hp=0,
                ac=0,
                mana=0,
                strength=7,
                endurance=None,
                dexterity=5,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
        ]

        enriched = enrich_item(weapon, stats)
        result = generator.generate_template(enriched, "Test Sword")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Test Sword" in result

        # Should contain {{Item/Weapon}} templates
        assert "{{Item/Weapon" in result

        # Should have tier markers for all three quality levels
        assert "|tier=0" in result  # Normal
        assert "|tier=1" in result  # Blessed
        assert "|tier=2" in result  # Godly

        # Should have weapon stats
        assert "|damage=10" in result  # Normal weapon dmg
        assert "|damage=12" in result  # Blessed weapon dmg
        assert "|damage=14" in result  # Godly weapon dmg

        # Should be in a wiki table
        assert "{|" in result
        assert "|}" in result

    def test_weapon_without_stats_raises_error(self, generator, enrich_item):
        """Test weapon without stats raises ValueError (fail fast)."""

        weapon = Item(
            id="101",
            resource_name="BrokenSword",
            stable_key="item:brokensword",
            item_name="Broken Sword",
            required_slot="Primary",
            weapon_dly=2.0,
        )

        enriched = enrich_item(weapon, stats=[])

        with pytest.raises(ValueError, match="has no ItemStats - this should NEVER happen"):
            generator.generate_template(enriched, "Broken Sword")

    def test_armor_with_stats_generates_fancy_armor_templates(self, generator, enrich_item):
        """Test armor with stats generates {{Item}} + {{Item/Armor}} templates."""

        armor = Item(
            id="102",
            resource_name="TestHelmet",
            stable_key="item:test helmet",
            item_name="Test Helmet",
            lore="Protective headgear",
            required_slot="Head",
            classes="Paladin",
        )

        stats = [
            ItemStats(
                item_stable_key="TestHelmet",
                quality="Normal",
                weapon_dmg=0,
                hp=50,
                ac=10,
                mana=0,
                strength=None,
                endurance=5,
                dexterity=None,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=5,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
            ItemStats(
                item_stable_key="TestHelmet",
                quality="Blessed",
                weapon_dmg=0,
                hp=62,
                ac=12,
                mana=0,
                strength=None,
                endurance=6,
                dexterity=None,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=6,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
            ItemStats(
                item_stable_key="TestHelmet",
                quality="Godly",
                weapon_dmg=0,
                hp=75,
                ac=15,
                mana=0,
                strength=None,
                endurance=7,
                dexterity=None,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=7,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
        ]

        enriched = enrich_item(armor, stats)
        result = generator.generate_template(enriched, "Test Helmet")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Test Helmet" in result

        # Should contain {{Item/Armor}} templates
        assert "{{Item/Armor" in result

        # Should have tier markers for all three quality levels
        assert "|tier=0" in result  # Normal
        assert "|tier=1" in result  # Blessed
        assert "|tier=2" in result  # Godly

        # Should have armor stats
        assert "|armor=10" in result  # Normal AC
        assert "|armor=12" in result  # Blessed AC
        assert "|armor=15" in result  # Godly AC

        assert "|health=50" in result  # Normal HP
        assert "|health=62" in result  # Blessed HP
        assert "|health=75" in result  # Godly HP

        # Should be in a wiki table
        assert "{|" in result
        assert "|}" in result

    def test_armor_without_stats_raises_error(self, generator, enrich_item):
        """Test armor without stats raises ValueError (fail fast)."""

        armor = Item(
            id="103",
            resource_name="BrokenHelmet",
            stable_key="item:brokenhelmet",
            item_name="Broken Helmet",
            required_slot="Head",
        )

        enriched = enrich_item(armor, stats=[])

        with pytest.raises(ValueError, match="has no ItemStats - this should NEVER happen"):
            generator.generate_template(enriched, "Broken Helmet")

    def test_general_item_without_stats_works(self, generator, enrich_item):
        """Test general items without stats work fine (no fancy template)."""

        potion = Item(
            id="104",
            resource_name="HealthPotion",
            stable_key="item:health_potion",
            item_name="Health Potion",
            lore="Restores health",
            required_slot="General",
            item_effect_on_click_stable_key="Heal",
            disposable=1,
        )

        enriched = enrich_item(potion, stats=[])
        result = generator.generate_template(enriched, "Health Potion")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Health Potion" in result

        # Should NOT contain fancy templates
        assert "{{Item/Weapon" not in result
        assert "{{Item/Armor" not in result

        # Should NOT have tier markers
        assert "|tier=" not in result

    def test_fancy_table_format(self, generator, enrich_item):
        """Test fancy templates are formatted in proper MediaWiki table."""

        weapon = Item(
            id="105",
            resource_name="TableTest",
            stable_key="item:table test",
            item_name="Table Test",
            required_slot="Primary",
            weapon_dly=1.5,
        )

        stats = [
            ItemStats(
                item_stable_key="TableTest",
                quality="Normal",
                weapon_dmg=5,
                hp=0,
                ac=0,
                mana=0,
                strength=None,
                endurance=None,
                dexterity=None,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
            ItemStats(
                item_stable_key="TableTest",
                quality="Blessed",
                weapon_dmg=6,
                hp=0,
                ac=0,
                mana=0,
                strength=None,
                endurance=None,
                dexterity=None,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
            ItemStats(
                item_stable_key="TableTest",
                quality="Godly",
                weapon_dmg=7,
                hp=0,
                ac=0,
                mana=0,
                strength=None,
                endurance=None,
                dexterity=None,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            ),
        ]

        enriched = enrich_item(weapon, stats)
        result = generator.generate_template(enriched, "Table Test")

        # Should start with table syntax
        assert "{|" in result

        # Should have header cells with fancy templates
        assert "!{{Item/Weapon" in result

        # Should end with table closing
        assert "|}" in result

        # Should have multiple fancy templates (one per quality tier)
        assert result.count("{{Item/Weapon") == 3


class TestTypeSpecificFields:
    """Test type-specific fields in the {{Item}} template for different item kinds."""

    def test_aura_item_has_buffgiven_field(self, generator, enrich_item):
        """Test aura items populate the buffgiven field with ability link."""
        from erenshor.domain.enriched_data.item import EnrichedItemData
        from erenshor.domain.entities.spell import Spell

        item = Item(
            id="200",
            resource_name="TestAura",
            stable_key="item:test_aura",
            item_name="Test Aura",
            lore="Grants a magical buff",
            required_slot="Aura",
            aura_stable_key="spell:test_buff",
        )

        # Create enriched data with aura spell
        aura_spell = Spell(
            stable_key="spell:test_buff",
            spell_name="Test Buff",
            type="Beneficial",
            spell_desc="A test buff effect",
        )
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            aura_spell=aura_spell,
        )

        result = generator.generate_template(enriched, "Test Aura")

        # buffgiven is NOT in {{Item}} infobox anymore - it's in the Item/Aura tooltip
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|buffgiven=" not in item_section
        # But the aura spell info should be in the Item/Aura tooltip
        assert "{{Item/Aura" in result
        assert "|aura_spell_name=" in result

    def test_spellscroll_item_has_taught_spell_fields(self, generator, mock_resolver):
        """Test spell scroll items populate taughtspell, spelltype, and manacost fields."""
        from erenshor.domain.enriched_data.item import EnrichedItemData
        from erenshor.domain.entities.spell import Spell

        item = Item(
            id="201",
            resource_name="SpellScrollFireball",
            stable_key="item:spell_scroll_fireball",
            item_name="Spell Scroll: Fireball",
            lore="Teaches the Fireball spell",
            required_slot="General",
            teach_spell_stable_key="spell:fireball",
        )

        # Create enriched data with taught spell
        taught_spell = Spell(
            stable_key="spell:fireball",
            spell_name="Fireball",
            type="Damage",
            mana_cost=150,
            spell_desc="Hurls a ball of fire",
        )
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            taught_spell=taught_spell,
        )

        result = generator.generate_template(enriched, "Spell Scroll: Fireball")

        # taughtspell is in {{Item}} infobox
        assert "|taughtspell={{AbilityLink|Test Ability}}" in result
        # spelltype and manacost are NOT in {{Item}} - they're in the Item/SpellScroll tooltip
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|spelltype=" not in item_section
        assert "|manacost=" not in item_section
        # But they should be in the Item/SpellScroll tooltip
        assert "{{Item/SpellScroll" in result
        assert "|spell_type=Damage" in result
        assert "|mana_cost=150" in result

    def test_skillbook_item_has_taught_skill_fields(self, generator, mock_resolver):
        """Test skill book items populate taughtskill and skilltype fields."""
        from erenshor.domain.enriched_data.item import EnrichedItemData
        from erenshor.domain.entities.skill import Skill

        item = Item(
            id="202",
            resource_name="SkillBookBackstab",
            stable_key="item:skill_book_backstab",
            item_name="Skill Book: Backstab",
            lore="Teaches the Backstab skill",
            required_slot="General",
            teach_skill_stable_key="skill:backstab",
        )

        # Create enriched data with taught skill
        taught_skill = Skill(
            stable_key="skill:backstab",
            skill_name="Backstab",
            type_of_skill="Attack",
            skill_desc="Deal major damage from behind",
            duelist_required_level=6,
        )
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            taught_skill=taught_skill,
        )

        result = generator.generate_template(enriched, "Skill Book: Backstab")

        # taughtskill is in {{Item}} infobox
        assert "|taughtskill={{AbilityLink|Test Ability}}" in result
        # skilltype is NOT in {{Item}} - it's in the Item/SkillBook tooltip
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|skilltype=" not in item_section
        # But it should be in the Item/SkillBook tooltip
        assert "{{Item/SkillBook" in result
        assert "|skill_type=Attack" in result

    def test_consumable_item_has_effect_and_disposable_fields(self, generator, mock_resolver):
        """Test consumable items populate effect and disposable fields."""
        from erenshor.domain.enriched_data.item import EnrichedItemData
        from erenshor.domain.entities.spell import Spell
        from erenshor.domain.value_objects.proc_info import ProcInfo

        item = Item(
            id="203",
            resource_name="HealthPotion",
            stable_key="item:health_potion",
            item_name="Health Potion",
            lore="Restores health",
            required_slot="General",
            item_effect_on_click_stable_key="spell:heal",
            disposable=1,
        )

        # Create enriched data with proc (effect) spell
        heal_spell = Spell(
            stable_key="spell:heal",
            spell_name="Heal",
            type="Heal",
            target_healing=50,
        )
        proc_info = ProcInfo(
            stable_key="spell:heal",
            description="Restores health",
            proc_chance="100",
            proc_style="Activatable",
            spell=heal_spell,
        )
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            proc=proc_info,
        )

        result = generator.generate_template(enriched, "Health Potion")

        # effect and disposable are NOT in {{Item}} - they're in the Item/Consumable tooltip
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|effect=" not in item_section
        assert "|disposable=" not in item_section
        # But they should be in the Item/Consumable tooltip
        assert "{{Item/Consumable" in result
        assert "|disposable=True" in result

    def test_non_disposable_consumable_has_empty_disposable(self, generator, mock_resolver):
        """Test non-disposable items have empty disposable field."""
        from erenshor.domain.enriched_data.item import EnrichedItemData
        from erenshor.domain.entities.spell import Spell
        from erenshor.domain.value_objects.proc_info import ProcInfo

        item = Item(
            id="204",
            resource_name="ReusableWand",
            stable_key="item:reusable_wand",
            item_name="Reusable Wand",
            lore="Can be used multiple times",
            required_slot="General",
            item_effect_on_click_stable_key="spell:spark",
            disposable=0,  # Not disposable
        )

        # Create enriched data with proc (effect) spell
        spark_spell = Spell(
            stable_key="spell:spark",
            spell_name="Spark",
            type="Damage",
            target_damage=10,
        )
        proc_info = ProcInfo(
            stable_key="spell:spark",
            description="Deals spark damage",
            proc_chance="100",
            proc_style="Activatable",
            spell=spark_spell,
        )
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            proc=proc_info,
        )

        result = generator.generate_template(enriched, "Reusable Wand")

        # Should NOT have disposable=True (empty instead)
        assert "|disposable=True" not in result
        # But field should still exist
        assert "|disposable=" in result

    def test_mold_item_has_produces_and_ingredients_fields(self, generator, mock_resolver):
        """Test mold items populate produces and ingredients fields."""
        from erenshor.domain.enriched_data.item import EnrichedItemData
        from erenshor.domain.value_objects.source_info import SourceInfo

        item = Item(
            id="205",
            resource_name="MoldCopperSword",
            stable_key="item:mold_copper_sword",
            item_name="Mold: Copper Sword",
            lore="A crafting template for copper sword",
            required_slot="General",
            template=1,
        )

        # Create source info with recipe data
        source_info = SourceInfo(
            vendors=[],
            drops=[],
            quest_rewards=[],
            quest_requirements=[],
            craft_sources=[],
            craft_recipe=[],
            component_for=[],
            crafting_results=[("item:copper_sword", 1)],  # Produces 1x Copper Sword
            recipe_ingredients=[
                ("item:copper_ore", 2),  # Needs 2x Copper Ore
                ("item:coal", 1),  # Needs 1x Coal
            ],
            item_drops=[],
        )
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            sources=source_info,
        )

        result = generator.generate_template(enriched, "Mold: Copper Sword")

        # produces and ingredients are NOT in {{Item}} - they're in the Item/Mold tooltip
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|produces=" not in item_section
        assert "|ingredients=" not in item_section
        # But they should be in the Item/Mold tooltip
        assert "{{Item/Mold" in result
        assert "|rewards=" in result  # produces is called "rewards" in Item/Mold
        assert "|ingredients=" in result  # ingredients is in the tooltip part

    def test_weapon_with_worn_effect_has_worneffect_field(self, generator, enrich_item):
        """Test weapons with worn effects populate worneffect field."""
        item = Item(
            id="206",
            resource_name="EnchantedSword",
            stable_key="item:enchanted_sword",
            item_name="Enchanted Sword",
            lore="Glows with magical energy",
            required_slot="Primary",
            weapon_dly=2.0,
            worn_effect_stable_key="spell:glow",
        )

        stats = [
            ItemStats(
                item_stable_key="EnchantedSword",
                quality="Normal",
                weapon_dmg=15,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
            ItemStats(
                item_stable_key="EnchantedSword",
                quality="Blessed",
                weapon_dmg=17,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
            ItemStats(
                item_stable_key="EnchantedSword",
                quality="Godly",
                weapon_dmg=19,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
        ]
        enriched = enrich_item(item, stats)

        result = generator.generate_template(enriched, "Enchanted Sword")

        # worneffect is NOT in {{Item}} template anymore - it's in tooltip templates only
        item_section = result.split("}}")[0]
        assert "|worneffect=" not in item_section
        # But should be in the Item/Weapon tooltip
        assert "{{Item/Weapon" in result

    def test_general_item_with_worn_effect_has_worneffect_field(self, generator, mock_resolver):
        """Test general items with worn effects - worneffect is in tooltip, not infobox."""
        from erenshor.domain.enriched_data.item import EnrichedItemData

        item = Item(
            id="207",
            resource_name="MagicRing",
            stable_key="item:magic_ring",
            item_name="Magic Ring",
            lore="A ring that grants a passive effect",
            required_slot="General",
            worn_effect_stable_key="spell:minor_protection",
        )

        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
        )

        result = generator.generate_template(enriched, "Magic Ring")

        # worneffect is NOT in {{Item}} infobox - it's in Item/General tooltip
        item_section = result.split("}}")[0]
        assert "|worneffect=" not in item_section

    def test_weapon_with_proc_effect_has_proceffect_field(self, generator, enrich_item):
        """Test weapons with proc on hit populate proceffect field."""
        item = Item(
            id="208",
            resource_name="VenomousBlade",
            stable_key="item:venomous_blade",
            item_name="Venomous Blade",
            lore="Coated in deadly poison",
            required_slot="Primary",
            weapon_dly=1.8,
            weapon_proc_on_hit_stable_key="spell:poison_proc",
        )

        stats = [
            ItemStats(
                item_stable_key="VenomousBlade",
                quality="Normal",
                weapon_dmg=12,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
            ItemStats(
                item_stable_key="VenomousBlade",
                quality="Blessed",
                weapon_dmg=14,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
            ItemStats(
                item_stable_key="VenomousBlade",
                quality="Godly",
                weapon_dmg=16,
                hp=0,
                ac=0,
                mana=0,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
            ),
        ]
        enriched = enrich_item(item, stats)

        result = generator.generate_template(enriched, "Venomous Blade")

        # proceffect is NOT in {{Item}} template anymore - it's in tooltip templates only
        item_section = result.split("}}")[0]
        assert "|proceffect=" not in item_section
        # But should be in the Item/Weapon tooltip
        assert "{{Item/Weapon" in result

    def test_spellscroll_without_spell_data_has_empty_fields(self, generator, mock_resolver):
        """Test spell scroll with no enriched spell data has empty type/mana fields in tooltip."""
        from erenshor.domain.enriched_data.item import EnrichedItemData

        item = Item(
            id="209",
            resource_name="MysterySpellScroll",
            stable_key="item:mystery_spell_scroll",
            item_name="Spell Scroll: Mystery",
            lore="Teaches an unknown spell",
            required_slot="General",
            teach_spell_stable_key="spell:mystery",
        )

        # No taught_spell provided (spell data not found in DB)
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            taught_spell=None,
        )

        result = generator.generate_template(enriched, "Spell Scroll: Mystery")

        # taughtspell is in {{Item}} infobox
        assert "|taughtspell={{AbilityLink|Test Ability}}" in result
        # spelltype and manacost are NOT in {{Item}} - they're in the Item/SpellScroll tooltip
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|spelltype=" not in item_section
        assert "|manacost=" not in item_section

    def test_skillbook_without_skill_data_has_empty_fields(self, generator, mock_resolver):
        """Test skill book with no enriched skill data has empty type field in tooltip."""
        from erenshor.domain.enriched_data.item import EnrichedItemData

        item = Item(
            id="210",
            resource_name="MysterySkillBook",
            stable_key="item:mystery_skill_book",
            item_name="Skill Book: Mystery",
            lore="Teaches an unknown skill",
            required_slot="General",
            teach_skill_stable_key="skill:mystery",
        )

        # No taught_skill provided (skill data not found in DB)
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            taught_skill=None,
        )

        result = generator.generate_template(enriched, "Skill Book: Mystery")

        # taughtskill is in {{Item}} infobox
        assert "|taughtskill={{AbilityLink|Test Ability}}" in result
        # skilltype is NOT in {{Item}} - it's in the Item/SkillBook tooltip
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|skilltype=" not in item_section

    def test_mold_without_sources_has_empty_recipe_fields(self, generator, mock_resolver):
        """Test mold item without sources has empty produces/ingredients fields."""
        from erenshor.domain.enriched_data.item import EnrichedItemData

        item = Item(
            id="211",
            resource_name="BrokenMold",
            stable_key="item:broken_mold",
            item_name="Broken Mold",
            lore="A damaged crafting template",
            required_slot="General",
            template=1,
        )

        # No sources provided
        enriched = EnrichedItemData(
            item=item,
            stats=[],
            classes=[],
            sources=None,
        )

        result = generator.generate_template(enriched, "Broken Mold")

        # produces and ingredients are NOT in {{Item}} - they're in the Item/Mold tooltip
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|produces=" not in item_section
        assert "|ingredients=" not in item_section
        # They should be in the Item/Mold tooltip (but empty)
        assert "{{Item/Mold" in result
