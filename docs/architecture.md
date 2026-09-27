# Data pipeline architecture

The pipeline turns the installed game into one clean SQLite database per
variant. Every published output reads that database.

```text
Steam client installation (CrossOver bottle, found by Steam app ID)
  → extract rip         AssetRipper Unity project   variants/{v}/unity
  → extract export      Unity batch export          variants/{v}/erenshor-{v}-raw.sqlite
  → extract code-facts  constants from the shipped Assembly-CSharp.dll, into the raw DB
  → extract build       Python processor + mapping.json
                        → variants/{v}/erenshor-{v}.sqlite (clean DB)
  → wiki, sheets, maps, guide   read the clean DB
```

## Layers

**Raw export.** The Unity Editor scripts in `src/Assets/Editor/` scan the
AssetRipper project and write tables that mirror the Unity assets. They do not
merge, rename, or filter. See `skill://unity-export-system`.

**Code facts.** `src/tools/CodeFacts/` reads hardcoded constants from the
shipped assembly and writes them into the raw database. `extract build` fails
when these tables are missing. See `skill://code-facts`.

**Clean build.** `src/erenshor/application/processor/build.py` reads the raw
database and `mapping.json` and writes the clean database. It applies display
name overrides, excludes entities, deduplicates characters, and computes
derived columns. The clean schema uses snake_case tables and columns and is
defined in `src/erenshor/application/processor/writer.py`.

**Consumers.** The wiki generators, the Google Sheets queries, the interactive
map, and the quest guide compiler read only the clean database. None of them
reads the raw database or the Unity project.

## Regression baselines

`uv run erenshor golden capture` writes snapshots of published output to
`tests/golden/`: CSV files for the sheets, the map spawn points, and the code
facts, and a sample of generated wiki pages. A diff there after a data change
shows what the change did to published output.
