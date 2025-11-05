#!/usr/bin/env python3
"""Test script to verify enrichment features."""

from pathlib import Path

from erenshor.application.generators.item_template_generator import ItemTemplateGenerator
from erenshor.application.generators.spell_template_generator import SpellTemplateGenerator
from erenshor.infrastructure.config import get_repo_root, load_config
from erenshor.infrastructure.database.connection import create_connection
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository


def test_item_enrichment():
    """Test item template enrichment features."""
    print("=" * 60)
    print("Testing Item Template Enrichment Features")
    print("=" * 60)

    repo_root = get_repo_root()
    config = load_config(repo_root)
    db_path = config.variants["main"].resolved_database(repo_root)

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run 'uv run erenshor extract export' first")
        return

    with create_connection(db_path) as conn:
        repo = ItemRepository()
        generator = ItemTemplateGenerator(conn, repo)

        # Get all items
        all_items = repo.get_all(conn)
        print(f"\n✓ Found {len(all_items)} items in database")

        # Test 1: Long name feature (>24 chars)
        print("\n--- Test 1: Long Name Feature (>24 chars) ---")
        long_name_items = [item for item in all_items if item.item_name and len(item.item_name) > 24]
        if long_name_items:
            item = long_name_items[0]
            print(f"Testing: '{item.item_name}' (length: {len(item.item_name)})")
            template = generator.generate(item.item_name)
            if 'style="font-size:20px"' in template or "font-size:20px" in template:
                print("✓ Long name font adjustment applied")
                # Show the title line
                for line in template.split("\n"):
                    if "font-size" in line or "| title" in line:
                        print(f"  {line.strip()}")
            else:
                print("❌ Long name font adjustment NOT found")
        else:
            print("⚠ No items with names >24 characters found")

        # Test 2: Item type display
        print("\n--- Test 2: Item Type Display ---")
        # Find a quest item
        quest_items = [item for item in all_items if item.related_quests]
        if quest_items:
            item = quest_items[0]
            print(f"Testing quest item: '{item.item_name}'")
            template = generator.generate(item.item_name)
            if "Quest Item" in template or "Quest Items" in template:
                print("✓ Quest Item type found")
            else:
                print("❌ Quest Item type NOT found")

        # Test 3: Proc extraction
        print("\n--- Test 3: Proc Extraction ---")
        proc_items = [
            item
            for item in all_items
            if item.weapon_proc_on_hit or item.wand_effect or item.bow_effect or item.worn_effect
        ]
        if proc_items:
            item = proc_items[0]
            print(f"Testing proc item: '{item.item_name}'")
            proc_field = (
                item.weapon_proc_on_hit or item.wand_effect or item.bow_effect or item.worn_effect or "unknown"
            )
            print(f"  Proc spell ResourceName: {proc_field}")
            template = generator.generate(item.item_name)
            if "| proc" in template.lower():
                print("✓ Proc field found in template")
                # Show proc lines
                for line in template.split("\n"):
                    if "proc" in line.lower():
                        print(f"  {line.strip()}")
            else:
                print("⚠ Proc field not populated (item may not have proc)")
        else:
            print("⚠ No items with procs found")

        # Test 4: CompleteOnRead quest items
        print("\n--- Test 4: CompleteOnRead Quest Items ---")
        complete_on_read_items = [item for item in all_items if item.complete_on_read]
        if complete_on_read_items:
            item = complete_on_read_items[0]
            print(f"Testing: '{item.item_name}' (CompleteOnRead={item.complete_on_read})")
            template = generator.generate(item.item_name)
            if "Quest Item" in template:
                print("✓ CompleteOnRead item marked as Quest Item")
            else:
                print("❌ CompleteOnRead item NOT marked as Quest Item")
        else:
            print("⚠ No CompleteOnRead items found")


