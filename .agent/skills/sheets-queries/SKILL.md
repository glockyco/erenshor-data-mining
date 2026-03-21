---
name: sheets-queries
description: Google Sheets SQL queries and deployment. Use when adding or modifying sheets queries.
---

# Adding New Google Sheets Queries

Sheets are generated from SQL queries against the SQLite database.

## Steps

1. **Create SQL file**: `src/erenshor/application/sheets/queries/my-sheet.sql`

```sql
SELECT
    i.ItemName AS "Item Name",
    i.ItemLevel AS "Level",
    i.Value AS "Value"
FROM Items i
WHERE i.IsEnabled = 1
ORDER BY i.ItemName
```

2. **Deploy**: `uv run erenshor sheets deploy --sheets my-sheet`

## Query Guidelines

- First row becomes header (use column aliases for display names)
- Results are written directly to the sheet tab
- Tab name matches filename (my-sheet.sql → "my-sheet" tab)
- Use JOINs for related data across tables

## Available Tables

Core tables in the SQLite database:
- Items, Characters, Spells, Skills
- Quests, SpawnPoints, LootTables
- Coordinates, Factions, Zones

Junction tables for relationships:
- CharacterAttackSpells, CharacterBuffSpells
- QuestRequiredItems, QuestRewards
- ItemClasses, SpellClasses
- SpawnPointCharacters

## Existing Queries

Located in `src/erenshor/application/sheets/queries/`:
- items.sql, characters.sql, spells.sql, skills.sql
- drop-chances.sql, spawn-points.sql
- And 15+ more

## Commands

```bash
uv run erenshor sheets list              # List available sheets
uv run erenshor sheets deploy --all-sheets  # Deploy all sheets
uv run erenshor sheets deploy --sheets X # Deploy specific sheet
uv run erenshor sheets deploy --dry-run  # Preview without writing
```
