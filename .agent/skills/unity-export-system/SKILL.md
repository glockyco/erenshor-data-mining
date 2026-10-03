---
name: unity-export-system
description: Add or repair a Unity asset export listener and its raw SQLite records when a game update changes the exported asset surface.
---

# Change a Unity export

The Unity batch export scans ripped assets and writes raw SQLite tables. Follow `skill://refreshing-game-data` for the complete update order.

## Add or change an exported field

1. Inspect the shipped field and its existing listener in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/`. Change the existing record in `src/Assets/Editor/Database/` when it already owns the entity.
2. Classify the field in `src/tools/ExportSurface/field-coverage.json`. A captured field needs matching listener extraction. An ignored field needs a reason that reflects its actual use.
3. Run `uv run erenshor -V {v} extract export`. The pre-export coverage check compares the manifest, shipped DLL, and listener types before Unity compiles. Fix its reported fields instead of bypassing it.
4. Run `uv run erenshor -V {v} extract code-facts` and `uv run erenshor -V {v} extract build` when the clean database must include the new export. Update the processor and writer if the raw schema changes.

## Add a new asset type

1. Follow a comparable record and listener in `src/Assets/Editor/Database/` and `src/Assets/Editor/ExportSystem/AssetScanner/Listener/`. Give the record a `[Table]` name, stable primary key, and fields that correspond to the exported data.
2. Implement `IAssetScanListener<T>` for the Unity type. Clear old rows, collect records in `OnAssetFound`, and insert the collected rows in `OnScanFinished`. Follow the comparable listener's transaction and foreign-key order.
3. Register the listener once in `src/Assets/Editor/ExportSystem/ExportListenerRegistry.cs`. Choose Null, GameObject, Component, or ScriptableObject registration according to its scan type. Declare its dependencies before the dependent listener and keep registration in dependency order. Do not add a second registry to `ExportBatch.cs`.
4. Add the scanned type and captured or ignored fields to `src/tools/ExportSurface/field-coverage.json`. Then run the export and clean-build commands above. Inspect the raw and clean rows, not only the command exit status.

Use `StableKeyGenerator` for entity keys. Do not join entities by display name. For scripted character spawns, classify the `(script, field)` pair in `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml` instead of inventing a placed `SpawnPoint`. Follow `skill://auditing-spawn-coverage` for exit 3 and orphan review.

## Resolve export failures

- If `extract rip` refuses missing Editor dependencies, run `uv run erenshor extract packages`. Add new NuGet dependencies to `src/Assets/packages.config` and restore them. Newtonsoft.Json instead comes from the UPM package injected by rip. Do not put a duplicate DLL under `src/Assets/Packages`.
- If the field-coverage gate fails, inspect `src/tools/ExportSurface/field-coverage.json` and the listener named in the error. A removed or retyped shipped field requires a source change, not only a manifest edit.
- If Unity reports a licensing failure, open Unity Hub and retry export after the license is ready.
- If export exits 3, use the dynamic-spawn error envelope. Do not run the clean build on this failed raw export.
