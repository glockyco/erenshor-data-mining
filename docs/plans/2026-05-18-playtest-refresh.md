# Playtest Refresh After Raid/Zone Update

**Date:** 2026-05-18
**Variant:** `playtest`
**Scope:** Refresh playtest data end-to-end after the latest Steam update (raid content + new zones), republish variant-scoped outputs (Google Sheets), bring the playtest map up locally, and grow the tile-capture roster to include any new zones.

**Out of scope:**
- Wiki publish — the wiki is a single shared target (`erenshor.wiki.gg`); a `wiki deploy --variant playtest` would overwrite main's pages.
- AdventureGuide compile / Thunderstore publish — no new quest content reported in this playtest bump.
- Map deploy to Cloudflare — local only.
- Main variant — Steam touched `variants/main/game/` today but the asset roster is unchanged from before; main hasn't received this content.

## State at plan-write time

| Path | mtime | Notes |
|---|---|---|
| `variants/playtest/game/Erenshor_Data` | May 17 | Fresh from Steam |
| `variants/playtest/unity/ExportedProject` | Feb 1 | **Stale** — AssetRipper must re-run |
| `variants/playtest/erenshor-playtest.sqlite` | Mar 7 | **Stale** — clean DB |
| `variants/playtest/erenshor-playtest-raw.sqlite` | — | **Missing** — raw DB has never existed for this variant |

Asset delta vs main: **+8 levels, +4 sharedassets bundles** → consistent with the new raid zones.

## Order of work

Each numbered item is one concept and one commit unless noted. Run from repo root.

### Phase 1 — Rebuild playtest data

#### 1. Re-rip the playtest Unity projec
```bash
uv run erenshor extract rip --variant playtes
```
- Wipes `variants/playtest/unity/`, runs AssetRipper against the May-17 game files, recreates the `Assets/Editor` symlink and copies `Packages/`.
- **Acceptance:** `variants/playtest/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/` exists with a recent mtime; `variants/playtest/unity/ExportedProject/Assets/Editor` is a symlink to `src/Assets/Editor`.
- **No commit** — outputs are gitignored.

#### 2. Unity batch-mode export → raw SQLite
```bash
uv run erenshor extract export --variant playtes
```
- Writes `variants/playtest/erenshor-playtest-raw.sqlite`.
- **Acceptance:** raw DB exists; `sqlite3 variants/playtest/erenshor-playtest-raw.sqlite ".tables"` shows the full table list.
- **No commit.**

#### 3. Python build → clean SQLite
```bash
uv run erenshor extract build --variant playtes
```
- Watch the build log for `mapping.json` warnings about new characters/items lacking overrides.
- Watch for any schema errors (raid content may introduce new fields on `Characters` / `Spells` / `Quests`).
- **Acceptance:** clean DB written; build exits 0; warning list captured for the next step.
- **No commit yet** — outputs are gitignored.

#### 4. Address any new entities needing `mapping.json` rules
If step 3 produced warnings about new NPCs/items lacking overrides, add the minimum necessary rules to `mapping.json` (default to `wiki_page_name = null`, `is_wiki_generated = 0` only when the entity is genuinely internal — see existing rules in `mapping.json` lines 39–47 for the pattern). Re-run step 3 until clean.

- **Commit:** `chore(mapping): add overrides for playtest raid entities` (only if mapping changed).

#### 5. Fix any processor / schema regressions
If step 3 surfaced exceptions (missing column, type mismatch, listener crash), fix at the source:
- New Unity field → add to the matching `IAssetScanListener` and database record under `src/Assets/Editor/`, then re-rip-export-build.
- New processor case → fix in `src/erenshor/application/processor/`.

- **Commit:** atomic per concept. `feat(export): ...` or `fix(pipeline): ...`.

#### 6. Refresh golden baselines
```bash
uv run pytest tests/integration -v -k playtes
uv run erenshor golden capture --variant playtes
git diff tests/golden/
```
Review the diff — separate "expected data changes from playtest update" from any accidental regressions.

