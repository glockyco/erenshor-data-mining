---
name: auditing-spawn-coverage
description: Classify new scripted spawn fields after export exit 3, then audit orphan characters and mapping exclusions after a game update.
---

# Audit spawn coverage

Run this after `skill://refreshing-game-data` exports a new build. The export gate classifies serialized character-prefab fields. A successful export does not prove that every runtime spawn has a known position.

## Resolve an export gate failure

1. Run `uv run erenshor -V {v} extract export`. On exit 3, read `variants/{v}/.export/dynamic-spawn-errors.json`.
2. For each `findings[]` entry, inspect its `script_type`, `field_name`, and resolved `example_prefab_path`. Read the corresponding shipped script in the ripped `Assembly-CSharp` tree. Verify how the field is used, not only its name.
3. Classify each `(script_type, field_name)` in `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml`. Allow a field when its instantiated prefab carries a `Character` component and its position is resolvable. Set `position_field` or an existing `position_strategy` when host position is wrong. Deny UI, effects, and runtime-rebound references with a specific `reason`.
4. Remove each `stale_entries[]` entry whose script no longer exists in the shipped assembly. Review renamed scripts before deleting their coverage.
5. Rerun export. Exit 0 clears the old error envelope. Do not continue with an exit-3 raw database.

The listener scans public instance fields of Assembly-CSharp `MonoBehaviour` instances. It reports an unknown field only when its serialized value resolves to a Character prefab. `SpawnPoint` and `SpawnPointTrigger` use separate listeners. Chained prefab spawns use `CharacterChainedSpawns`, which the clean build expands into spawn rows. The gate does not identify zone-tick scripts or runtime-generated positions.

## Audit after the clean build

1. Run `uv run python src/tools/audit_spawn_coverage.py --variant {v} --include-disabled`. Compare its orphan count and categories with the prior reviewed build. Its query excludes characters covered by a dedup sibling, a summoning spell, or a possible treasure-chest spawn.
2. Run `uv run python src/tools/audit_mapping_exclusions.py --variant {v} --only-content`. Investigate excluded characters that still have loot, dialog, or vendor content.
   Its last section lists each excluded prefab without a spawn whose object name a placed character carries under another name. A built scene keeps no link to the prefab of a placed character, so such a prefab looks unused. When a wiki page names the prefab, record a rename or a split in `content-lifecycle.json` (`skill://wiki-templates`). The check finds only copies that keep the prefab's object name. A copy whose object was renamed as well, such as `Character_Ghost_01 (1)` placed as `Ghostly Figure`, needs `trace_character_sources.py`.
3. Run `uv run python src/tools/trace_character_sources.py --variant {v} --stable-key '<character-key>'` for each unexplained orphan. Check asset GUID references and the decompiled scripts for a field alias. A differently named field can reference the missing prefab.
4. Review each `mapping.json` decision. Keep a character with loot on the wiki even if its position cannot be mapped. Do not treat `is_enabled=0` as proof that a spawn is unreachable. Exclude an entity only after checking its asset references and scripted use.
5. Do not publish sheets, wiki, or map while a new unexplained orphan remains. Record each newly understood runtime-only or dead prefab with the correct visibility decision.

`trace_character_sources.py` finds references in `.unity` and `.prefab` files, not C# instantiation sites. Check the catalog and scripts separately. `skill://unity-export-system` covers listener and record changes.
