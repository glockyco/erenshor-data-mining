---
title: Map Search UX — Filter Chips, Icons, Fuzzy, Highlight
type: spec
status: implemented
created: 2026-06-28
parent:
archived: 2026-06-28
---

# Map Search UX — Filter Chips, Icons, Fuzzy, Highlight

**Goal:** Improve the `/map` command palette search experience with five
user-facing improvements and one asset-pipeline prerequisite: (1) category
filter chips with live result counts, (2) item icons in palette rows and the
item popup, (3) fuzzy search via Fuse.js with conservative typo tolerance,
(4) matched-substring highlighting in result rows, and (5) arrow-key
navigation for the chip row. Chips, counts, keyboard cycling, and highlighting
cover both static results and live entities (players/pets/NPCs from the
companion mod); the Live chip renders only when the mod is connected. The
matching function (`searchMarkers`) gains tiered Fuse fallback and returns
match-range metadata; `searchLiveEntities` gains match-range metadata without
Fuse; the map renderer, URL state, and popup dispatch are unchanged.

**Tech Stack:** SvelteKit (`+page.server.ts` prerender), bits-ui `Command`
palette, Svelte 5 (`$state`/`$derived`), TypeScript, Fuse.js (new dep), sharp
(new dev dep, build-time WebP conversion), Node prebuild scripts.

---

## Architecture

```
build step (Node script)      →  icon assets (WebP in static/items/)
+page.server.ts load()        →  adds iconName to getItemDroppers query
ItemSearchProvider            →  propagates iconName onto ItemSearchResult
searchMarkers() (index.ts)   →  tiered matching: prefix → substring → Fuse
searchLiveEntities()          →  gains matchRange return; no Fuse (live is small)
MapSearch.svelte              →  pill chips w/ counts, icons, highlight, arrows
SearchItemPopup.svelte        →  larger item icon in header
```

Layered, not entangled: chips consume result counts (read-only); Fuse changes
what matches but chips just display counts of whatever is returned; icons are a
render-layer concern with a build-step prerequisite. Each improvement can be
verified independently.

**New dependencies** (`src/maps/package.json`):
- `fuse.js` (~6 KB gz) — runtime fuzzy matching
- `sharp` (devDependency) — build-time PNG→WebP conversion

---

## Data shape

### `ItemDropperRow` gains `iconName`

```sql
SELECT
    i.stable_key        AS itemStableKey,
    i.display_name      AS displayName,
    i.wiki_page_name    AS wikiPageName,
    i.item_icon_name    AS iconName,        -- new
    c.stable_key        AS characterStableKey,
    c.npc_name          AS npcName,
    c.is_friendly       AS isFriendly,
    c.is_rare           AS isRare,
    c.is_unique         AS isUnique,
    ld.drop_probability AS dropProbability
FROM loot_drops ld
JOIN items i ON i.stable_key = ld.item_stable_key
JOIN characters c ON c.stable_key = ld.character_stable_key
WHERE i.is_map_visible = 1
ORDER BY i.display_name, ld.drop_probability DESC
```

`ItemDropperRow` (in `map-markers.ts`) gains `iconName: string | null`.

### `ItemSearchResult` gains `iconName`

```typescript
export type ItemSearchResult = {
    type: 'item';
    itemStableKey: string;
    itemName: string;
    iconName: string | null;   // new
    wikiPageName: string | null;
    dropperCount: number;
    zoneCount: number;
};
```

`ItemSearchProvider` sets `iconName` from the first drop row's `iconName`
(matching how it already reads `displayName`/`wikiPageName`).

---

## Build step — `scripts/generate-item-icons.mjs`

New Node script, registered in the maps prebuild step alongside
`generate-tiles-manifest.js` and `generate-og-image.mjs`. No Python change —
`maps build` already invokes Node prebuild scripts.

Responsibilities:
1. Read distinct `item_icon_name` values from the DB (`static/db/erenshor.sqlite`)
2. For each, locate `<unity-export>/Assets/Texture2D/<iconName>.png`
3. Convert to WebP at two sizes using `sharp`:
   - `<iconName>.w20.webp` — palette rows (20px display)
   - `<iconName>.w48.webp` — popup header (48px display)
4. Write to `src/maps/static/items/`
5. Skip already-converted icons (idempotent; only converts new/changed)
6. Log a summary count

**Path resolution:** the Unity export path comes from the variant config
(resolved variant dir). The script must work for `main`, `playtest`, `demo`
variants — same pattern as the DB copy step in `maps build`.

**Missing-icon handling:** if `item_icon_name` is null/empty or the PNG
doesn't exist, skip silently (the render layer falls back to the Lucide
`Package` icon).

**Payload:** ~1,324 icons × 2 sizes. WebP at these small sizes is ~1–3 KB
each → ~3–8 MB total raw on disk. Not preloaded — the palette only renders
icons for the ~20 currently-visible rows; the browser fetches per-icon and
caches.

