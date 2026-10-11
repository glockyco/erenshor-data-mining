# Tasks

## 1. Game data and code facts

- [ ] 1.1 `feat(export): export the Chessboard's item fields`: add a `ChessboardListener` in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/` and a record under `src/Assets/Editor/Database/` that write one raw row per `Item` field of each `Chessboard` component: scene, field name, and item stable key. Follow `skill://unity-export-system`. Verify: the export of the main variant has rows for `Candlekeeper` (A Strange Figurine) and `ReplaceStatue`, and the export surface check passes.
- [ ] 1.2 `feat(tools): pin the Candlekeeper, Time Stone, and Flame Well rules`: add `assert` facts to `src/tools/CodeFacts/specs/erenshor-facts.json` for the Candlekeeper branch of `Chessboard` (consumes the figurine, adds `ReplaceStatue`), the Time Stone scene branch of `SpellVessel` (item ID and both scene names, stone returned), the `CheckOfferingStones` stone IDs, success rule, and quality results, and the `Braxonian Flame Well` call site in `TradeWindow`. Follow `skill://code-facts`. Verify: `uv run erenshor extract code-facts` binds every new fact on the current main build, and changing one literal in a test fixture fails it.

## 2. Clean database

- [ ] 2.1 `feat(pipeline): record runtime item mechanics in the clean database`: add `src/erenshor/application/processor/item_mechanics.py` and the four tables of design D3 in `writer.py`, and call it from `build.py`. Tag each consumer constant with its fact ID, including `fishing.map_bonus`. Raise on a missing fact, an unresolved item ID, a missing Chessboard field, or a `Maps` pool shorter than four. Add unit tests for each table's rows and for each failure. Verify: the tests pass and `test_code_facts_coverage.py` passes.
- [ ] 2.2 Run export, code facts, and the clean build for the main variant. Verify against the clean database: the scenarios of the `runtime-item-mechanics` spec hold, and `extract changes` lists the new facts as `ok`.

## 3. Documentation and close-out

- [ ] 3.1 `docs(wiki): point Cargo item sources and uses at the new tables`: in `publish-wiki-cargo-data`, add the four tables to the `ItemSources` and `ItemUses` sources of design D4, with the Reliquary Flame Well condition, and mark task 6.2 of `adopt-data-backed-wiki` done with the result. Verify: `openspec validate --strict` passes for both changes.
- [ ] 3.2 Archive this change. Verify: `openspec/specs/runtime-item-mechanics/spec.md` exists and `uv run erenshor test ci` passes.
