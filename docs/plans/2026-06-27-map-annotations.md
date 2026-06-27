---
title: World Map — User Annotations (Pins, Paths, Regions)
type: spec
status: active
created: 2026-06-27
parent:
---

# World Map — User Annotations (Pins, Paths, Regions)

**Goal:** Let users place personal annotations on the world map — styled point pins (icon + color), drawn paths (farming routes), and drawn regions (area highlights) — persisted in localStorage with JSON export/import for backup and sharing.

**Architecture:** A self-contained annotation subsystem: a `AnnotationStore` class wraps localStorage reads/writes and exposes reactive state; three deck.gl layers render the stored GeoJSON; a drawing state machine handles mode transitions and vertex accumulation; a floating mode indicator shows the active drawing mode. The annotation icon atlas is a separate function from the existing `createIconAtlas()` to keep concerns isolated. No backend, no accounts.

**Tech Stack:** SvelteKit + Svelte 5 (`$state`), deck.gl (`ScatterplotLayer`, `IconLayer`, `PathLayer`, `PolygonLayer`), GeoJSON, localStorage, Lucide icons.

---

## Data model

Annotations are stored as a GeoJSON `FeatureCollection` under the localStorage key `erenshor-annotations`. Each feature:

```typescript
type AnnotationGeometry =
    | { type: 'Point';      coordinates: [number, number] }
    | { type: 'LineString'; coordinates: [number, number][] }
    | { type: 'Polygon';    coordinates: [number, number][][] }; // outer ring only

type AnnotationProperties = {
    id: string;          // crypto.randomUUID()
    label: string;       // optional, ≤60 chars; empty string = no label
    note: string;        // optional free-form text; empty string = no note
    color: string;       // one of ANNOTATION_COLORS (hex)
    icon: string;        // one of ANNOTATION_ICONS — Point only; ignored for Line/Polygon
    createdAt: number;   // Date.now()
};

type Annotation = GeoJSON.Feature<AnnotationGeometry, AnnotationProperties>;
type AnnotationCollection = GeoJSON.FeatureCollection<AnnotationGeometry, AnnotationProperties>;
```

Coordinates are world `[x, y]` — the same space as all other deck.gl markers. The coordinate system is never lat/lng.

---

## Preset palette

### Colors (6)
```typescript
export const ANNOTATION_COLORS = {
    white:  '#e4e4e7',
    red:    '#ef4444',
    yellow: '#eab308',
    green:  '#22c55e',
    cyan:   '#06b6d4',
    orange: '#f97316',
} as const;
export type AnnotationColor = keyof typeof ANNOTATION_COLORS;
```

Defaults: `color = 'yellow'`, `icon = 'flag'`.

### Icons (12, Point annotations only)
Sourced from `lucide` (already a project dependency):

| Key | Lucide export |
|---|---|
| `flag` | `Flag` |
| `star` | `Star` |
| `map-pin` | `MapPin` |
| `skull` | `Skull` |
| `alert` | `TriangleAlert` |
| `check` | `CircleCheck` |
| `flame` | `Flame` |
| `gem` | `Gem` |
| `sword` | `Sword` |
| `target` | `Crosshair` |
| `package` | `Package` |
| `question` | `CircleHelp` |

---

## Annotation store

New file `src/maps/src/lib/map/annotations/store.svelte.ts`:

```typescript
export class AnnotationStore {
    annotations = $state<Annotation[]>([]);

    constructor() { this.load(); }

    private load(): void { /* read + parse localStorage */ }
    private save(): void { /* write JSON to localStorage */ }

    add(annotation: Annotation): void;
    update(id: string, patch: Partial<AnnotationProperties>): void;
    remove(id: string): void;

    exportJson(): string;           // JSON.stringify of the FeatureCollection
    importJson(json: string): void; // parse + merge by id (skip duplicates)
}
```

A singleton instance is created once in `+page.svelte` and passed down. The `annotations` field is a Svelte 5 `$state` array so deck.gl layers re-render reactively when it changes.

---

## Annotation icon atlas

New file `src/maps/src/lib/map/annotations/icon-atlas.ts` — a function parallel to `createIconAtlas()`:

```typescript
export async function createAnnotationIconAtlas(): Promise<IconAtlasResult>
```