---

## Category filter chips (MapSearch.svelte)

Horizontal pill chips above the results list, below the search input. The
Live chip only renders when the companion mod is connected
(`liveEntities.length > 0`); otherwise it is absent, not greyed — a dead
chip with no connection is noise.

```
[ All ]  [ Live (3) ]  [ Drops (12) ]  [ Enemies (3) ]  [ NPCs (1) ]  [ Zones (0) ]
```

**State:** `activeCategory: SearchResult['type'] | 'live' | 'all'` (default
`'all'`). The `'live'` variant is only selectable while live entities are
present.

**Counts:** derived from the current results — computed once per search,
not re-queried. Static chips count from `staticResults` grouped by type;
the Live chip counts `liveResults.length` (already capped at 5 by
`searchLiveEntities`).

**Zero-count chips:** render disabled/greyed (`opacity-40 cursor-not-allowed`),
not hidden. Five static categories is few enough that greyed-out is clearer
than disappearing chips and avoids layout shift as the user types. The Live
chip is the exception: absent entirely when there is no connection, because
zero live entities means the feature isn't active.

**Selection model:** single-select. Clicking a chip sets `activeCategory`;
the results list filters to that category. `All` restores round-robin
interleave and shows live results first (matching existing render order).
Selecting `Live` shows only live results. Selecting a static category hides
live results. When `activeCategory !== 'all'` and `!== 'live'`, interleave is
bypassed and static results show in their in-category sort order (enemy
rarity sort, alphabetical for others) — the existing `sortCategories` still
runs.

**Visuals (existing design tokens):**
- Selected chip: `bg-accent text-accent-ink` (the gold `#e2b15a`)
- Unselected chip: `bg-surface-2 text-muted hover:text-ink`
- Pill-shaped (`rounded-full`), `text-xs`, tight padding
- No side-stripe borders — full pill background only (impeccable ban)

**Keyboard navigation:**
- `Tab` / `Shift+Tab`: cycles focus between chips (forward/backward). Chips
  form a `role="group"` with `aria-label="Filter by category"`; each chip is a
  `<button>` with `aria-pressed` reflecting `activeCategory`.
- `←` / `→`: switches `activeCategory` directly when focus is in the chip row
  (no intermediate activate step — arrows select the category instantly).
  Cycle order matches render order: `All → Live → Drops → Enemies → NPCs →
  Zones → All` (Live skipped when absent).
- Arrows only navigate chips when focus is *not* in the text input (arrows
  move the cursor in the input, as they must).
- Results list: keeps existing `↑` / `↓` + `Enter`. No conflict — chips are
  above the input/results, results nav stays within the list.
- Flow: type → `Tab` once to leave input → `←`/`→` switches categories, `↑`/`↓`
  walks results. No further focus management needed.

**Visible focus:** `focus-visible:ring-2 ring-accent ring-offset-2 ring-offset-bg`
on each chip — readable at 200% zoom per accessibility requirements.

**Reduced motion:** chip selection is instant (no transition). The only motion
is a 100ms `background-color` fade on hover/active — gated behind
`@media (prefers-reduced-motion: reduce)` to snap instead.

---

## Item icons in render

**Palette rows (MapSearch.svelte):** 20px icon left of the result text.
For `result.type === 'item' && result.iconName`:
```svelte
<img src={`/items/${result.iconName}.w20.webp`} alt="" class="h-5 w-5 shrink-0" />
```
Otherwise: existing Lucide icons (Skull/User/MapIcon/Package fallback).

**Popup header (SearchItemPopup.svelte):** 48px icon next to the item name and
wiki link:
```svelte
<img src={`/items/${result.iconName}.w48.webp`} alt="" class="h-12 w-12" />
```
Only for items (the popup is item-specific).

`alt=""` because the name is the adjacent text — icon is decorative.

---

## Fuzzy search (Fuse.js)

### Tiered matching

```
Tier 1: exact prefix (startsWith)      — highest rank
Tier 2: substring (includes)           — middle rank
Tier 3: Fuse fuzzy fallback             — lowest rank
```

Each tier fully exhausted before the next. Within each tier, results keep
their existing in-category sort (rarity for enemies, alphabetical for
others). Round-robin interleave across categories still applies.

**Why tiered, not Fuse-first:** Fuse on its own would rank "lum" against
200+ items containing those letters, burying exact prefix matches like
"Luminstone". Tiering guarantees that a user who types the real prefix gets
it first; fuzzy only rescues when exact/substring yield nothing or too
little.

### Fuse config

```typescript
const fuse = new Fuse(entries, {
    keys: ['searchText'],
    threshold: 0.5,        // conservative — tolerates 1-2 char edits
    distance: 100,
    minMatchCharLength: 2,
    includeScore: true,
    ignoreLocation: false
});
```

Conservative typo tolerance: "lumsten" → "Luminstone", but won't match wildly
unrelated names.

