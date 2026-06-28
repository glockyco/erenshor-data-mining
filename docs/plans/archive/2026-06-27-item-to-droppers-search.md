---
title: World Map — Item-to-Droppers Search
type: spec
status: implemented
created: 2026-06-27
parent:
archived: 2026-06-28
---

# World Map — Item-to-Droppers Search

**Goal:** Let users search for a droppable item by name and immediately see every enemy and NPC that drops it highlighted on the world map, with a popup listing each dropper alongside its drop chance.

**Architecture:** A new `ItemSearchProvider` slots into the existing `SearchProvider` infrastructure without touching the search engine, map renderer, or URL state. Item dropper data is preloaded server-side (one extra query in `+page.server.ts`) and passed to `buildSearchIndex`. The `"Drops"` result group in `MapSearch.svelte` is a small additive change. Highlight resolution cross-references character stable keys against already-loaded world markers — no new DB queries at runtime.

**Tech Stack:** SvelteKit (`+page.server.ts` prerender), deck.gl (`+page.svelte` layer composition), Svelte 5 (`$state`/`$derived`), sql.js (`RepositoryBase`), TypeScript.

---

## Data shape

971 map-visible droppable items, 3,965 drop relationships across enemies and NPCs.

The server-side query (new `getItemDroppers()` on `RepositoryBase`):

```sql
SELECT
    i.stable_key        AS item_stable_key,
    i.display_name,
    i.wiki_page_name,
    c.stable_key        AS character_stable_key,
    c.npc_name,
    c.is_friendly,
    c.is_rare,
    c.is_unique,
    ld.drop_probability
FROM loot_drops ld
JOIN items i ON i.stable_key = ld.item_stable_key
JOIN characters c ON c.stable_key = ld.character_stable_key
WHERE i.is_map_visible = 1
ORDER BY i.display_name, ld.drop_probability DESC
```

Returned as `ItemDropperRow[]`:
```typescript
type ItemDropperRow = {
    itemStableKey: string;
    displayName: string;
    wikiPageName: string | null;
    characterStableKey: string;
    npcName: string;
    isFriendly: boolean;
    isRare: boolean;
    isUnique: boolean;
    dropProbability: number; // 0–100
};
```

Added to the `load()` return value in `+page.server.ts` as `itemDroppers: ItemDropperRow[]`. `FilteredMapData` in `types/world-map.ts` gains a matching field.

---

## Search result type

New discriminant added to the `SearchResult` union in `search/types.ts`:

```typescript
export type ItemSearchResult = {
    type: 'item';
    itemName: string;
    wikiPageName: string | null;
    dropperCount: number;   // total unique characters
    zoneCount: number;      // unique zones containing any dropper spawn
};

export type SearchResult = EnemySearchResult | NpcSearchResult | ZoneSearchResult | ItemSearchResult;
// Comment on line 38: updated from "// Future: | ItemSearchResult"
```

---

## ItemSearchProvider

New file `src/maps/src/lib/map/search/item-drop-provider.ts`:

```typescript
export class ItemSearchProvider implements SearchProvider {
    readonly categoryLabel = 'Drops';
    readonly categoryOrder = 0; // highest priority — item search is the primary new use case

    // item stable key → { result, characterStableKeys[] }
    private readonly itemMap: Map<string, {
        result: ItemSearchResult;
        characterStableKeys: string[];
    }>;

    constructor(
        rows: ItemDropperRow[],
        allMarkers: (WorldEnemy | WorldNpc)[]
    ) {
        // Build item → dropper character keys mapping
        // Then compute zoneCount by cross-referencing allMarkers
        ...
    }

    buildIndex(): IndexEntry[] { ... }

    resolveHighlight(result: SearchResult): ResolvedHighlight {
        // Cross-reference characterStableKeys against allMarkers.characters[].stableKey
        // Returns { type: 'positions', positions: [...], stableKeys: [...] }
        // covering every spawn point that contains at least one dropper character
    }
}
```

