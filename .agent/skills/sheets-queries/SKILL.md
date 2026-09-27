---
name: sheets-queries
description: Authoring SQL query files that build Google Sheets tabs from the clean SQLite DB, and deploying them. Use when adding, editing, or deploying a sheet query under src/erenshor/application/sheets/queries/.
---

# Adding New Google Sheets Queries

Sheets are generated from SQL queries against the SQLite database.

## Steps

1. **Create SQL file**: `src/erenshor/application/sheets/queries/my-sheet.sql`

```sql
SELECT
    i.display_name AS 'Item Name',
    i.item_level AS 'Level',
    i.item_value AS 'Value'
FROM items i
ORDER BY i.display_name;
```

2. **Deploy**: `uv run erenshor sheets deploy --sheets my-sheet`

## Query Guidelines

- First row becomes header (use column aliases for display names)
- Results are written directly to the sheet tab
- Tab name matches filename (my-sheet.sql → "my-sheet" tab)
- Use JOINs for related data across tables

## Available Tables

The clean database uses snake_case tables and columns, such as `items`,
`characters`, `spells`, `zones`, `loot_drops`, and `map_character_spawns`.
List the tables and columns from the database instead of from memory:

```bash
sqlite3 variants/main/erenshor-main.sqlite ".tables"
sqlite3 variants/main/erenshor-main.sqlite "PRAGMA table_info(items);"
```

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
uv run erenshor --dry-run sheets deploy --all-sheets  # Preview without writing
```
