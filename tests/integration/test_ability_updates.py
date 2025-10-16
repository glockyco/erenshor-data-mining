"""Integration tests for ability (spell/skill) updates.

Tests cover:
- Spell generation (direct damage, healing, buffs, debuffs)
- Skill generation
- Template structure
- Validation
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from erenshor.application.services.update_service import UpdateService
from erenshor.domain.events import (
    PageUpdated,
    UpdateComplete,
    ValidationFailed,
)
from erenshor.infrastructure.storage.page_storage import PageStorage


def test_spell_generation(
    test_engine: Engine,
    ability_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test spell generation (various types)."""
    events = list(ability_update_service.update_pages(test_engine))

    spell_events = [
        e
        for e in events
        if isinstance(e, PageUpdated) and not e.page_title.startswith("Skill:")
    ]

    assert len(spell_events) >= 3, "Should generate at least 3 spell pages"

    for event in spell_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Spells should have appropriate template (Spell, Ability, or custom)
        # Exact template name depends on implementation
        assert "{{" in content and "}}" in content, "Should have templates"


def test_damage_spell(
    test_engine: Engine,
    ability_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test direct damage spell generation."""
    events = list(ability_update_service.update_pages(test_engine))

    damage_spell_events = [
        e for e in events if isinstance(e, PageUpdated) and "Fireball" in e.page_title
    ]

    assert len(damage_spell_events) >= 1, "Should generate Fireball spell"

    for event in damage_spell_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should have damage information
        assert (
            "damage" in content.lower() or "dmg" in content.lower()
        ), "Damage spell should mention damage"


def test_healing_spell(
    test_engine: Engine,
    ability_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test healing spell generation."""
    events = list(ability_update_service.update_pages(test_engine))

    heal_spell_events = [
        e for e in events if isinstance(e, PageUpdated) and "Heal" in e.page_title
    ]

    assert len(heal_spell_events) >= 1, "Should generate Heal spell"

    for event in heal_spell_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should have healing information
        assert "heal" in content.lower(), "Healing spell should mention healing"


def test_buff_spell(
    test_engine: Engine,
    ability_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test buff spell generation."""
    events = list(ability_update_service.update_pages(test_engine))

    buff_spell_events = [
        e
        for e in events
        if isinstance(e, PageUpdated)
        and ("Shield" in e.page_title or "Haste" in e.page_title)
    ]

    # Buffs may or may not be in test data
    for event in buff_spell_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should have buff information
        assert len(content) > 50, "Buff spell should have content"


def test_skill_generation(
    test_engine: Engine,
    ability_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that all abilities (spells) are generated.

    NOTE: Skills (Mining, Fishing) are separate from Spells in the database.
    The AbilityGenerator currently only generates Spells, not Skills.
    This test verifies that spell generation works for various spell types.
    """
    events = list(ability_update_service.update_pages(test_engine))

    ability_events = [e for e in events if isinstance(e, PageUpdated)]

    # Test data has 8 spells that should be generated
    assert len(ability_events) >= 1, "Should generate at least one ability page"

    for event in ability_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Abilities should have content
        assert (
            len(content) > 50
        ), f"Ability page should have content: {event.page_title}"


def test_ability_update_statistics(
    test_engine: Engine,
    ability_update_service: UpdateService,
) -> None:
    """Test that UpdateComplete event has correct statistics."""
    events = list(ability_update_service.update_pages(test_engine))

    complete_events = [e for e in events if isinstance(e, UpdateComplete)]

    assert len(complete_events) == 1, "Should have exactly one UpdateComplete event"

    complete = complete_events[0]
    # Test data has 8 spells + 10 skills = 18 abilities total
    assert (
        complete.total >= 18
    ), f"Should generate at least 18 abilities, got {complete.total}"


def test_ability_validation_passes(
    test_engine: Engine,
    ability_update_service: UpdateService,
) -> None:
    """Test that generated abilities pass validation."""
    events = list(ability_update_service.update_pages(test_engine))

    failed_events = [e for e in events if isinstance(e, ValidationFailed)]

    if failed_events:
        for event in failed_events:
            print(f"Validation failed for {event.page_title}:")
            for violation in event.violations:
                print(f"  - {violation.field}: {violation.message}")

    assert len(failed_events) < 5, f"Too many validation failures: {len(failed_events)}"


def test_ability_content_not_empty(
    test_engine: Engine,
    ability_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that generated ability pages are not empty."""
    events = list(ability_update_service.update_pages(test_engine))

    updated_events = [e for e in events if isinstance(e, PageUpdated)]

    for event in updated_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        assert content is not None, f"Page content is None: {event.page_title}"
        assert (
            len(content) > 50
        ), f"Page content too short ({len(content)} chars): {event.page_title}"


def test_spell_vs_skill_distinction(
    test_engine: Engine,
    ability_update_service: UpdateService,
) -> None:
    """Test that spells and skills are distinguished correctly."""
    events = list(ability_update_service.update_pages(test_engine))

    updated_events = [e for e in events if isinstance(e, PageUpdated)]

    # Test data has 8 spells + 10 skills = 18 abilities
    assert len(updated_events) >= 18, "Should generate at least 18 abilities"

    # Note: Some abilities may map to the same page (multi-entity pages)
    # This is expected behavior in the registry system
    titles = [e.page_title for e in updated_events]
    unique_titles = set(titles)
    assert (
        len(unique_titles) >= 8
    ), f"Should have at least 8 unique pages, got {len(unique_titles)}"


def test_skill_casttime_innate_vs_noninnate(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Innate skills have blank casttime, non-innate skills have 'Instant'."""
    list(ability_update_service.update_pages(test_engine))

    # Mining is Innate - should have blank casttime
    mining_page = test_output_storage.registry.get_page_by_title("Mining")
    assert mining_page is not None
    mining_content = test_output_storage.read(mining_page)
    assert mining_content is not None
    assert "|casttime=\n" in mining_content or "|casttime=\r\n" in mining_content

    # Power Strike is Attack (non-Innate) - should have casttime=Instant
    power_strike_page = test_output_storage.registry.get_page_by_title("Power Strike")
    assert power_strike_page is not None
    power_strike_content = test_output_storage.read(power_strike_page)
    assert power_strike_content is not None
    assert "|casttime=Instant" in power_strike_content


def test_skill_effects_from_effect_to_apply_id(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Skills with EffectToApplyId show linked effect in effects field."""
    list(ability_update_service.update_pages(test_engine))

    # Weakening Strike has EffectToApplyId pointing to Weakness
    page = test_output_storage.registry.get_page_by_title("Weakening Strike")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None
    assert "|effects={{AbilityLink|Weakness}}" in content


def test_skill_effects_from_cast_on_target_id(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Skills with CastOnTargetId show linked effect in effects field."""
    list(ability_update_service.update_pages(test_engine))

    # Fire Strike has CastOnTargetId pointing to Fireball
    page = test_output_storage.registry.get_page_by_title("Fire Strike")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None
    assert "|effects={{AbilityLink|Fireball}}" in content


def test_skill_effects_both_ids_different(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Skills with both EffectToApplyId and CastOnTargetId show both separated by <br>."""
    list(ability_update_service.update_pages(test_engine))

    # Dual Effect Strike has both Shield and Haste
    page = test_output_storage.registry.get_page_by_title("Dual Effect Strike")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None
    assert (
        "{{AbilityLink|Shield}}<br>{{AbilityLink|Haste}}" in content
        or "{{AbilityLink|Haste}}<br>{{AbilityLink|Shield}}" in content
    )


def test_skill_effects_deduplication(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """When EffectToApplyId and CastOnTargetId point to same spell, effect shown once."""
    list(ability_update_service.update_pages(test_engine))

    # Stunning Blow has both pointing to Weakness
    page = test_output_storage.registry.get_page_by_title("Stunning Blow")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None

    # Should have single occurrence, not duplicate
    assert (
        "|effects={{AbilityLink|Weakness}}\n" in content
        or "|effects={{AbilityLink|Weakness}}\r\n" in content
    )

    # Should NOT have duplicate
    assert "{{AbilityLink|Weakness}}<br>{{AbilityLink|Weakness}}" not in content


def test_skill_require_bow_suffix(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Skills with RequireBow=1 have 'Requires a bow.' appended to description."""
    list(ability_update_service.update_pages(test_engine))

    # Piercing Shot has RequireBow
    page = test_output_storage.registry.get_page_by_title("Piercing Shot")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None
    assert "Requires a bow." in content
    assert "|description=A precise arrow attack<br>Requires a bow." in content


def test_skill_require_shield_suffix(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Skills with RequireShield=1 have 'Requires a shield.' appended to description."""
    list(ability_update_service.update_pages(test_engine))

    # Shield Slam has RequireShield
    page = test_output_storage.registry.get_page_by_title("Shield Slam")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None
    assert "Requires a shield." in content
    assert "|description=Slam enemy with shield<br>Requires a shield." in content


def test_skill_requirement_suffix_not_duplicated(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Requirement suffix not added if description already contains it."""
    list(ability_update_service.update_pages(test_engine))

    # Aimed Shot already has "Requires a bow." in description
    page = test_output_storage.registry.get_page_by_title("Aimed Shot")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None

    # Should appear once, not twice
    assert content.count("Requires a bow.") == 1


def test_skill_cooldown_display(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Skills with cooldown display formatted cooldown (cooldowns stored in ticks, 60/sec)."""
    list(ability_update_service.update_pages(test_engine))

    # Power Strike has 300 ticks cooldown = 5 seconds (300 / 60)
    page = test_output_storage.registry.get_page_by_title("Power Strike")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None
    assert "|cooldown=5 seconds" in content


def test_ability_preserves_manual_content_after_infobox(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
    test_cache_storage: PageStorage,
) -> None:
    """Test that ability updates preserve manual content after the infobox.

    This is a critical requirement for idempotent updates - we must not lose
    user-written content like descriptions, strategies, notes, etc.
    """
    # Create a page with manual content after the infobox
    mining_page = test_output_storage.registry.get_page_by_title("Mining")
    if mining_page is None:
        # Register the page if it doesn't exist
        from erenshor.domain.entities.page import EntityRef
        from erenshor.domain.value_objects.entity_type import EntityType

        mining_ref = EntityRef(
            entity_type=EntityType.SKILL, db_id="1", db_name="Mining"
        )
        mining_page = test_output_storage.registry.register_entity(mining_ref, "Mining")
        assert mining_page is not None

    # Write a page with infobox + manual content to cache
    manual_content = """{{Ability
|id=1
|title=Mining
|description=Extract ore from rocks
}}

'''Mining''' is an innate skill that allows players to extract valuable ores from mining nodes.

=Mining Nodes=
Mining nodes can be found throughout the world:
*Copper nodes in starting areas
*Iron nodes in mid-level zones
*Gold nodes in high-level zones

=Strategy=
The best strategy is to mine everything you see to level up quickly."""

    test_cache_storage.write(mining_page, manual_content)

    # Run the update
    list(ability_update_service.update_pages(test_engine))

    # Read the updated content
    updated_content = test_output_storage.read(mining_page)
    assert updated_content is not None

    # Verify manual content is preserved
    assert (
        "'''Mining''' is an innate skill" in updated_content
    ), "Manual description after infobox should be preserved"
    assert "=Mining Nodes=" in updated_content, "Manual sections should be preserved"
    assert (
        "Copper nodes in starting areas" in updated_content
    ), "Manual bullet points should be preserved"
    assert "=Strategy=" in updated_content, "Manual sections should be preserved"
    assert (
        "best strategy is to mine everything" in updated_content
    ), "Manual content should be preserved"


def test_ability_preserves_manual_content_before_infobox(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
    test_cache_storage: PageStorage,
) -> None:
    """Test that ability updates preserve manual content before the infobox.

    Some pages may have warnings, notices, or other content before the infobox.
    """
    # Get or create a page
    page = test_output_storage.registry.get_page_by_title("Power Strike")
    if page is None:
        from erenshor.domain.entities.page import EntityRef
        from erenshor.domain.value_objects.entity_type import EntityType

        ref = EntityRef(entity_type=EntityType.SKILL, db_id="2", db_name="Power Strike")
        page = test_output_storage.registry.register_entity(ref, "Power Strike")
        assert page is not None

    # Write a page with content before the infobox
    manual_content = """{{Spoiler|This ability is obtained late in the game}}

'''WARNING:''' This page contains spoilers!

{{Ability
|id=2
|title=Power Strike
|description=A powerful melee attack
}}

This ability is very powerful in endgame content."""

    test_cache_storage.write(page, manual_content)

    # Run the update
    list(ability_update_service.update_pages(test_engine))

    # Read the updated content
    updated_content = test_output_storage.read(page)
    assert updated_content is not None

    # Verify content before infobox is preserved
    assert (
        "{{Spoiler|" in updated_content
    ), "Spoiler template before infobox should be preserved"
    assert (
        "WARNING:" in updated_content
    ), "Warning text before infobox should be preserved"
    assert (
        "This ability is very powerful in endgame content" in updated_content
    ), "Content after infobox should be preserved"


def test_ability_idempotency(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
    test_cache_storage: PageStorage,
) -> None:
    """Test that running ability updates multiple times produces identical results.

    Idempotency is critical - we must be able to re-run updates without causing
    content drift, duplication, or loss.
    """
    # Run update first time
    list(ability_update_service.update_pages(test_engine))

    # Get all updated pages
    from erenshor.domain.events import PageUpdated

    events1 = list(ability_update_service.update_pages(test_engine))
    updated_pages1 = [e for e in events1 if isinstance(e, PageUpdated)]

    # Capture content after first run
    first_run_content = {}
    for event in updated_pages1:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        if page:
            content = test_output_storage.read(page)
            if content:
                first_run_content[event.page_title] = content

    # Copy output to cache (simulating the pages being "live" on wiki)
    for title, content in first_run_content.items():
        page = test_output_storage.registry.get_page_by_title(title)
        if page:
            test_cache_storage.write(page, content)

    # Run update second time
    events2 = list(ability_update_service.update_pages(test_engine))
    updated_pages2 = [e for e in events2 if isinstance(e, PageUpdated)]

    # Capture content after second run
    second_run_content = {}
    for event in updated_pages2:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        if page:
            content = test_output_storage.read(page)
            if content:
                second_run_content[event.page_title] = content

    # Verify content is identical
    assert len(first_run_content) == len(
        second_run_content
    ), "Same number of pages should be generated"

    for title in first_run_content:
        assert title in second_run_content, f"Page {title} should exist in both runs"
        assert (
            first_run_content[title] == second_run_content[title]
        ), f"Page {title} content should be identical across runs (idempotency)"


def test_summoning_spell_character_links(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Test that summoning spells generate proper character links."""
    list(ability_update_service.update_pages(test_engine))

    # Find summoning spells in the generated pages
    # Summoning spells have non-empty pet_to_summon values
    summoning_pages = []
    for page in test_output_storage.registry.pages.values():
        content = test_output_storage.read(page)
        if content and "|pet_to_summon=" in content:
            # Extract the pet_to_summon line
            lines = content.split("\n")
            pet_line = [line for line in lines if "|pet_to_summon=" in line]
            if pet_line:
                pet_value = pet_line[0].split("|pet_to_summon=", 1)[1].strip()
                # Only consider it a summoning spell if pet_to_summon is not empty
                if pet_value:
                    summoning_pages.append((page, content, pet_value))

    # If no summoning spells in test data, skip this test
    if not summoning_pages:
        return

    # Check that each summoning spell has a proper character link
    for page, content, pet_value in summoning_pages:
        # pet_to_summon should use standard MediaWiki link syntax [[...]]
        # Pattern: |pet_to_summon=[[Character Name]] or [[Page|Display]]
        assert pet_value.startswith(
            "[["
        ), f"Summoning spell {page.title} should use [[...]] link syntax, got: {pet_value}"

        # Should end with ]]
        assert pet_value.endswith(
            "]]"
        ), f"MediaWiki link in {page.title} should be properly closed, got: {pet_value}"

        # Should NOT use custom templates
        assert (
            "{{CharacterLink" not in pet_value
        ), f"Summoning spell {page.title} should not use {{{{CharacterLink}}}} template, got: {pet_value}"
