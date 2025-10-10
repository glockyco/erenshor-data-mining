# Google Sheets Formatters

This package provides formatters for exporting Erenshor game data to Google Sheets.

## Components

### SheetsFormatter
**File:** `items.py`

Executes SQL queries from individual `.sql` files and formats results for Google Sheets API.

**Query Files:** Each sheet has its own `.sql` file in the `queries/` directory.

```python
from erenshor.application.formatters.sheets import SheetsFormatter
from sqlalchemy import create_engine
from pathlib import Path

engine = create_engine("sqlite:///variants/main/erenshor-main.sqlite")
queries_dir = Path("src/erenshor/application/formatters/sheets/queries")
formatter = SheetsFormatter(engine, queries_dir)

# Format single sheet (reads queries/items.sql)
rows = formatter.format_sheet("items")
# Returns:
# [
#   ["ID", "Name", "Level", ...],  # Header
#   ["item_1", "Sword", 10, ...],  # Data rows
#   ...
# ]

# Get all available sheets
sheet_names = formatter.get_sheet_names()
# Returns: ['achievement-triggers', 'ascensions', 'books', 'characters', ...]

# Format all sheets
all_data = formatter.format_all_sheets()
# Returns: {"items": [...], "characters": [...], ...}

# Get row count
count = formatter.get_row_count("items")
# Returns: 1234 (excluding header)
```

## Data Type Handling

The formatter automatically converts database values for Google Sheets:

| Database Type | Google Sheets Value |
|---------------|-------------------|
| `None` | `""` (empty string) |
| `True` | `"TRUE"` |
| `False` | `"FALSE"` |
| `int`, `float` | Preserved as-is |
| `str` | Preserved as-is |

## Available Sheets

The `queries/` directory contains 21 SQL query files:

1. `drop-chances` - NPC loot drop probabilities
2. `items` - All items with stats
3. `item-bags` - Loot bag locations
4. `characters` - NPCs and creatures
5. `character-dialogs` - NPC dialog trees
6. `classes` - Player classes
7. `spells` - Spell data
8. `skills` - Skill data
9. `ascensions` - Ascension abilities
10. `quests` - Quest information
11. `books` - In-game books
12. `factions` - Faction data
13. `zones` - Zone information
14. `teleports` - Teleport locations
15. `treasure-locations` - Treasure hunting spots
16. `wishing-wells` - Wishing well locations
17. `fishing` - Fishing spots and drops
18. `mining-nodes` - Mining node locations
19. `spawn-points` - NPC spawn points
20. `secret-passages` - Secret passage locations
21. `achievement-triggers` - Achievement trigger locations

## Query File Structure

Each `.sql` file in `queries/` contains a single SQL query:
- Filename = sheet name (e.g., `items.sql` → "items" sheet)
- No special formatting required
- Just the SQL query text

**Example:** `queries/items.sql`
```sql
SELECT
    ItemDBIndex,
    Id,
    ItemName,
    -- ... more columns
FROM items i
LEFT JOIN ItemStats s ON s.ItemId = i.Id
ORDER BY i.ItemDBIndex;
```

## Usage with SheetsDeployService

Typically, you won't use these formatters directly. Instead, use the `SheetsDeployService`:

```python
from erenshor.application.services import SheetsDeployService
from erenshor.infrastructure.publishers import GoogleSheetsPublisher

service = SheetsDeployService(
    engine=engine,
    queries_dir=Path("src/erenshor/application/formatters/sheets/queries"),
    publisher=GoogleSheetsPublisher(...),
)

result = service.deploy_all(
    spreadsheet_id="...",
    sheet_names=["items", "characters"],
)
```

See [Google Sheets Deployment Guide](../../../../docs/GOOGLE_SHEETS_DEPLOYMENT.md) for complete documentation.