Renders each of the 12 annotation icons as a **white icon on a transparent background** (no colored circle — the color comes from the `ScatterplotLayer` beneath). The mapping uses `mask: false` — the raw white-on-transparent PNG is used as-is. The deck.gl `IconLayer` for pins renders above a `ScatterplotLayer` that provides the colored circle, keeping color and shape independent.

Atlas layout: one row of 12 cells at 64 × 64 px each.

---

## Drawing state machine

New file `src/maps/src/lib/map/annotations/drawing.svelte.ts`:

```typescript
export type DrawingMode = 'off' | 'pin' | 'path' | 'polygon';

export class DrawingState {
    mode = $state<DrawingMode>('off');
    inProgressVertices = $state<[number, number][]>([]);
    // cursor position for ghost rendering (updated on mousemove)
    cursorPosition = $state<[number, number] | null>(null);

    setMode(m: DrawingMode): void;
    addVertex(pos: [number, number]): void;  // called on map click
    finish(): [number, number][] | null;     // returns vertices, resets state
    cancel(): void;                          // Escape key or mode switch
}
```

Mode transitions: switching mode always calls `cancel()` first. `finish()` is called on:
- **Pin**: immediately on first click
- **Path**: double-click, or "Done" button in the mode indicator chip
- **Polygon**: double-click (auto-closes to first vertex), or "Done" button

---

## Deck.gl layers

