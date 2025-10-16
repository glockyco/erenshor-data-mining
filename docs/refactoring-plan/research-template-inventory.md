# Template Inventory Research

## Executive Summary

This document provides a comprehensive audit of the current wiki template system for the Erenshor project. The system uses Jinja2 templates to generate MediaWiki template invocations for different entity types.

**Key Findings:**
- 20 Jinja2 template files across 4 entity categories
- 7 generators producing wiki content
- Item subtypes have specialized templates (weapons, armor, charms, auras, molds, ability books, consumables, general)
- Spells and skills share the same `{{Ability}}` template
- Characters use a single `{{Enemy}}` template for both NPCs and enemies
- Fishing data uses specialized table templates

---

## Current Template Inventory

### Items Category

Items have the most complex template structure with 8 subtypes, each using different templates:

#### 1. General Items
- **Template File:** `items/item.j2`
- **Wiki Template:** `{{Item}}`
- **Generator:** `GeneralItemGenerator.generate_general_block()`
- **Used For:** Fallback for items that don't fit other categories
- **Fields:** All standard item fields (26 fields)
  - title, image, imagecaption, type
  - vendorsource, source, othersource, questsource, relatedquest
  - craftsource, componentfor, relic, classes
  - effects, damage, delay, dps, casttime, duration, cooldown
  - description, buy, sell, itemid
  - crafting, recipe

#### 2. Weapons
- **Template Files:**
  - `items/item.j2` - Item infobox (sources only)
  - `items/fancy_weapon_template.j2` - Individual tier template
  - `items/fancy_weapon_table.j2` - 3-tier table
- **Wiki Templates:**
  - `{{Item}}` - Source fields only
  - `{{Fancy-weapon}}` - Individual tier with stats (34 fields)
  - Fancy-weapon table - 3 tiers side-by-side
- **Generator:** `WeaponArmorGenerator.generate_weapon_blocks()`
- **Special Features:**
  - Three quality tiers: Normal, Blessed, Godly
  - Proc support (proc_name, proc_desc, proc_chance, proc_style)
  - Class restrictions with checkboxes
  - Damage, delay, and stat modifiers
  - Relic flag
- **Fancy-weapon Fields:**
  - image, name, type, relic, tier
  - str, end, dex, agi, int, wis, cha, res
  - damage, delay, health, mana
  - armor, magic, poison, elemental, void
  - description
  - arcanist, duelist, druid, paladin, stormcaller (class flags)
  - proc_name, proc_desc, proc_chance, proc_style

#### 3. Armor
- **Template Files:**
  - `items/item.j2` - Item infobox (sources only)
  - `items/fancy_armor_template.j2` - Individual tier template
  - `items/fancy_armor_table.j2` - 3-tier table
- **Wiki Templates:**
  - `{{Item}}` - Source fields only
  - `{{Fancy-armor}}` - Individual tier with stats (33 fields)
  - Fancy-armor table - 3 tiers side-by-side
- **Generator:** `WeaponArmorGenerator.generate_armor_blocks()`
- **Special Features:**
  - Three quality tiers: Normal, Blessed, Godly
  - Slot specification (Head, Chest, Legs, etc.)
  - Proc support (same as weapons)
  - Class restrictions with checkboxes
  - Stat modifiers only (no damage/delay)
  - Relic flag
- **Fancy-armor Fields:**
  - image, name, type, slot, relic, tier
  - str, end, dex, agi, int, wis, cha, res
  - health, mana, armor, magic, poison, elemental, void
  - description
  - arcanist, duelist, druid, paladin, stormcaller (class flags)
  - proc_name, proc_desc, proc_chance, proc_style

#### 4. Charms
- **Template Files:**
  - `items/item.j2` - Item infobox (sources only)
  - `items/fancy_charm.j2` - Charm template with scaling stats
- **Wiki Templates:**
  - `{{Item}}` - Source fields only
  - `{{Fancy-charm}}` - Charm display (17 fields)