- **Commit:** `chore(tests): refresh playtest golden baselines for v<X> raid update` (one commit; reference the changelog if available).

### Phase 2 — Republish playtest Google Sheets

#### 7. Dry-run sheets deploy
```bash
uv run erenshor sheets deploy --variant playtest --dry-run
```
Inspect the planned sheet writes. Confirm the spreadsheet target is `1gRgoCSXVRcbAbLNa7_FD5CMN9Z0PQA-mInSLeW1cRGE` (playtest spreadsheet from `config.toml`), **not** the main one.

#### 8. Actual sheets deploy
```bash
uv run erenshor sheets deploy --variant playtes
```
- **Acceptance:** all sheets succeed; open the spreadsheet, spot-check the rows for one new raid NPC and one new zone.
- **No commit** — output is the remote spreadsheet.

### Phase 3 — Local playtest map

#### 9. Add `[variants.playtest.maps]` to `config.toml`
Mirror main's section but with a distinct `deploy_target` so a future accidental `maps deploy` requires an explicit second change in `wrangler.jsonc` before it can ship.

```toml
[variants.playtest.maps]
source_dir = "$REPO_ROOT/src/maps"
data_dir = "$REPO_ROOT/src/maps/static/data"
database_dir = "$REPO_ROOT/src/maps/static/db"
build_dir = "$REPO_ROOT/src/maps/build-playtest"
deploy_target = "erenshor-maps-playtest"
```

Notes:
- `build_dir` is separate (`build-playtest/`) so main and playtest builds don't stomp each other.
- `data_dir` / `database_dir` / `source_dir` are shared with main by design — `maps build` swaps the DB symlink per variant; tiles + JSON data files are variant-agnostic until proven otherwise.

- **Commit:** `feat(config): add maps section for playtest variant`.

#### 10. Local map build + serve
```bash
uv run erenshor maps build --variant playtes
uv run erenshor maps dev --variant playtes
# or: uv run erenshor maps preview --variant playtes
```
- `maps build` swaps `src/maps/static/db/erenshor.sqlite` → `variants/playtest/erenshor-playtest.sqlite` before the SvelteKit build.
- **Acceptance:** dev server starts, a known new raid NPC appears at a sane location, zones list includes any new playtest zones (those will appear as broken-tile entries until Phase 4 lands).
- **Restore the main symlink** after this session: `uv run erenshor maps build --variant main` (no deploy needed) so day-to-day work on main still works.

### Phase 4 — Tile capture for new playtest zones

#### 11. Compute the new-zone delta
```bash
uv run python -c "
import json, sqlite3
db = sqlite3.connect('variants/playtest/erenshor-playtest.sqlite')
playtest_scenes = {r[0] for r in db.execute('SELECT DISTINCT scene_name FROM zones WHERE scene_name IS NOT NULL')}
configured = set(json.load(open('src/maps/src/lib/data/zone-capture-config.json')).keys())
new = sorted(playtest_scenes - configured)
print(f'{len(new)} new zones:')
for z in new:
    print(f'  - {z}')
"
```
If the delta is empty, **skip the rest of Phase 4**; no new tiles are needed.

#### 12. Deploy MapTileCapture mod to playtes
```bash
uv run erenshor mod deploy --mod MapTileCapture --variant playtes
```
- One-time per session, before launching playtest.

#### 13. For each new zone — bounds discovery via HotRepl
With playtest game running and the mod loaded:

```bash
# Switch scene
uv run erenshor eval run 'SceneManager.LoadScene("<NewZone>");'
sleep 4

# Bounds discovery — full snippet in skill://tile-capture
uv run erenshor eval run '
var scene = SceneManager.GetActiveScene();
var bounds = new Bounds(); bool first = true; int n = 0;
foreach (var go in scene.GetRootGameObjects())
    foreach (var r in go.GetComponentsInChildren<MeshRenderer>()) {
        var s = r.bounds.size;
        if (s.x > 200 || s.z > 200) continue;
        if (first) { bounds = r.bounds; first = false; } else bounds.Encapsulate(r.bounds);
        n++;
    }
string.Format("n={0} minX={1:F2} maxX={2:F2} minZ={3:F2} maxZ={4:F2}",
    n, bounds.min.x, bounds.max.x, bounds.min.z, bounds.max.z)
'
```

