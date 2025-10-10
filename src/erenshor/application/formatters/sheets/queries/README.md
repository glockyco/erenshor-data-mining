# SQL Query Files

This directory contains SQL queries for Google Sheets export, with one file per sheet.

## Structure

Each `.sql` file corresponds to a Google Sheets tab:
- Filename = sheet name (e.g., `items.sql` → "Items" sheet)
- Contains only the SQL query (no special formatting needed)
- All queries execute against the SQLite database

## Usage

The `SheetsFormatter` class reads these files dynamically:

```python
from erenshor.application.formatters.sheets import SheetsFormatter

formatter = SheetsFormatter(engine, queries_dir)
rows = formatter.format_sheet("items")  # Reads items.sql
```

## Available Queries

1. `drop-chances.sql` - NPC loot drop probabilities
2. `items.sql` - All items with stats
3. `item-bags.sql` - Loot bag locations
4. `characters.sql` - NPCs and creatures
5. `character-dialogs.sql` - NPC dialog trees
6. `classes.sql` - Player classes
7. `spells.sql` - Spell data
8. `skills.sql` - Skill data
9. `ascensions.sql` - Ascension abilities
10. `quests.sql` - Quest information
11. `books.sql` - In-game books
12. `factions.sql` - Faction data
13. `zones.sql` - Zone information
14. `teleports.sql` - Teleport locations
15. `treasure-locations.sql` - Treasure hunting spots
16. `wishing-wells.sql` - Wishing well locations
17. `fishing.sql` - Fishing spots and drops
18. `mining-nodes.sql` - Mining node locations
19. `spawn-points.sql` - NPC spawn points
20. `secret-passages.sql` - Secret passage locations
21. `achievement-triggers.sql` - Achievement trigger locations

## Adding New Queries

1. Create a new `.sql` file with the sheet name
2. Add the SQL query (must start with `SELECT` or `WITH`)
3. The query will be automatically available in `SheetsFormatter`
