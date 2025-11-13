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
            # Convert to title case (e.g., "testsword" -> "Test Sword")
            return " ".join(word.capitalize() for word in name.replace("_", " ").split())
        return "Test Item"

    def resolve_image_name(stable_key: str) -> str:
        return resolve_display_name(stable_key)

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
def generator(mock_resolver):
    """Create item template generator."""
    return ItemSectionGenerator(mock_resolver)


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
        # Verify {{Item}} section has empty stat fields
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|delay=" in item_section  # Field exists
        assert "|delay=2.0" not in item_section  # No value in Item template
        assert "|classes=" in item_section  # Field exists
        assert "|classes=Duelist" not in item_section  # No value in Item template
        assert "|description=" in item_section  # Field exists
        assert "|description=A sharp blade" not in item_section  # No value in Item template

        # Should contain {{Fancy-weapon}} template
        assert "{{Fancy-weapon" in result

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
        # Verify {{Item}} section has empty stat fields
        item_section = result.split("}}")[0]  # Get just the {{Item}} template
        assert "|description=" in item_section  # Field exists
        assert "|description=Protective headgear" not in item_section  # No value in Item template
        assert "|classes=" in item_section  # Field exists
        assert "|classes=Arcanist" not in item_section  # No value in Item template

        # Should contain {{Fancy-armor}} template
        assert "{{Fancy-armor" in result

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
            stable_key="item:testpotion",
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
            stable_key="item:testmold",
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
            resource_name="TestSpellBook",
            stable_key="item:testspellbook",
            item_name="Spell Scroll: Fireball",
            lore="Teaches Fireball",
            required_slot="General",
            teach_spell="Fireball",
        )

        enriched = enrich_item(item)
        result = generator.generate_template(enriched, "Spell Scroll: Fireball")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Spell Scroll: Fireball" in result

    def test_generate_page_handles_none_values(self, generator, enrich_item):
        """Test that generator handles None values gracefully."""

        item = Item(
            id="8",
            resource_name="MinimalItem",
            stable_key="item:minimalitem",
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
        # Empty fields should be present but empty
        assert "|description=" in result
        assert "|classes=" in result

    def test_generate_page_handles_relic_flag(self, generator, enrich_item):
        """Test that relic flag is properly formatted."""

        # Relic item
        relic_item = Item(
            id="9",
            resource_name="RelicItem",
            stable_key="item:relicitem",
            item_name="Relic Item",
            relic=1,
        )

        enriched = enrich_item(relic_item)
        result = generator.generate_template(enriched, "Relic Item")
        assert "|relic=True" in result

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
        assert "|relic=True" not in result
        assert "|relic=" in result  # Empty value

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
        """Test ability book classification."""

        spell_book = Item(
            id="16",
            resource_name="SpellBook",
            stable_key="item:spellbook",
            item_name="Spell Book",
            teach_spell_stable_key="Fireball",
        )
        assert generator._classify(spell_book) == ItemKind.ABILITY_BOOK

        skill_book = Item(
            id="17",
            resource_name="SkillBook",
            stable_key="item:skillbook",
            item_name="Skill Book",
            teach_skill_stable_key="Mining",
        )
        assert generator._classify(skill_book) == ItemKind.ABILITY_BOOK

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
            stable_key="item:testitem",
            item_name="Test Item",
            lore="Test description",
            item_value=100,
            sell_value=25,
            relic=1,
        )

        enriched = enrich_item(item, classes=["Arcanist", "Duelist"])
        context = generator._build_item_template_context(enriched, page_title="Test Item")

        assert context["title"] == "Test Item"
        assert context["description"] == "Test description"
        assert context["classes"] == "[[Arcanist]], [[Duelist]]"
        assert context["buy"] == "100"
        assert context["sell"] == "25"
        assert context["relic"] == "True"

    def test_long_name_font_adjustment(self, generator, enrich_item):
        """Test that long item names (>24 chars) get smaller font."""

        # Short name - no font adjustment
        short_item = Item(
            id="20",
            resource_name="ShortItem",
            stable_key="item:shortitem",
            item_name="Short Name",
            required_slot="General",
        )
        enriched = enrich_item(short_item)
        short_result = generator.generate_template(enriched, "Short Name")
        assert "|title=Short Name" in short_result
        assert '<span style="font-size:' not in short_result

        # Long name (>24 chars) - should get font adjustment
        long_item = Item(
            id="21",
            resource_name="LongItem",
            stable_key="item:longitem",
            item_name="This is a very long item name that exceeds 24 characters",
            required_slot="General",
        )
        enriched = enrich_item(long_item)
        long_result = generator.generate_template(enriched, "This is a very long item name that exceeds 24 characters")
        assert (
            '<span style="font-size:20px">This is a very long item name that exceeds 24 characters</span>'
            in long_result
        )

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
        """Test weapon with stats generates {{Item}} + {{Fancy-weapon}} templates."""

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

        # Should contain {{Fancy-weapon}} templates
        assert "{{Fancy-weapon" in result

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
        """Test armor with stats generates {{Item}} + {{Fancy-armor}} templates."""

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

        # Should contain {{Fancy-armor}} templates
        assert "{{Fancy-armor" in result

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
            stable_key="item:healthpotion",
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
        assert "{{Fancy-weapon" not in result
        assert "{{Fancy-armor" not in result

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
        assert "!{{Fancy-weapon" in result

        # Should end with table closing
        assert "|}" in result

        # Should have multiple fancy templates (one per quality tier)
        assert result.count("{{Fancy-weapon") == 3