Compute, per `skill://tile-capture`:
- `baseTilesX = ceil(width / 256)`, `baseTilesY = ceil(depth / 256)`
- `originX = centerX - baseTilesX * 128`
- `originY = centerZ - baseTilesY * 128`

#### 14. Add config entries + display names
For each new zone, append to `src/maps/src/lib/data/zone-capture-config.json`:
```json
"<NewZone>": {
    "sceneName": "<NewZone>",
    "baseTilesX": <X>,
    "baseTilesY": <Y>,
    "tileSize": 256,
    "maxZoom": 1,  // start conservative; bump after capture+budget check
    "originX": <X>,
    "originY": <Y>,
    "northBearing": null,
    "captureVariants": ["clear"],
    "exclusionRules": [],
    "usingSun": <true|false>  // outdoor=true, indoor=false
}
```

Add the display name in `src/maps/src/lib/maps.ts` under `DISPLAY_NAMES`.

#### 15. Capture + verify per zone
```bash
uv run erenshor capture run --variant playtest --zones <NewZone>
# Verify content is centred in the master (snippet from skill://tile-capture)
# If clipped or off-centre, adjust origin/baseTiles and re-run.
```

If exclusion rules are needed (rooftops or oversized props inflate bounds), iterate using `capture tile --zones <NewZone>` (no game needed for re-tile).

#### 16. Thumbnails + per-zone commi
```bash
uv run erenshor maps dev --variant playtest &  # in background
uv run erenshor maps thumbnails --variant playtest --zones <NewZone> --url http://localhost:5173
```

- **Commit:** `feat(map): capture <NewZone> tiles` per zone (keeps history readable if multiple new zones).
  - Includes: `zone-capture-config.json` entry, `maps.ts` display name, the new `src/maps/static/tiles/<NewZone>/**` tiles, and the thumbnail.

#### 17. Budget check
```bash
uv run erenshor capture budge
```
- Currently ~18,315 / ~20,000 file Cloudflare limit. New zones eat into the budget; if we cross ~19,500, drop `maxZoom` on the largest new zone before committing.

### Phase 5 — Sanity

#### 18. Full test suite
```bash
uv run pytes
```
- **Acceptance:** all tests pass. Fix any regressions encountered.

#### 19. Restore main's map state
```bash
uv run erenshor maps build --variant main
```
- Leaves `src/maps/static/db/erenshor.sqlite` pointing at main so day-to-day map work isn't accidentally on the playtest DB.

## Risks / failure modes

| Risk | Detection | Response |
|---|---|---|
| Raid content introduces new Unity fields the listeners don't know about | `extract export` log shows nulls or `extract build` fails on missing columns | Add listener field + record column under `src/Assets/Editor/`, see `skill://unity-export-system` |
| Bounds snippet under-counts because new zones use unusual root structure | Master image is clipped or off-centre | Fall back to median-filter snippet referenced in `skill://tile-capture` |
| `mapping.json` gap surfaces in sheets, not in build (silent default) | Spot-check sheets after deploy | Add rule, redeploy the affected sheet only |
| Playtest DB symlink left pointing at playtest when working on main | Map shows playtest-only content during main dev | Step 19 — always restore at end of session |
| Tile budget exceeded | `capture budget` after Phase 4 | Drop `maxZoom` on large new zones before committing |

## Tracking

Open a `bd` issue for this work and link discovered sub-issues:

```bash
bd create "Refresh playtest after v<X> raid update" -p 2 -t task --description "See docs/plans/2026-05-18-playtest-refresh.md"
# For each surprise (new mapping rule, schema fix, etc):
bd create "<Title>" -p 2 --deps discovered-from:<parent-id>
```
