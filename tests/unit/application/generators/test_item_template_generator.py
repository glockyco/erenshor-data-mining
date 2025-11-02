"""Unit tests for ItemTemplateGenerator.

Tests item page generation for different item types including weapons, armor,
consumables, and general items.
"""

from erenshor.application.generators.item_template_generator import ItemTemplateGenerator
from erenshor.domain.entities.item import Item


class TestItemTemplateGenerator:
    """Test suite for ItemTemplateGenerator."""

    def test_init_creates_category_generator(self):
        """Test that initialization creates category generator."""
        generator = ItemTemplateGenerator()
        assert generator._category_generator is not None

    def test_generate_page_for_general_item(self):
        """Test generating page for general item."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="1",
            resource_name="TestItem",
            item_name="Test Item",
            lore="A test item",
            required_slot="General",
            item_value=100,
            sell_value=25,
        )

        result = generator.generate_template(item, page_title="Test Item")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Test Item" in result
        assert "|description=A test item" in result
        assert "|buy=100" in result
        assert "|sell=25" in result

        # Should contain category tags
        assert "[[Category:" in result

    def test_generate_page_for_weapon(self):
        """Test generating page for weapon."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="2",
            resource_name="TestSword",
            item_name="Test Sword",
            lore="A sharp blade",
            required_slot="Primary",
            weapon_dly=2.0,
            classes="Duelist, Paladin",
            item_value=500,
            sell_value=125,
        )

        result = generator.generate_template(item, page_title="Test Sword")

        # Should contain {{Item}} template (fancy weapon deferred for now)
        assert "{{Item" in result
        assert "|title=Test Sword" in result
        assert "|delay=2.0" in result
        assert "|classes=Duelist, Paladin" in result

        # Should contain category tags
        assert "[[Category:" in result

    def test_generate_page_for_armor(self):
        """Test generating page for armor."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="3",
            resource_name="TestHelmet",
            item_name="Test Helmet",
            lore="Protective headgear",
            required_slot="Head",
            classes="Arcanist",
            item_value=300,
            sell_value=75,
        )

        result = generator.generate_template(item, page_title="Test Helmet")

        # Should contain {{Item}} template (fancy armor deferred for now)
        assert "{{Item" in result
        assert "|title=Test Helmet" in result
        assert "|description=Protective headgear" in result

        # Should contain category tags
        assert "[[Category:" in result

    def test_generate_page_for_charm(self):
        """Test generating page for charm."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="4",
            resource_name="TestCharm",
            item_name="Test Charm",
            lore="Magical charm",
            required_slot="Charm",
            classes="Arcanist, Druid",
        )

        result = generator.generate_template(item, page_title="Test Charm")

        # Should contain {{Item}} template (fancy charm deferred for now)
        assert "{{Item" in result
        assert "|title=Test Charm" in result

        # Should contain category tags
        assert "[[Category:" in result

    def test_generate_page_for_consumable(self):
        """Test generating page for consumable."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="5",
            resource_name="TestPotion",
            item_name="Test Potion",
            lore="Restores health",
            required_slot="General",
            item_effect_on_click="HealSpell",
            disposable=1,
            stackable=1,
            item_value=50,
            sell_value=10,
        )

        result = generator.generate_template(item, page_title="Test Potion")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Test Potion" in result

        # Should contain category tags (including Consumable)
        assert "[[Category:" in result

    def test_generate_page_for_mold(self):
        """Test generating page for mold (crafting template)."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="6",
            resource_name="TestMold",
            item_name="Test Mold",
            lore="Crafting template",
            required_slot="General",
            template=1,
            template_ingredient_ids="1,2,3",
            template_reward_ids="7",
        )

        result = generator.generate_template(item, page_title="Test Mold")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Test Mold" in result

        # Should contain category tags
        assert "[[Category:" in result

    def test_generate_page_for_ability_book(self):
        """Test generating page for ability book."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="7",
            resource_name="TestSpellBook",
            item_name="Spell Scroll: Fireball",
            lore="Teaches Fireball",
            required_slot="General",
            teach_spell="Fireball",
        )

        result = generator.generate_template(item, page_title="Spell Scroll: Fireball")

        # Should contain {{Item}} template
        assert "{{Item" in result
        assert "|title=Spell Scroll: Fireball" in result

        # Should contain category tags
        assert "[[Category:" in result

    def test_generate_page_handles_none_values(self):
        """Test that generator handles None values gracefully."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="8",
            resource_name="MinimalItem",
            item_name="Minimal Item",
            # Most fields are None
            required_slot=None,
            lore=None,
            classes=None,
            item_value=None,
            sell_value=None,
        )

        result = generator.generate_template(item, page_title="Minimal Item")

        # Should generate valid wikitext even with minimal data
        assert "{{Item" in result
        assert "|title=Minimal Item" in result
        # Empty fields should be present but empty
        assert "|description=" in result
        assert "|classes=" in result

    def test_generate_page_handles_relic_flag(self):
        """Test that relic flag is properly formatted."""
        generator = ItemTemplateGenerator()

        # Relic item
        relic_item = Item(
            id="9",
            resource_name="RelicItem",
            item_name="Relic Item",
            relic=1,
        )

        result = generator.generate_template(relic_item, page_title="Relic Item")
        assert "|relic=True" in result

        # Non-relic item
        normal_item = Item(
            id="10",
            resource_name="NormalItem",
            item_name="Normal Item",
            relic=0,
        )

        result = generator.generate_template(normal_item, page_title="Normal Item")
        assert "|relic=True" not in result
        assert "|relic=" in result  # Empty value

    def test_classify_weapon_by_required_slot(self):
        """Test weapon classification by RequiredSlot."""
        generator = ItemTemplateGenerator()

        # Primary slot weapon
        primary = Item(id="11", resource_name="Primary", item_name="Primary", required_slot="Primary")
        assert generator._classify(primary) == "weapon"

        # Secondary slot weapon
        secondary = Item(id="12", resource_name="Secondary", item_name="Secondary", required_slot="Secondary")
        assert generator._classify(secondary) == "weapon"

        # Two-hand weapon (via slot name pattern)
        twohanded = Item(id="13", resource_name="TwoHand", item_name="TwoHand", required_slot="PrimaryOrSecondary")
        assert generator._classify(twohanded) == "weapon"

    def test_classify_armor_by_required_slot(self):
        """Test armor classification by RequiredSlot."""
        generator = ItemTemplateGenerator()

        armor_slots = ["Head", "Shoulders", "Chest", "Hands", "Legs", "Feet", "Waist", "Neck", "Back"]

        for slot in armor_slots:
            item = Item(id=f"armor_{slot}", resource_name=slot, item_name=slot, required_slot=slot)
            assert generator._classify(item) == "armor", f"Failed for slot: {slot}"

    def test_classify_consumable(self):
        """Test consumable classification."""
        generator = ItemTemplateGenerator()

        consumable = Item(
            id="14",
            resource_name="Potion",
            item_name="Potion",
            required_slot="General",
            item_effect_on_click="HealSpell",
            disposable=1,
        )
        assert generator._classify(consumable) == "consumable"

    def test_classify_mold(self):
        """Test mold classification."""
        generator = ItemTemplateGenerator()

        mold = Item(
            id="15",
            resource_name="Mold",
            item_name="Mold",
            template=1,
        )
        assert generator._classify(mold) == "mold"

    def test_classify_ability_book(self):
        """Test ability book classification."""
        generator = ItemTemplateGenerator()

        spell_book = Item(
            id="16",
            resource_name="SpellBook",
            item_name="Spell Book",
            teach_spell="Fireball",
        )
        assert generator._classify(spell_book) == "ability_book"

        skill_book = Item(
            id="17",
            resource_name="SkillBook",
            item_name="Skill Book",
            teach_skill="Mining",
        )
        assert generator._classify(skill_book) == "ability_book"

    def test_classify_aura(self):
        """Test aura classification."""
        generator = ItemTemplateGenerator()

        aura = Item(
            id="18",
            resource_name="Aura",
            item_name="Aura",
            required_slot="Aura",
        )
        assert generator._classify(aura) == "aura"

    def test_build_item_template_context(self):
        """Test building template context from item."""
        generator = ItemTemplateGenerator()

        item = Item(
            id="19",
            resource_name="TestItem",
            item_name="Test Item",
            lore="Test description",
            classes="Arcanist, Duelist",
            item_value=100,
            sell_value=25,
            relic=1,
        )

        context = generator._build_item_template_context(item, page_title="Test Item")

        assert context["title"] == "Test Item"
        assert context["description"] == "Test description"
        assert context["classes"] == "Arcanist, Duelist"
        assert context["buy"] == "100"
        assert context["sell"] == "25"
        assert context["relic"] == "True"
        assert context["itemid"] == "19"