- **Generator:** `CharmGenerator.generate_charm_blocks()`
- **Special Features:**
  - Stat scaling values (strscaling, endscaling, etc.)
  - Class restrictions
  - No quality tiers (uses first tier's scaling)
- **Fancy-charm Fields:**
  - image, name, description
  - strscaling, endscaling, dexscaling, agiscaling, intscaling, wisscaling, chascaling
  - arcanist, duelist, druid, paladin, stormcaller (class flags)

#### 5. Auras
- **Template File:** `items/item.j2`
- **Wiki Template:** `{{Item}}`
- **Generator:** `AuraGenerator.generate_aura_block()`
- **Special Features:**
  - Uses standard Item template
  - Type field set to "[[Auras|Aura]]"
  - Effects field links to aura spell
  - No quality tiers

#### 6. Ability Books (Spell/Skill Books)
- **Template File:** `items/ability_book.j2`
- **Wiki Template:** `{{Ability Books}}`
- **Generator:** `AbilityBookGenerator.generate_ability_book_block()`
- **Fields (17 fields):**
  - title, image, imagecaption, type, spelltype
  - classes, effects, manacost, description
  - buy, sell, vendorsource, source, othersource
  - componentfor, itemid
  - questsource, relatedquest, craftsource (not in template but in context)
- **Special Features:**
  - Links to learned spell/skill in effects field
  - Shows mana cost for spells (empty for skills)
  - Shows class requirements with level requirements

#### 7. Molds (Crafting Recipe Items)
- **Template File:** `items/mold.j2`
- **Wiki Template:** `{{Mold}}`
- **Generator:** `MoldGenerator.generate_mold_block()`
- **Fields (11 fields):**
  - title, buy, sell, vendorsource, source, description
  - questsource, relatedquest, crafting, recipe
  - (additional: itemid in context but not template)
- **Special Features:**
  - Simplified template for recipe items
  - Shows what can be crafted and recipe ingredients
  - No stats or equipment fields

#### 8. Consumables
- **Template File:** `items/item.j2`
- **Wiki Template:** `{{Item}}`
- **Generator:** `ConsumableGenerator.generate_consumable_block()`
- **Special Features:**
  - Uses standard Item template
  - Effects field links to spell/buff granted
  - Type field shows "[[Consumables|Consumable]]"

#### 9. Mold Sources (Section Template)
- **Template File:** `items/mold_sources.j2`
- **Wiki Template:** Wikitext section (not a template)
- **Generator:** Used by item generators for source lists
- **Purpose:** Generates "; Sources" section with bullet points

---

### Abilities Category

Spells and skills share the same template structure but use different generators:

#### Spells & Skills (Shared Template)
- **Template File:** `abilities/ability.j2`
- **Wiki Template:** `{{Ability}}`
- **Generators:**
  - `SpellGenerator.generate()` for spells
  - `SkillGenerator.generate()` for skills
- **Fields (69 fields):**
  - **Basic:** id, title, image, imagecaption, description
  - **Classification:** type, line, classes, required_level
  - **Costs:** manacost, aggro, is_taunt
  - **Timing:** casttime, cooldown, duration, duration_in_ticks, has_unstable_duration
  - **Mechanics:** is_instant_effect, is_reap_and_renew, is_sim_usable
  - **Targeting:** range, max_level_target, is_self_only, is_group_effect, is_applied_to_caster
  - **Effects:** effects, damage_type, resist_modifier
  - **Combat:** target_damage, target_healing, caster_healing, shield_amount
  - **Summons:** pet_to_summon
  - **Status:** status_effect, add_proc, add_proc_chance
  - **Life/Mana:** has_lifetap, lifesteal, damage_shield, percent_mana_restoration
  - **Bleed:** bleed_damage_percent
  - **Special:** special_descriptor
  - **Stats:** hp, ac, mana, str, dex, end, agi, wis, int, cha
  - **Resists:** mr, er, vr, pr
  - **Buffs:** haste, resonance, movement_speed, atk_roll_modifier, xp_bonus
  - **CC:** is_root, is_stun, is_charm, is_broken_on_damage
  - **Sources:** itemswitheffect, source
- **Special Features:**
  - Extremely comprehensive template (largest in the system)
  - Handles both offensive and defensive abilities
  - Supports buffs, debuffs, healing, damage, summons, crowd control
  - Class restrictions with level requirements
  - Duration mechanics with ticks and instability flags

---

### Characters Category

#### NPCs and Enemies (Unified Template)
- **Template File:** `characters/enemy.j2`
- **Wiki Template:** `{{Enemy}}`
- **Generator:** `CharacterGenerator.generate()`
- **Fields (30 fields):**
  - name, image, imagecaption, type, faction, factionChange
  - zones, coordinates, spawnchance, respawn
  - guaranteeddrops, droprates
  - level, experience, health, mana, ac
  - strength, endurance, dexterity, agility, intelligence, wisdom, charisma
  - magic, poison, elemental, void
- **Special Features:**
  - Single template for both NPCs and enemies
  - Type field shows: "[[:Category:Characters|NPC]]", "[[Enemies|Boss]]", "[[Enemies|Rare]]", "[[Enemies|Enemy]]"
  - Faction modifiers for reputation changes
  - Spawn information (chance, respawn time, coordinates)
  - Loot tables (guaranteed and chance-based drops)
  - Full stat blocks with base stats
  - Resist ranges (e.g., "10-15" for variable resists)

#### Character (Unused Template)
- **Template File:** `characters/character.j2`
- **Wiki Template:** `{{Character}}`
- **Status:** Currently unused (Enemy template used for all characters)
- **Fields (9 fields):**
  - name, image, type, faction, zones, level, experience
- **Note:** Simplified version that appears to be deprecated

---

### Fishing Category

#### Fishing Tables
- **Template File:** `fishing/table.j2`
- **Wiki Template:** Wikitext table (not a template)
- **Generator:** Not actively used (superseded by canonical)
- **Purpose:** Zone-specific fishing table with day/night rates
- **Fields:** name, day_rate, night_rate

#### Fishing Canonical (Active)
- **Template File:** `fishing/canonical.j2`
- **Wiki Template:** Full page content (not a template)
- **Generator:** `FishingGenerator.generate()`
- **Structure:** Multiple zone sections, each with its own table
- **Fields per row:** name, rate
- **Special Features:**
  - Generates complete "Fishing" page
  - Groups fish by zone
  - Shows catch rates as percentages

---

### Auras Category

#### Aura Overview Table
- **Template File:** `auras/table.j2`
- **Wiki Template:** Wikitext table (not a template)
- **Generator:** Used by overview/list generators
- **Purpose:** Table listing all aura items
- **Fields per row:** item, buff, stats, classes
- **Note:** This is for overview pages, not individual aura pages

---

## Overview Pages

### Weapons Overview
- **Generator:** `OverviewGenerator._generate_weapons_page()`
- **Output:** Wikitext table (not using template file)
- **Features:**
  - Sortable datatable with 23 columns
  - Shows all weapon stats at a glance
  - Includes slot, type, level, damage, delay
  - Shows all stat modifiers
  - Notes column for procs and special effects
  - Class restrictions

### Armor Overview
- **Generator:** `OverviewGenerator._generate_armor_page()`
- **Output:** Wikitext table (not using template file)
- **Features:**
  - Sortable datatable with 21 columns
  - Shows all armor stats at a glance
  - Includes slot, level
  - Shows all stat modifiers and resists
  - Notes column for worn effects and procs
  - Class restrictions

---

## Template Usage Matrix

| Entity Type | Subtype | Template File | Wiki Template | Block ID Pattern | Generator |
|-------------|---------|---------------|---------------|------------------|-----------|
| Item | Weapon | `items/item.j2` | `{{Item}}` | `{ResourceName}` | WeaponArmorGenerator |
| Item | Weapon | `items/fancy_weapon_template.j2` | `{{Fancy-weapon}}` | `{ResourceName}:Normal/Blessed/Godly` | WeaponArmorGenerator |
| Item | Weapon | `items/fancy_weapon_table.j2` | Table | `{ResourceName}` | WeaponArmorGenerator |
| Item | Armor | `items/item.j2` | `{{Item}}` | `{ResourceName}` | WeaponArmorGenerator |
| Item | Armor | `items/fancy_armor_template.j2` | `{{Fancy-armor}}` | `{ResourceName}:Normal/Blessed/Godly` | WeaponArmorGenerator |
| Item | Armor | `items/fancy_armor_table.j2` | Table | `{ResourceName}` | WeaponArmorGenerator |
| Item | Charm | `items/item.j2` | `{{Item}}` | `{ResourceName}` | CharmGenerator |
| Item | Charm | `items/fancy_charm.j2` | `{{Fancy-charm}}` | `{ResourceName}` | CharmGenerator |
| Item | Aura | `items/item.j2` | `{{Item}}` | `{ResourceName}` | AuraGenerator |
| Item | Ability Book | `items/ability_book.j2` | `{{Ability Books}}` | `{ResourceName}` | AbilityBookGenerator |
| Item | Mold | `items/mold.j2` | `{{Mold}}` | `{ResourceName}` | MoldGenerator |
| Item | Consumable | `items/item.j2` | `{{Item}}` | `{ResourceName}` | ConsumableGenerator |
| Item | General | `items/item.j2` | `{{Item}}` | `{ResourceName}` | GeneralItemGenerator |
| Spell | All | `abilities/ability.j2` | `{{Ability}}` | `{ResourceName}` | SpellGenerator |
| Skill | All | `abilities/ability.j2` | `{{Ability}}` | `{ResourceName}` | SkillGenerator |
| Character | NPC/Enemy | `characters/enemy.j2` | `{{Enemy}}` | `{StableId}` | CharacterGenerator |
| Overview | Fishing | `fishing/canonical.j2` | Page content | `fishing_canonical` | FishingGenerator |
| Overview | Weapons | None (generated) | Wikitext table | `weapons_overview` | OverviewGenerator |
| Overview | Armor | None (generated) | Wikitext table | `armor_overview` | OverviewGenerator |

---

## Future Templates Needed

Based on database schema analysis, the following entity types exist but don't have generators/templates yet:

### High Priority

#### 1. Quests
- **Database Tables:** `Quests`, `QuestRequiredItems`, `QuestRewards`, `QuestZoneAssignments`, `QuestZoneCompletions`, `QuestCompleteOtherQuests`, `QuestFactionAffects`
- **Suggested Template:** `{{Quest}}`
- **Template File:** `quests/quest.j2`
- **Key Fields:**
  - title, image, type, level, zone
  - giver, turn_in (NPCs)
  - description, objectives
  - prerequisites (required quests)
  - required_items (with quantities)
  - rewards (items, gold, experience, faction)
  - follow_up_quests
  - completion_requirements (zone completions, other quests)
- **Complexity:** High (multiple junction tables)

#### 2. Factions
- **Database Tables:** `Factions`, `QuestFactionAffects`
- **Suggested Template:** `{{Faction}}`
- **Template File:** `factions/faction.j2`
- **Key Fields:**
  - name, description
  - alignment (good/evil/neutral)
  - how_to_gain_reputation
  - reputation_rewards
  - associated_npcs
  - associated_zones
- **Complexity:** Medium

#### 3. Zones
- **Database Tables:** `ZoneAnnounces`, `ZoneAtlasEntries`, `ZoneLines`
- **Suggested Template:** `{{Zone}}`
- **Template File:** `zones/zone.j2`
- **Key Fields:**
  - name, image, level_range
  - description, lore
  - npcs_in_zone
  - enemies_in_zone
  - quests_in_zone
  - resources (mining, fishing, etc.)
  - zone_lines (connections)
  - atlas_info
- **Complexity:** Medium-High

### Medium Priority

#### 4. Classes
- **Database Table:** `Classes`
- **Suggested Template:** `{{Class}}`
- **Template File:** `classes/class.j2`
- **Key Fields:**
  - name, description, role
  - primary_stats, secondary_stats
  - available_spells (by level)
  - available_skills (by level)
  - equipment_restrictions
  - playstyle_notes
- **Complexity:** Medium (needs to aggregate spells/skills)

#### 5. Mining Nodes
- **Database Tables:** `MiningNodes`, `MiningNodeItems`
- **Suggested Template:** `{{Mining Node}}`
- **Template File:** `mining/node.j2`
- **Key Fields:**
  - name, type, level_required
  - zones, locations
  - items (with drop rates)
  - respawn_time
- **Complexity:** Low-Medium

#### 6. Crafting Recipes
- **Database Tables:** `CraftingRecipes`, `CraftingRewards`
- **Suggested Template:** `{{Recipe}}`
- **Template File:** `crafting/recipe.j2`
- **Key Fields:**
  - name, mold_required
  - ingredients (with quantities)
  - results (with quantities)
  - station_required
- **Complexity:** Low-Medium

### Low Priority

#### 7. Achievements
- **Database Table:** `AchievementTriggers`
- **Suggested Template:** `{{Achievement}}`
- **Template File:** `achievements/achievement.j2`
- **Key Fields:**
  - name, description, category
  - requirements, progress_tracking
  - rewards
- **Complexity:** Low

#### 8. Teleports
- **Database Table:** `Teleports`
- **Suggested Template:** `{{Teleport}}`
- **Template File:** `teleports/teleport.j2`
- **Key Fields:**
  - name, source_zone, destination_zone
  - coordinates, requirements
  - type (portal, NPC, spell)
- **Complexity:** Low

#### 9. Doors
- **Database Table:** `Doors`
- **Suggested Template:** `{{Door}}`
- **Template File:** `doors/door.j2`
- **Key Fields:**
  - name, zone, coordinates
  - key_required, lock_difficulty
  - connects_to
- **Complexity:** Low

#### 10. Books
- **Database Table:** `Books`
- **Suggested Template:** `{{Book}}`
- **Template File:** `books/book.j2`
- **Key Fields:**
  - title, author, text
  - location, how_to_obtain
  - lore_category
- **Complexity:** Low

---

## Implementation Recommendations

### 1. Template Architecture Improvements

**Problem:** Inconsistent handling of subtypes across entity types.

**Recommendations:**
- **Create base templates for shared field sets:**
  - `items/base_infobox.j2` - Common item fields (sources, buy/sell, etc.)
  - `abilities/base_ability.j2` - Common ability fields
  - Use Jinja2 `{% include %}` or `{% extends %}` for DRY
  
- **Standardize subtype handling:**
  - Use consistent naming: `{entity}/{subtype}.j2`
  - Document subtype selection logic clearly
  - Consider enum-based subtype classification

### 2. Template Context Improvements

**Problem:** Template contexts are defined in `infrastructure/templates/contexts/*.py` but there's some duplication.

**Recommendations:**
- **Create base context classes:**
  - `ItemInfoboxBaseContext` with common item fields
  - `AbilityInfoboxBaseContext` with common ability fields
  - Use dataclass inheritance for subtypes
  
- **Validate context fields:**
  - Add runtime validation for required fields
  - Add type hints for all context fields
  - Consider using Pydantic for validation

### 3. Generator Architecture Improvements

**Problem:** Generators have inconsistent patterns for handling subtypes.

**Recommendations:**
- **Standardize generator structure:**
  - All generators should inherit from `BaseGenerator`
  - Implement `generate()` method that yields `GeneratedContent`
  - Use `_matches_filter()` for consistent filtering
  
- **Extract subtype routing:**
  - Create `ItemGeneratorRouter` to delegate to subtype generators
  - Use strategy pattern for subtype selection
  - Make it easy to add new subtypes without modifying existing code

### 4. Template Discovery and Registration

**Problem:** Templates are hardcoded in generator code.

**Recommendations:**
- **Create template registry:**
  - Map entity types and subtypes to template files
  - Enable template lookup by key
  - Support template inheritance/fallbacks
  
- **Template metadata:**
  - Document required context fields
  - Document wiki template name
  - Document example usage

### 5. Future Template System

**For Quest templates:**
- **Complexity:** Quests have many relationships (items, NPCs, zones, prerequisites)
- **Recommendation:** 
  - Create specialized context builders
  - Use async/cached lookups for related entities
  - Consider split templates (quest infobox + quest chain visualization)

**For Zone templates:**
- **Complexity:** Zones aggregate many entities (NPCs, enemies, quests, resources)
- **Recommendation:**
  - Generate multiple blocks (infobox + entity tables)
  - Use overview table templates for entity lists
  - Consider paginating large zone content

### 6. Testing Strategy

**Problem:** No template testing infrastructure.

**Recommendations:**
- **Add template tests:**
  - Test each template with sample context
  - Validate generated wikitext structure
  - Check for missing/extra fields
  
- **Add generator tests:**
  - Test subtype classification logic
  - Test context building logic
  - Test multi-block generation

### 7. Documentation Strategy

**Problem:** Template field meanings are not documented centrally.

**Recommendations:**
- **Create template field reference:**
  - Document each field's purpose
  - Show example values
  - Note which fields are required vs optional
  
- **Create template style guide:**
  - Document naming conventions
  - Document formatting rules
  - Show common patterns

---

## Current System Strengths

1. **Clean separation:** Templates, contexts, generators are clearly separated
2. **Type safety:** Context objects use dataclasses with type hints
3. **Extensibility:** Easy to add new generators for new entity types
4. **Jinja2 filters:** Custom filters for duration, percent, etc.
5. **Streaming:** Generators yield one entity at a time for progress tracking

## Current System Weaknesses

1. **No template inheritance:** Lots of duplication in template files
2. **Hardcoded routing:** Subtype selection logic scattered across generators
3. **No validation:** Missing field validation for contexts
4. **No tests:** Templates and generators lack comprehensive tests
5. **Limited documentation:** Field meanings not documented
6. **Mixed responsibilities:** Some generators build wikitext directly instead of using templates

---

## Appendix: Template Field Reference

### Item Template Fields

```
{{Item
|title=                  # Display name
|image=                  # [[File:name.png]]
|imagecaption=           # Optional caption
|type=                   # Item category with wiki links
|vendorsource=           # Vendor NPCs (line-separated)
|source=                 # Drop sources (line-separated)
|othersource=            # Fishing, mining, etc (line-separated)
|questsource=            # Quest rewards (line-separated)
|relatedquest=           # Related quests (line-separated)
|craftsource=            # Crafting sources (line-separated)
|componentfor=           # Used in recipes (line-separated)
|relic=                  # True if relic, else empty
|classes=                # Class restrictions (comma-separated)
|effects=                # Click/worn effects (wiki links)
|damage=                 # Base damage
|delay=                  # Attack delay
|dps=                    # Damage per second
|casttime=               # Cast time
|duration=               # Effect duration
|cooldown=               # Cooldown time
|description=            # Lore text
|buy=                    # Buy price
|sell=                   # Sell price
|itemid=                 # Database ID
|crafting=               # Crafted results (line-separated)
|recipe=                 # Recipe ingredients (line-separated)
}}
```

### Fancy-weapon Template Fields

```
{{Fancy-weapon
| image =                # [[File:name.png|80px]]
| name =                 # Display name (may have font-size span)
| type =                 # Weapon type display
| relic =                # True if relic, else empty
| str =                  # Strength bonus (0 shown as empty)
| end =                  # Endurance bonus
| dex =                  # Dexterity bonus
| agi =                  # Agility bonus
| int =                  # Intelligence bonus
| wis =                  # Wisdom bonus
| cha =                  # Charisma bonus
| res =                  # Resonance bonus
| damage =               # Weapon damage
| delay =                # Attack delay (2 decimal places)
| health =               # Health bonus
| mana =                 # Mana bonus
| armor =                # Armor class bonus
| magic =                # Magic resist bonus
| poison =               # Poison resist bonus
| elemental =            # Elemental resist bonus
| void =                 # Void resist bonus
| description =          # Lore text
| arcanist =             # True if Arcanist can use
| duelist =              # True if Duelist can use
| druid =                # True if Druid can use
| paladin =              # True if Paladin can use
| stormcaller =          # True if Stormcaller can use
| proc_name =            # Proc ability name (wiki link)
| proc_desc =            # Proc description
| proc_chance =          # Proc chance percentage
| proc_style =           # Proc trigger ("on attack", "on cast", etc)
| tier =                 # Normal / Blessed / Godly
}}
```

### Ability Template Fields

```
{{Ability
|id=                     # Database ID
|title=                  # Display name
|image=                  # [[File:name.png|thumb]]
|imagecaption=           # Status message ("You are...")
|description=            # Ability description
|type=                   # Spell type (Offensive, Defensive, etc)
|line=                   # Spell line (e.g., "Fire Line")
|classes=                # Classes that can learn (line-separated with levels)
|required_level=         # Minimum level
|manacost=               # Mana cost
|aggro=                  # Aggro generated
|is_taunt=               # True if taunt, else empty
|casttime=               # Cast time ("Instant" or "X seconds")
|cooldown=               # Cooldown duration
|duration=               # Effect duration
|duration_in_ticks=      # Duration in ticks
|has_unstable_duration=  # True if varies, else empty
|is_instant_effect=      # True if instant, else empty
|is_reap_and_renew=      # True if special mechanic
|is_sim_usable=          # True if usable in sim, else empty
|range=                  # Spell range
|max_level_target=       # Max target level
|is_self_only=           # True if self-cast only
|is_group_effect=        # True if affects group
|is_applied_to_caster=   # True if buff applies to caster
|effects=                # Linked effects (skills only)
|damage_type=            # Damage type (Physical, Magic, etc)
|resist_modifier=        # Resist modifier
|target_damage=          # Damage amount
|target_healing=         # Healing amount
|caster_healing=         # Caster heal amount
|shield_amount=          # Shield/absorb amount
|pet_to_summon=          # Summoned pet name (wiki link)
|status_effect=          # Status effect name (wiki link)
|add_proc=               # Added proc ability (wiki link)
|add_proc_chance=        # Proc chance
|has_lifetap=            # True if lifetap
|lifesteal=              # Lifesteal percentage
|damage_shield=          # Damage shield amount
|percent_mana_restoration= # Mana restore percentage
|bleed_damage_percent=   # Bleed damage percentage
|special_descriptor=     # Special notes
|hp=                     # Health modifier
|ac=                     # Armor class modifier
|mana=                   # Mana modifier
|str=                    # Strength modifier
|dex=                    # Dexterity modifier
|end=                    # Endurance modifier
|agi=                    # Agility modifier
|wis=                    # Wisdom modifier
|int=                    # Intelligence modifier
|cha=                    # Charisma modifier
|mr=                     # Magic resist modifier
|er=                     # Elemental resist modifier
|vr=                     # Void resist modifier
|pr=                     # Poison resist modifier
|haste=                  # Haste percentage
|resonance=              # Resonance chance
|movement_speed=         # Movement speed modifier
|atk_roll_modifier=      # Attack roll modifier
|xp_bonus=               # XP bonus percentage
|is_root=                # True if roots target
|is_stun=                # True if stuns target
|is_charm=               # True if charms target
|is_broken_on_damage=    # True if breaks on damage
|itemswitheffect=        # Items with this effect (line-separated)
|source=                 # How to learn (line-separated)
}}
```

### Enemy Template Fields

```
{{Enemy
|name=                   # Display name
|image=                  # [[File:name.png|thumb]]
|imagecaption=           # Optional caption
|type=                   # NPC / Enemy / Boss / Rare
|faction=                # Faction name (wiki link)
|factionChange=          # Faction modifiers on kill (line-separated)
|zones=                  # Zones where found (line-separated)
|coordinates=            # X x Y x Z coordinates
|spawnchance=            # Spawn chance percentage
|respawn=                # Respawn time
|guaranteeddrops=        # 100% drop items (line-separated)
|droprates=              # Chance-based drops (line-separated)
|level=                  # Level
|experience=             # XP reward (min-max or single)
|health=                 # Base health
|mana=                   # Base mana
|ac=                     # Armor class
|strength=               # Strength stat
|endurance=              # Endurance stat
|dexterity=              # Dexterity stat
|agility=                # Agility stat
|intelligence=           # Intelligence stat
|wisdom=                 # Wisdom stat
|charisma=               # Charisma stat
|magic=                  # Magic resist (may be range)
|poison=                 # Poison resist (may be range)
|elemental=              # Elemental resist (may be range)
|void=                   # Void resist (may be range)
}}
```

---

## Conclusion

The Erenshor template system is well-structured with clear separation of concerns. The main areas for improvement are:

1. Reduce template duplication through inheritance
2. Add validation for context fields
3. Standardize subtype routing logic
4. Add comprehensive tests
5. Document template fields and conventions
6. Plan for future entity types (quests, zones, factions)

The system is ready to scale to additional entity types with some refactoring to reduce duplication and improve maintainability.
