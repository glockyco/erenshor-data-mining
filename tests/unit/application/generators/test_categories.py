"""Tests for category tag generation."""

import pytest

from erenshor.application.generators.categories import CategoryGenerator
from erenshor.domain.entities.item import Item


class TestCategoryGenerator:
    """Test CategoryGenerator class."""

    @pytest.fixture
    def generator(self) -> CategoryGenerator:
        """Create CategoryGenerator instance."""
        return CategoryGenerator()

    # Primary category tests (based on item kind)

    def test_weapon_category(self, generator: CategoryGenerator) -> None:
        """Test weapon items get 'Weapons' category."""
        item = Item(
            id="1",
            resource_name="IronSword",
            required_slot="Primary",
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Weapons"]

    def test_armor_category(self, generator: CategoryGenerator) -> None:
        """Test armor items get 'Armor' category."""
        item = Item(
            id="2",
            resource_name="IronHelm",
            required_slot="Head",
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Armor"]

    def test_consumable_category(self, generator: CategoryGenerator) -> None:
        """Test consumable items get 'Consumables' category."""
        item = Item(
            id="3",
            resource_name="HealthPotion",
            required_slot="General",
            item_effect_on_click="HealSpell",
            disposable=1,
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Consumables"]

    def test_mold_category(self, generator: CategoryGenerator) -> None:
        """Test mold items get 'Molds' category."""
        item = Item(
            id="4",
            resource_name="SwordMold",
            required_slot="General",
            template=1,
        )
        categories = generator.generate_item_categories(item)
        assert "Molds" in categories

    def test_ability_book_category(self, generator: CategoryGenerator) -> None:
        """Test ability books get 'Ability Books' category."""
        item = Item(
            id="5",
            resource_name="FireballBook",
            required_slot="General",
            teach_spell="Fireball",
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Ability Books"]

    def test_aura_category(self, generator: CategoryGenerator) -> None:
        """Test aura items get 'Auras' category."""
        item = Item(
            id="6",
            resource_name="StrengthAura",
            required_slot="Aura",
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Auras"]

    def test_general_category(self, generator: CategoryGenerator) -> None:
        """Test general items get 'Items' category."""
        item = Item(
            id="7",
            resource_name="RandomItem",
            required_slot="General",
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Items"]

    # Secondary category tests (multi-category support)

    def test_quest_item_category(self, generator: CategoryGenerator) -> None:
        """Test items with quest interactions get 'Quest Items' category."""
        item = Item(
            id="8",
            resource_name="QuestStarter",
            required_slot="General",
            assign_quest_on_read="SomeQuest",
        )
        categories = generator.generate_item_categories(item)
        assert "Items" in categories
        assert "Quest Items" in categories

    def test_quest_completion_item_category(self, generator: CategoryGenerator) -> None:
        """Test items that complete quests get 'Quest Items' category."""
        item = Item(
            id="9",
            resource_name="QuestCompletion",
            required_slot="General",
            complete_on_read="SomeQuest",
        )
        categories = generator.generate_item_categories(item)
        assert "Items" in categories
        assert "Quest Items" in categories

    def test_mold_gets_crafting_materials_category(self, generator: CategoryGenerator) -> None:
        """Test molds (template=1) get 'Crafting Materials' category."""
        item = Item(
            id="10",
            resource_name="ArmorMold",
            required_slot="General",
            template=1,
        )
        categories = generator.generate_item_categories(item)
        assert "Molds" in categories
        assert "Crafting Materials" in categories

    # Multi-category tests

    def test_weapon_quest_item_multiple_categories(self, generator: CategoryGenerator) -> None:
        """Test weapon that's also a quest item gets both categories."""
        item = Item(
            id="11",
            resource_name="QuestSword",
            required_slot="Primary",
            assign_quest_on_read="HeroQuest",
        )
        categories = generator.generate_item_categories(item)
        assert "Weapons" in categories
        assert "Quest Items" in categories

    def test_consumable_quest_item_multiple_categories(self, generator: CategoryGenerator) -> None:
        """Test consumable quest item gets both categories."""
        item = Item(
            id="12",
            resource_name="QuestPotion",
            required_slot="General",
            item_effect_on_click="HealSpell",
            disposable=1,
            complete_on_read="QuestName",
        )
        categories = generator.generate_item_categories(item)
        assert "Consumables" in categories
        assert "Quest Items" in categories

    # Edge cases

    def test_empty_quest_fields_not_quest_item(self, generator: CategoryGenerator) -> None:
        """Test items with empty quest fields don't get 'Quest Items' category."""
        item = Item(
            id="13",
            resource_name="RegularItem",
            required_slot="General",
            assign_quest_on_read="",  # Empty string
            complete_on_read="   ",  # Whitespace only
        )
        categories = generator.generate_item_categories(item)
        assert "Quest Items" not in categories

    def test_no_duplicates_in_categories(self, generator: CategoryGenerator) -> None:
        """Test category list has no duplicates."""
        item = Item(
            id="14",
            resource_name="TestItem",
            required_slot="Primary",
        )
        categories = generator.generate_item_categories(item)
        assert len(categories) == len(set(categories))

    def test_always_has_at_least_one_category(self, generator: CategoryGenerator) -> None:
        """Test all items get at least one category (primary)."""
        item = Item(
            id="15",
            resource_name="MinimalItem",
            required_slot=None,
        )
        categories = generator.generate_item_categories(item)
        assert len(categories) >= 1
        assert "Items" in categories  # Fallback to general

    # Format tests

    def test_format_single_category(self, generator: CategoryGenerator) -> None:
        """Test formatting single category tag."""
        formatted = generator.format_category_tags(["Weapons"])
        assert formatted == "[[Category:Weapons]]"

    def test_format_multiple_categories(self, generator: CategoryGenerator) -> None:
        """Test formatting multiple category tags."""
        formatted = generator.format_category_tags(["Molds", "Crafting Materials"])
        expected = "[[Category:Molds]]\n[[Category:Crafting Materials]]"
        assert formatted == expected

    def test_format_empty_list(self, generator: CategoryGenerator) -> None:
        """Test formatting empty category list."""
        formatted = generator.format_category_tags([])
        assert formatted == ""

    # Integration tests with classify_item_kind

    def test_secondary_weapon_classification(self, generator: CategoryGenerator) -> None:
        """Test secondary weapon slot gets 'Weapons' category."""
        item = Item(
            id="16",
            resource_name="Shield",
            required_slot="Secondary",
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Weapons"]

    def test_primary_or_secondary_weapon_classification(self, generator: CategoryGenerator) -> None:
        """Test PrimaryOrSecondary slot gets 'Weapons' category."""
        item = Item(
            id="17",
            resource_name="Dagger",
            required_slot="PrimaryOrSecondary",
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Weapons"]

    def test_ability_book_with_teach_skill(self, generator: CategoryGenerator) -> None:
        """Test items with teach_skill get 'Ability Books' category."""
        item = Item(
            id="18",
            resource_name="MiningBook",
            required_slot="General",
            teach_skill="Mining",
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Ability Books"]

    def test_non_consumable_general_item(self, generator: CategoryGenerator) -> None:
        """Test general items without click effect are not consumables."""
        item = Item(
            id="19",
            resource_name="Junk",
            required_slot="General",
            disposable=1,  # Has disposable flag but no click effect
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Items"]
        assert "Consumables" not in categories

    def test_armor_slots(self, generator: CategoryGenerator) -> None:
        """Test various armor slots get 'Armor' category."""
        slots = ["Head", "Chest", "Legs", "Hands", "Feet", "Neck", "Finger", "Back"]
        for slot in slots:
            item = Item(
                id=f"armor_{slot}",
                resource_name=f"{slot}Armor",
                required_slot=slot,
            )
            categories = generator.generate_item_categories(item)
            assert categories == ["Armor"], f"Failed for slot: {slot}"

    # Real-world examples

    def test_real_world_sword(self, generator: CategoryGenerator) -> None:
        """Test realistic sword item."""
        item = Item(
            id="100",
            resource_name="IronSword",
            item_name="Iron Sword",
            required_slot="Primary",
            this_weapon_type="Sword",
            item_level=10,
        )
        categories = generator.generate_item_categories(item)
        assert categories == ["Weapons"]

    def test_real_world_quest_potion(self, generator: CategoryGenerator) -> None:
        """Test realistic quest consumable item."""
        item = Item(
            id="101",
            resource_name="ElixirOfLife",
            item_name="Elixir of Life",
            required_slot="General",
            item_effect_on_click="FullHeal",
            disposable=1,
            unique=1,
            assign_quest_on_read="LifeQuest",
        )
        categories = generator.generate_item_categories(item)
        assert "Consumables" in categories
        assert "Quest Items" in categories
        assert len(categories) == 2

    def test_real_world_armor_mold(self, generator: CategoryGenerator) -> None:
        """Test realistic armor mold item."""
        item = Item(
            id="102",
            resource_name="PlateArmorMold",
            item_name="Plate Armor Mold",
            required_slot="General",
            template=1,
            template_ingredient_ids="Iron,Steel",
            template_reward_ids="PlateArmor",
        )
        categories = generator.generate_item_categories(item)
        assert "Molds" in categories
        assert "Crafting Materials" in categories
        assert len(categories) == 2