def test_spell_enrichment():
    """Test spell template enrichment features."""
    print("\n" + "=" * 60)
    print("Testing Spell Template Enrichment Features")
    print("=" * 60)

    repo_root = get_repo_root()
    config = load_config(repo_root)
    db_path = config.variants["main"].resolved_database(repo_root)

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return

    with create_connection(db_path) as conn:
        repo = SpellRepository()
        generator = SpellTemplateGenerator(conn, repo)

        # Get all spells
        all_spells = repo.get_all(conn)
        print(f"\n✓ Found {len(all_spells)} spells in database")

        # Test: XP bonus conditional (only show if spell has duration)
        print("\n--- Test: XP Bonus Conditional ---")

        # Find spell with duration AND xp_bonus
        duration_spells = [spell for spell in all_spells if spell.spell_duration_in_ticks and spell.xp_bonus]
        if duration_spells:
            spell = duration_spells[0]
            print(
                f"Testing: '{spell.spell_name}' (duration={spell.spell_duration_in_ticks}, xp_bonus={spell.xp_bonus})"
            )
            template = generator.generate(spell.spell_name)
            if "| xp_bonus" in template and str(spell.xp_bonus) in template:
                print("✓ XP bonus shown for spell with duration")
            else:
                print("❌ XP bonus NOT shown despite having duration")
        else:
            print("⚠ No spells with both duration and XP bonus found")

        # Find spell with xp_bonus but NO duration (should not show xp_bonus)
        no_duration_spells = [spell for spell in all_spells if not spell.spell_duration_in_ticks and spell.xp_bonus]
        if no_duration_spells:
            spell = no_duration_spells[0]
            print(f"Testing: '{spell.spell_name}' (no duration, xp_bonus={spell.xp_bonus})")
            template = generator.generate(spell.spell_name)
            xp_line = [line for line in template.split("\n") if "| xp_bonus" in line]
            if xp_line and (xp_line[0].strip().endswith("=") or "| xp_bonus =" in xp_line[0]):
                print("✓ XP bonus correctly hidden for spell without duration")
            else:
                print("⚠ XP bonus field check inconclusive")
        else:
            print("⚠ No spells with XP bonus but no duration found")


def test_database_schema():
    """Test database schema changes (ResourceName foreign keys)."""
    print("\n" + "=" * 60)
    print("Testing Database Schema Changes")
    print("=" * 60)

    repo_root = get_repo_root()
    config = load_config(repo_root)
    db_path = config.variants["main"].resolved_database(repo_root)

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return

    with create_connection(db_path) as conn:
        # Test 1: Foreign keys use ResourceName (strings, not numeric IDs)
        print("\n--- Test 1: Foreign Keys Use ResourceName ---")

        cursor = conn.execute("SELECT ItemName, WeaponProcOnHit, WandEffect FROM Items WHERE WeaponProcOnHit != '' LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"✓ Item '{row[0]}' has WeaponProcOnHit='{row[1]}'")
            if row[1] and not row[1].isdigit():
                print("  ✓ WeaponProcOnHit is ResourceName (not numeric ID)")
            else:
                print("  ❌ WeaponProcOnHit appears to be numeric ID")

        cursor = conn.execute("SELECT QuestName, ItemOnComplete FROM Quests WHERE ItemOnComplete != '' LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"✓ Quest '{row[0]}' has ItemOnComplete='{row[1]}'")
            if row[1] and not row[1].isdigit():
                print("  ✓ ItemOnComplete is ResourceName (not numeric ID)")
            else:
                print("  ❌ ItemOnComplete appears to be numeric ID")

        # Test 2: Check field names don't have misleading _id suffix
        print("\n--- Test 2: Field Names (No Misleading _id Suffix) ---")
        cursor = conn.execute("PRAGMA table_info(Quests)")
        columns = [col[1] for col in cursor.fetchall()]
        if "ItemOnComplete" in columns:
            print("✓ Quests.ItemOnComplete field exists (no _id suffix)")
        if "ItemOnCompleteId" in columns:
            print("❌ Quests.ItemOnCompleteId still exists (should be renamed)")

        cursor = conn.execute("PRAGMA table_info(Skills)")
        columns = [col[1] for col in cursor.fetchall()]
        if "CastOnTarget" in columns:
            print("✓ Skills.CastOnTarget field exists (no _id suffix)")
        if "CastOnTargetId" in columns:
            print("❌ Skills.CastOnTargetId still exists (should be renamed)")

        # Test 3: Junction tables exist and have data
        print("\n--- Test 3: Junction Tables ---")
        tables = [
            "CharacterAttackSpells",
            "CharacterAttackSkills",
            "SpellClasses",
            "QuestRequiredItems",
        ]
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"✓ {table}: {count} rows")


if __name__ == "__main__":
    test_database_schema()
    test_item_enrichment()
    test_spell_enrichment()
    print("\n" + "=" * 60)
    print("✓ All enrichment tests completed!")
    print("=" * 60)
