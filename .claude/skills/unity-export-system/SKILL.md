---
name: unity-export-system
description: Understand the Unity data export system architecture. Use when working with asset scanners, listeners, database records, or the C# export code.
---

# Unity Export System

The export system scans Unity assets and writes to SQLite.

## Architecture

```
AssetScanner
├── Scans Unity project for assets
├── Notifies registered listeners
└── Listeners write to SQLite

ExportBatch.cs (entry point)
├── Opens SQLite connection
├── Registers all listeners
├── Triggers asset scan
└── Closes connection
```

## Core Components

**Location**: `src/Assets/Editor/ExportSystem/`

| File | Purpose |
|------|---------|
| ExportBatch.cs | Batch mode entry point |
| AssetScanner.cs | Scans assets, notifies listeners |
| Repository.cs | Database operations |

## Listeners

Each listener extracts specific game data. Located in
`src/Assets/Editor/ExportSystem/AssetScanner/Listener/`:

**Core entities**:
- ItemListener.cs - Items and equipment
- CharacterListener.cs - NPCs and creatures
- SpellListener.cs - Spells and abilities
- SkillListener.cs - Skills and professions

**Game systems**:
- QuestListener.cs - Quest data
- SpawnPointListener.cs - Enemy spawn locations
- LootTableListener.cs - Drop tables
- TeleportLocListener.cs - Teleport locations

**Other**:
- ItemBagListener.cs, BookListener.cs, AchievementTriggerListener.cs
- AscensionListener.cs, ClassListener.cs, WorldFactionListener.cs
- And 15+ more...

## Database Records

Record classes define SQLite table schemas. Located in
`src/Assets/Editor/Database/`:

- ItemRecord.cs, CharacterRecord.cs, SpellRecord.cs, SkillRecord.cs
- QuestRecord.cs, SpawnPointRecord.cs, LootTableRecord.cs
- CoordinateRecord.cs (shared location data)
- 40+ total record classes

## Junction Tables

Many-to-many relationships use junction tables:

- CharacterAttackSpells, CharacterBuffSpells - Character abilities
- QuestRequiredItems, QuestRewards - Quest relationships
- ItemClasses, SpellClasses - Class restrictions
- SpawnPointCharacters, SpawnPointPatrolPoints - Spawn mechanics

**Total**: 20,600+ normalized rows across all junction tables.

## StableKey System

Entities use stable keys for consistent identification:

```csharp
// Items: "item:resource_name"
StableKeyGenerator.ForItem(item)

// Characters (prefab): "character:object_name"
// Characters (placed): "character:object_name|scene|x|y|z"
StableKeyGenerator.ForCharacter(character)

// Spells: "spell:resource_name"
StableKeyGenerator.ForSpell(spell)
```

## Running Exports

```bash
# Full export via CLI
uv run erenshor extract export

# Or via Unity batch mode directly
Unity -batchmode -projectPath variants/main/unity \
  -executeMethod ExportBatch.Run -logFile export.log -quit
```