`buildSearchIndex()` in `search/index.ts` gains:
- Parameter `itemDroppers: ItemDropperRow[]`
- Constructs `itemProvider = new ItemSearchProvider(itemDroppers, [...enemiesCommon, ...enemiesRare, ...enemiesUnique, ...npcs])`
- Adds it to `providers[]`
- Exposes `itemProvider` on the `SearchIndex` interface

---

## Search palette changes (MapSearch.svelte)

Three minimal additions:

```typescript
// categoryLabels
const categoryLabels: Record<SearchResult['type'], string> = {
    enemy: 'Enemy Spawn Points',
    npc: 'NPC Spawn Points',
    zone: 'Zones',
    item: 'Drops'               // new
};

// staticCategoryOrder controls display grouping in MapSearch.svelte; categoryOrder controls
// interleaving priority within buildSearchIndex. Both set items first.
const staticCategoryOrder: SearchResult['type'][] = ['item', 'enemy', 'npc', 'zone'];

// getStaticResultSublabel
case 'item': {
    return `${result.dropperCount} dropper${result.dropperCount !== 1 ? 's' : ''} · ${result.zoneCount} zone${result.zoneCount !== 1 ? 's' : ''}`;
}

// getStaticResultValue
case 'item':
    return `item-${result.itemName}`;
```

Result card icon in the palette: `Package` from Lucide — add `import Package from '@lucide/svelte/icons/package'` to `MapSearch.svelte`.

---

## Popup: SearchItemPopup.svelte

New file `src/maps/src/lib/components/map/popups/SearchItemPopup.svelte`, modeled on `SearchEnemyPopup.svelte`.

Props:
```typescript
interface Props {
    result: ItemSearchResult;
    markers: (WorldEnemy | WorldNpc)[];  // all spawn markers containing a dropper character
    dropRows: ItemDropperRow[];           // from searchIndex.itemProvider
    onHoverSpawn: (stableKey: string | null) => void;
    onFocusSpawn: (stableKey: string) => void;
    onFocusAll: () => void;
}
```

Layout:
1. **Header row** — item name, optional wiki link (`WikiLink` component)
2. **"Show all N spawn points" button** — calls `onFocusAll()`, same style as `SearchEnemyPopup`
3. **Dropper list** — one row per dropper character, grouped by zone (descending spawn count), sorted within zone by drop probability descending. Each row shows:
   - Character name
   - Rarity chip (`Unique` / `Rare` / no chip for common) — matching existing rarity badge CSS
   - Drop chance (`3.2%`)
   - Spawn count for that character in this zone
   - Crosshair icon (hover → `onHoverSpawn`, click → `onFocusSpawn`)

`onHoverSpawn` and `onFocusSpawn` accept a spawn point stable key and delegate to the existing `handleHoverSpawn` / `handleFocusSpawn` handlers in `+page.svelte` unchanged.

---

## Popup routing in +page.svelte / MapPopup.svelte

`MapPopup.svelte` (or `PopupContainer.svelte` — wherever `SearchEnemyPopup` is currently dispatched) gains a branch for `selection.type === 'search' && selection.result.type === 'item'` that renders `SearchItemPopup` with:
- `result` from `selection.result`
- `markers` from `searchIndex.itemProvider.getMarkersForItem(result.itemName)` (a new helper method on `ItemSearchProvider`)
- `dropRows` from `searchIndex.itemProvider.getDropRowsForItem(result.itemName)`

The fly-to behavior (`handleFocusAll`) and hover/focus handlers are already wired at the `+page.svelte` level — no changes needed there.

---

## Acceptance criteria

- Typing a map-visible item name (e.g. "Luminstone") in the search palette shows a "Drops" group entry with dropper count + zone count.
- Selecting the entry highlights all dropper spawn points on the map and flies to their bounding box.
- The popup lists every dropper character with drop %, grouped by zone, sorted by drop probability.
- Hovering a dropper row narrows the map highlight to that character's spawns.
- Clicking a dropper row flies to that character's spawns.
- Items with `is_map_visible = 0` do not appear.
- No runtime DB queries — all data preloaded at build time.
