#!/usr/bin/env python3
"""Test script to verify enrichment features."""

import sqlite3

from erenshor.infrastructure.config import get_repo_root, load_config


def test_database_schema():
    """Test database schema changes (ResourceName foreign keys)."""
    print("=" * 60)
    print("Testing Database Schema Changes")
    print("=" * 60)

    repo_root = get_repo_root()
    config = load_config()
    db_path = config.variants["main"].resolved_database(repo_root)

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run 'uv run erenshor extract export' first")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    success = True

    try:
        # Test 1: Foreign keys use ResourceName (strings, not numeric IDs)
        print("\n--- Test 1: Foreign Keys Use ResourceName ---")

        cursor = conn.execute(
            "SELECT ItemName, WeaponProcOnHit, WandEffect FROM Items WHERE WeaponProcOnHit != '' LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            print(f"✓ Item '{row['ItemName']}' has WeaponProcOnHit='{row['WeaponProcOnHit']}'")
            if row["WeaponProcOnHit"] and not row["WeaponProcOnHit"].isdigit():
                print("  ✓ WeaponProcOnHit is ResourceName (not numeric ID)")
            else:
                print("  ❌ WeaponProcOnHit appears to be numeric ID")
                success = False
        else:
            print("  ⚠ No items with WeaponProcOnHit found")

        cursor = conn.execute("SELECT QuestName, ItemOnComplete FROM Quests WHERE ItemOnComplete != '' LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"✓ Quest '{row['QuestName']}' has ItemOnComplete='{row['ItemOnComplete']}'")
            if row["ItemOnComplete"] and not row["ItemOnComplete"].isdigit():
                print("  ✓ ItemOnComplete is ResourceName (not numeric ID)")
            else:
                print("  ❌ ItemOnComplete appears to be numeric ID")
                success = False
        else:
            print("  ⚠ No quests with ItemOnComplete found")

        # Test 2: Check field names don't have misleading _id suffix
        print("\n--- Test 2: Field Names (No Misleading _id Suffix) ---")
        cursor = conn.execute("PRAGMA table_info(Quests)")
        columns = [col[1] for col in cursor.fetchall()]
        if "ItemOnComplete" in columns:
            print("✓ Quests.ItemOnComplete field exists (no _id suffix)")
        else:
            print("❌ Quests.ItemOnComplete field missing")
            success = False
        if "ItemOnCompleteId" in columns:
            print("❌ Quests.ItemOnCompleteId still exists (should be renamed)")
            success = False

        cursor = conn.execute("PRAGMA table_info(Skills)")
        columns = [col[1] for col in cursor.fetchall()]
        if "CastOnTarget" in columns:
            print("✓ Skills.CastOnTarget field exists (no _id suffix)")
        else:
            print("❌ Skills.CastOnTarget field missing")
            success = False
        if "CastOnTargetId" in columns:
            print("❌ Skills.CastOnTargetId still exists (should be renamed)")
            success = False

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
            if count > 0:
                print(f"✓ {table}: {count} rows")
            else:
                print(f"⚠ {table}: 0 rows (may be expected)")

        # Test 4: Check denormalized fields were removed
        print("\n--- Test 4: Denormalized Fields Removed ---")
        cursor = conn.execute("PRAGMA table_info(Characters)")
        columns = [col[1] for col in cursor.fetchall()]

        removed_fields = [
            "AttackSkills",
            "AttackSpells",
            "BuffSpells",
            "HealSpells",
            "GroupHealSpells",
            "CCSpells",
            "TauntSpells",
        ]
        for field in removed_fields:
            if field in columns:
                print(f"❌ Characters.{field} still exists (should be removed)")
                success = False

        if not any(field in columns for field in removed_fields):
            print("✓ Denormalized spell/skill fields removed from Characters")

        # PetSpell and ProcOnHit should remain
        if "PetSpell" in columns and "ProcOnHit" in columns:
            print("✓ PetSpell and ProcOnHit fields retained (as expected)")
        else:
            print("❌ PetSpell or ProcOnHit missing")
            success = False

    finally:
        conn.close()

    return success


def test_enrichment_constants():
    """Test that enrichment constants are defined."""
    print("\n" + "=" * 60)
    print("Testing Enrichment Constants")
    print("=" * 60)

    try:
        from erenshor.shared.game_constants import LONG_NAME_FONT_SIZE, LONG_NAME_THRESHOLD

        print(f"✓ LONG_NAME_THRESHOLD = {LONG_NAME_THRESHOLD}")
        print(f"✓ LONG_NAME_FONT_SIZE = '{LONG_NAME_FONT_SIZE}'")

        if LONG_NAME_THRESHOLD == 24 and LONG_NAME_FONT_SIZE == "20px":
            print("✓ Constants have expected values")
            return True
        print("❌ Constants have unexpected values")
        return False

    except ImportError as e:
        print(f"❌ Failed to import constants: {e}")
        return False


def test_enrichment_modules():
    """Test that enrichment modules exist and can be imported."""
    print("\n" + "=" * 60)
    print("Testing Enrichment Modules")
    print("=" * 60)

    success = True

    try:
        from erenshor.application.generators.item_type_display import build_item_types

        print("✓ item_type_display module imported")
        print("  - build_item_types function available")
    except ImportError as e:
        print(f"❌ Failed to import item_type_display: {e}")
        success = False

    try:
        from erenshor.application.generators.proc_extractor import ProcExtractor

        print("✓ proc_extractor module imported")
        print("  - ProcExtractor class available")
    except ImportError as e:
        print(f"❌ Failed to import proc_extractor: {e}")
        success = False

    return success


def main():
    """Run all enrichment tests."""
    print("\n" + "=" * 60)
    print("ENRICHMENT FEATURE TEST SUITE")
    print("=" * 60)

    results = []

    # Test schema changes
    results.append(("Database Schema", test_database_schema()))

    # Test constants
    results.append(("Enrichment Constants", test_enrichment_constants()))

    # Test modules
    results.append(("Enrichment Modules", test_enrichment_modules()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠ Some tests failed. See details above.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
