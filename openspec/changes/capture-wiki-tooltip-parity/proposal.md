## Why

The wiki copies game tooltip facts, but no whole-build check compares its rendered text with the game's own windows. A game update or template edit can change thousands of tooltips without a reliable warning.

## What Changes

- Capture the TextMeshPro fields that the game writes for every item, spell, skill, and reachable stance. Keep the raw text as build-specific evidence.
- Parse game markup into ordered lines and typed tones. Reject unknown tags instead of losing their meaning.
- Render every matching wiki tooltip in an isolated local MediaWiki stack with the same build's generated modules and articles. Compare text and tone by stable key and line.
- List the three intentional differences from `adopt-data-backed-wiki` design D14: equipment quality cards, damage over time shown as `/ 3 sec`, and the wiki's fixed Base DPS formula. Explicitly exclude other player-dependent lines from comparison.
- Stop any deploy that writes a tooltip input when current-build coverage is incomplete or an unexplained difference remains. Tooltip inputs are generated articles, generated data modules, and maintained tooltip modules and templates. Produce a report that names each entity and line.

## Capabilities

### New Capabilities

- `wiki-tooltip-parity`: build-specific game tooltip evidence, exhaustive local comparison, and the gate on every deploy of a tooltip input.

### Modified Capabilities

None. The tooltip presentation and hover behavior in the active `wiki-publishing` plan remain unchanged.

## Impact

- Python CLI, HotRepl collection script, wiki comparison code, local MediaWiki importer, deploy precondition, and focused tests.
- Evidence and reports under `variants/<variant>/wiki/`, outside repository-owned wiki page sources.
- No production wiki read or write is needed for comparison. Existing dry runs, render checks, and guarded writes remain in place.
- No new native mod or third-party dependency is required. This change does not implement the article conversion or reproduce Unity's pixel layout.