All annotation layers are added to `createLayers()` in `+page.svelte`, above movement overlays and below selection highlights. They are always rendered (no layer toggle — annotations are the user's own content, always visible).

```
// Layer stack order (annotation layers):
allWanderRangesLayer,
allPatrolPathsLayer,
annotationPolygonLayer,    // filled regions (lowest — terrain-like)
annotationPathLayer,       // drawn routes
annotationPinCircleLayer,  // ScatterplotLayer: colored circle background
annotationPinIconLayer,    // IconLayer: white icon on top
// ... selection highlights above
```

### annotationPolygonLayer — `PolygonLayer`
- Data: `annotations.filter(a => a.geometry.type === 'Polygon')`
- `getPolygon`: the outer ring coordinates
- `getFillColor`: parse hex from `properties.color`, alpha 40/255
- `getLineColor`: parse hex, alpha 200/255
- `getLineWidth: 2`, `lineWidthUnits: 'pixels'`
- `pickable: true` → click selects for editing/deletion

### annotationPathLayer — `PathLayer`
- Data: `annotations.filter(a => a.geometry.type === 'LineString')`
- `getPath`: coordinates array
- `getColor`: parse hex, alpha 220/255
- `getWidth: 3`, `widthUnits: 'pixels'`
- `pickable: true`

### annotationPinCircleLayer — `ScatterplotLayer`
- Data: `annotations.filter(a => a.geometry.type === 'Point')`
- `getPosition`: coordinates
- `getRadius: 14`, `radiusUnits: 'pixels'`
- `getFillColor`: parse hex from `properties.color`
- `getLineColor: [0, 0, 0, 100]` (subtle shadow border)
- `stroked: true`, `lineWidthMinPixels: 1`
- `pickable: true`

### annotationPinIconLayer — `IconLayer`
- Same data as circle layer
- Uses annotation atlas
- `getIcon`: `properties.icon`
- `getSize: 22`, `sizeUnits: 'pixels'`
- `getColor: [255, 255, 255, 255]` (always white)
- `pickable: false` (picking handled by circle layer beneath)

### In-progress ghost layers (drawing mode only)
When `drawingState.mode !== 'off'` and `drawingState.inProgressVertices.length > 0`:
- A `ScatterplotLayer` renders placed vertices as small white dots
- A `PathLayer` renders edges between placed vertices + a trailing edge to `cursorPosition`
- These use the currently selected color at 60% opacity

---

## Mode indicator chip

A small floating `<div>` at the bottom-center of the map, visible only when `drawingState.mode !== 'off'`:

```
[ 📍 Pin mode — click to place · Esc to cancel ]
```

For path/polygon:
```
[ — Path mode — click to add points · double-click or [Done] to finish · Esc to cancel ]  [Done]
```

Positioned with `class="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 ..."` so it doesn't overlap the sidebar.

---

## Sidebar controls (Annotations section)

A new `SidebarSection title="Annotations"` added to `MapSidebar.svelte` below "Movement":

```
[ Pointer ] [ Pin ] [ Path ] [ Region ]   ← mode button group
○ ● ○ ○ ○ ○                               ← color palette (6 swatches)
⬇ Export    ⬆ Import                       ← two small buttons
```

**Mode button group**: four icon buttons (Pointer/ArrowPointer, MapPin, Route/Spline, Pentagon). Active mode highlighted with a ring. Clicking the active mode button returns to `'off'`.

**Color palette**: clicking a swatch sets `selectedColor` (Svelte state in `+page.svelte`), shown as active with a ring. Default: yellow. Used when the next annotation is placed.

**Icon picker**: shown only when mode = `'pin'`. A 4×3 grid of the 12 icon buttons. Active icon highlighted. Default: flag.

**Export button**: calls `annotationStore.exportJson()`, triggers `<a download>` for `erenshor-annotations.json`.

**Import button**: opens a hidden `<input type="file" accept=".json">`, reads the file, calls `annotationStore.importJson()`.

---

## Annotation placement flow

1. User selects a mode (e.g. Pin) and a color/icon in the sidebar.
2. Map cursor changes to crosshair (`cursor: crosshair` on the deck.gl canvas container).
3. Map `onClick` is intercepted before deck.gl picking when `drawingState.mode !== 'off'`.
4. **Pin**: one click → `drawingState.finish()` returns one vertex → a "New annotation" form popover appears at the screen position of the pin (see below) → on Save, `annotationStore.add(...)` is called.
5. **Path / Polygon**: clicks call `drawingState.addVertex()`. Double-click or "Done" calls `drawingState.finish()` → form popover appears → on Save, `annotationStore.add(...)` is called. Mode returns to `'off'` after save.
6. **Escape** at any point calls `drawingState.cancel()` and returns to `'off'`.

---

## Annotation form popover

A small popover that appears after completing a shape. It is NOT a full sidebar panel — it floats near where the annotation was placed (or centered on the polygon bounding box). Contains:

- **Label** text input (placeholder "Label (optional)", maxlength 60)
- **Note** textarea (placeholder "Note (optional)", 2 rows)
- **Save** button (stores annotation, closes popover)
- **Discard** button (cancels, no annotation stored)

The form re-opens when clicking an existing annotation (pin click via `ScatterplotLayer` pick, path/polygon via `PolygonLayer`/`PathLayer` pick), adding a **Delete** button alongside Save. Edit mode pre-fills the fields.

---

## Click handling for existing annotations

`deck.gl`'s `onBeforeRender`/`onClick` callback in `+page.svelte` receives pick info. When the clicked object comes from an annotation layer, the flow is:

1. `editingAnnotationId` state is set to the picked `properties.id`.
2. The annotation form popover opens pre-filled.
3. Save → `annotationStore.update(id, ...)`, close popover.
4. Delete → `annotationStore.remove(id)`, close popover.

This is separate from `applySelection()` — annotation editing does not affect the map's selection state.

---

## Export / Import

**Export**: `annotationStore.exportJson()` returns a JSON string of the full `AnnotationCollection`. A hidden `<a>` element is created, `href = URL.createObjectURL(new Blob([json], { type: 'application/json' }))`, `download = 'erenshor-annotations.json'`, `.click()` triggered, then revoked.

**Import**: file input `onchange` reads the file as text, passes to `annotationStore.importJson(text)`. Import merges by `id` — annotations whose `id` already exists in the store are skipped (idempotent re-import). Invalid JSON shows a brief error toast. After merge, `save()` is called and the deck.gl layers re-render.

---

## Acceptance criteria

- User can place a pin on the world map by selecting Pin mode in the sidebar then clicking.
- User can draw a path by selecting Path mode, clicking to add vertices, and double-clicking to finish.
- User can draw a region by selecting Polygon mode, clicking vertices, and double-clicking to close.
- Each annotation can have a label, note, color, and (for pins) an icon, set via the form popover.
- Color and icon selection persists as the default for the next annotation placed in the same session.
- All annotations survive page reload (localStorage).
- Clicking an existing annotation opens the edit/delete form.
- Export downloads a valid GeoJSON file. Import re-loads it and merges without duplicates.
- Escape cancels any in-progress drawing without storing anything.
- Annotations do not interfere with the existing map selection/highlight system.