### `searchMarkers` signature change

```typescript
export type SearchMatch = {
    result: SearchResult;
    matchRange: [number, number] | null;  // char offsets for highlight; null for fuzzy
};

export function searchMarkers(
    query: string,
    index: IndexEntry[],
    limit?: number
): SearchMatch[];
```

`matchRange` is `[start, end]` character offsets into the lowercased name for
prefix/substring matches (for highlight rendering). `null` for fuzzy matches
(Fuse doesn't give clean ranges cheaply, and highlighting fuzzy matches is
visually noisy).

### Performance

Fuse builds its index once over the flat `entries` array (1,655 entries —
trivial). Rebuilt only when `searchIndex` rebuilds (live-entity changes).
Per-query Fuse search is sub-millisecond at this scale. The existing 150ms
debounce stays.

### Fuse instance lifecycle

`IndexEntry` is unchanged — Fuse indexes the `searchText`
field directly. A `Fuse` instance is held on `SearchIndex` (built inside
`buildSearchIndex`, rebuilt when live entities change) so the index is not
recomputed per query.

---

## Matched-substring highlighting

In the palette result row, bold the portion of the name that matched the
query. `searchMarkers` returns `matchRange`; the row renderer wraps that range
in `<mark class="bg-transparent text-ink font-semibold">` (no background —
just weight/color emphasis, consistent with the dark theme).

For fuzzy matches (`matchRange === null`), no highlight — the full name shows
in normal weight. Highlighting fuzzy matches is visually noisy and Fuse
doesn't expose clean ranges cheaply.

**Label function:** `getStaticResultLabel` returns the raw name; the render
emplate splits it by `matchRange` into `[before, match, after]` and wraps
`match` in the `<mark>`.

---

## Live entities (companion mod)

Live entities (players, pets, NPCs from the companion mod) are a separate
result stream from the static `searchMarkers` path. They use their own
`searchLiveEntities()` function (prefix→substring, capped at 5) and render as
a `Live Entities` group at the top of the results list. They are included in
the chip system so counts and filtering stay consistent when the mod is
connected.

**Chip:** a `Live` chip renders first after `All`, but only when
`liveEntities.length > 0`. When the mod is disconnected, the chip is absent
(not greyed) — zero live entities means the feature isn't active, and a
dead chip is noise. The count is `liveResults.length` (already capped at 5).

**Fuzzy:** live entities keep their own `searchLiveEntities()` and do **not**
use Fuse. They are few (≤5, contextual to the current zone) and the existing
prefix→substring matching is sufficient; fuzzy adds complexity for no gain.
Live results are always excluded from the Fuse index.

**Highlighting:** `searchLiveEntities()` returns match-range metadata so live
result names highlight consistently with static results. The function gains
the same `matchRange` return shape as `searchMarkers` — prefix/substring
matches carry `[start, end]`, and since live search has no fuzzy tier,
`matchRange` is never `null` for live results.

**Filtering:** selecting the `Live` chip shows only live results. Selecting
`All` shows live results first (existing render order) then static results.
Selecting any static category hides live results. The `←`/`→` cycle order is
`All → Live → Drops → Enemies → NPCs → Zones → All`, skipping Live when
absent.

---

## Deferred improvements

Two improvements were researched but deferred — see
`2026-06-28-map-search-deferred-ux` for rationale: per-category empty
states and recent-searches persistence.

---

## Acceptance criteria

- [ ] Typing a query shows a row of pill chips (All · Drops · Enemies · NPCs ·
      Zones) with live result counts; zero-count chips are greyed, not hidden.
- [ ] When the companion mod is connected, a `Live` chip renders first after
      `All` with a live-entity count; when disconnected, the chip is absent.
- [ ] Clicking a chip filters the results list to that category; `All`
      restores round-robin interleave and shows live results first.
- [ ] `←`/`→` switches the active category when focus is in the chip row
      (after one `Tab` from the input); cycle order is All → Live → Drops →
      Enemies → NPCs → Zones (Live skipped when absent); `↑`/`↓` still
      navigates results.
- [ ] Item results show their in-game sprite icon (20px) in the palette row;
      non-item results keep their Lucide icons.
- [ ] The `SearchItemPopup` header shows the item icon (48px) next to the
      name and wiki link.
- [ ] Typing a slightly misspelled name (e.g. "lumsten") returns the intended
      item ("Luminstone") via fuzzy fallback, ranked below exact matches.
- [ ] Exact prefix/substring matches still rank above fuzzy matches.
- [ ] The matched substring is bolded in result rows for prefix/substring
      matches (both static and live); fuzzy matches show no highlight.
- [ ] Live entity names highlight matched substrings; live search does not
      use Fuse.
- [ ] `uv run erenshor maps build` generates the WebP icon assets in
      `static/items/` as a prebuild step.
- [ ] All existing tests pass; new tests cover the Fuse tiered matching and
      chip count/filter logic.
