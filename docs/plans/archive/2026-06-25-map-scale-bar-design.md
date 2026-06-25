---
title: Map Scale Bar Design
type: spec
status: implemented
created: 2026-06-25
parent:
superseded_by:
archived: 2026-06-25
---

# Map Scale Bar Design

**Surface:** `src/maps/` — SvelteKit map UI, deck.gl world map, Leaflet zone maps.
**Visual mockup:** `docs/mockups/map-scale-bar/index.html`.

---

## 1. Goal

Add a clean scale-bar overlay to both map surfaces:

- `/map` world overview.
- `/:mapName` individual zone maps.

The scale bar displays **Erenshor coordinate units**, not meters, feet, miles, or kilometers. Success means the bar stays correct under pan, zoom, sidebar layout changes, resize, and zone-map rotation without depending on brittle zoom-only math. It must look like native map instrumentation, not a floating card.

## 2. Non-goals

- No metric or imperial unit conversion.
- No Leaflet `L.control.scale`; its labels are geographic/real-world units and are wrong for `L.CRS.Simple` game coordinates.
- No static CSS-only ruler.
- No hardcoded `2 ** zoom` scale calculation for the deck.gl world map.
- No new measurement tool or click-to-measure interaction.

## 3. Chosen approach

Use one shared visual component and one pure scale-selection module, with thin adapters for each map engine.

The adapters compute local coordinate distance from the active viewport transform at the scale bar's actual screen position:

- **World map:** read the active deck.gl viewport (`deckInstance.getViewports?.()[0]`) and call `viewport.unproject([screenX, screenY])` for the bar's left/right screen points.
- **Zone maps:** call Leaflet `map.containerPointToLatLng(...)` for the same left/right bar points. With `L.CRS.Simple`, `lat`/`lng` are local map coordinates, not geography.

Distance is Euclidean in map coordinates. This makes the displayed scale a local measurement at the bar position, matching cartographic best practice for projected/rotated map views.

## 4. Visual design

Use a map-native scale rule, not a boxed widget.

Placement:

- World map: lower-left map chrome, offset past the sidebar on desktop and near the viewport edge on mobile.
- Zone maps: lower-left map chrome, visually aligned with the Leaflet controls but not using Leaflet's metric/imperial scale control.

Style:

- No surrounding panel/card/box.
- Horizontal hairline ruler with end ticks and a center tick.
- High-contrast two-tone stroke: light foreground with a dark halo/shadow so it remains readable over both bright world-map art and dark zone tiles.
- Compact mono label: `250 units`.
- Label uses text shadow/halo rather than a filled badge.
- Hide until a finite valid measurement exists; never show stale values after map teardown.

Existing zone-map chrome fix:

- Restyle the custom rotation mode control (`Match Compass` / `Match Coordinates`) from its current inline white surface to the normal black-ish map chrome.
- Keep it as a Leaflet control, but give it explicit dark background, border, foreground, hover, and focus states instead of inheriting default light Leaflet styling.
- Implement that control styling with a global class (`app.css` or `:global(...)`) or explicit inline styles, because Leaflet DOM created through `L.DomUtil.create` will not receive Svelte's scoped style attribute.

## 5. Scale-selection behavior

The bar targets a readable pixel width, then chooses a nice Erenshor-unit value that fits.

Algorithm:

1. Measure how many Erenshor units are represented by `maxPixelWidth` CSS pixels at the bar's screen position.
2. Choose the largest nice distance that is less than or equal to that measured distance.
3. Convert the chosen unit distance back to CSS pixels using the local units-per-pixel ratio.
4. Render that pixel width and label.

Nice distances use the series:

```text
1, 2, 2.5, 5 × 10^n
```

Examples:

| Measured units in 120 px | Chosen label | Render width |
|---:|---:|---:|
| 37 | `25 units` | ~81 px |
| 118 | `100 units` | ~102 px |
| 312 | `250 units` | ~96 px |
| 1,220 | `1,000 units` | ~98 px |

## 6. Module boundaries

Create:

- `src/maps/src/lib/map/scale-bar.ts`
  - Pure types and functions: `ScaleBarState`, nice-distance selection, label formatting, measured-distance-to-state conversion.
  - No Svelte, deck.gl, Leaflet, DOM, or window dependencies.
- `src/maps/src/lib/components/map/ScaleBar.svelte`
  - Presentational component that receives `ScaleBarState | null` and optional positioning classes/style.
  - Renders nothing for `null`.

Modify:

- `src/maps/src/routes/map/+page.svelte`
  - Maintain `scaleBarState` from deck.gl viewport measurements.
  - Recompute on map initialization, view-state changes, sidebar changes, and window resize.
  - Render `ScaleBar` above the map container chrome.
- `src/maps/src/routes/[mapName]/+page.svelte`
  - Maintain `scaleBarState` from Leaflet `containerPointToLatLng` measurements.
  - Recompute on map initialization, move, zoom, resize, and rotation/bearing changes.
  - Remove event listeners when the Leaflet map is torn down.
  - Restyle the rotation mode control to match dark map chrome.

## 7. Testing strategy

Use TDD for production code.

Unit tests:

- Add `src/maps/src/lib/map/scale-bar.test.ts`.
- Assert nice-distance selection picks stable labels and widths.
- Assert invalid measurements (`0`, negative, `NaN`, infinite, zero pixel width) return `null`.
- Assert label formatting stays in Erenshor units and never emits meters/feet.

Integration checks:

- `pnpm --filter maps test -- scale-bar`
- `pnpm --filter maps check`
- Manual browser smoke test on `/map` and at least one zone map:
  - zoom changes label/width.
  - pan keeps label finite.
  - sidebar collapse moves the world-map bar without changing to stale state.
  - zone-map rotation keeps a finite game-unit label.
  - scale bar has no boxed/card background.
  - `Match Coordinates` / `Match Compass` uses black-ish map chrome, not a white control.

## 8. Planned commits

1. `docs(map): design the Erenshor scale bar`
2. `feat(map): add viewport-measured scale bars`

## 9. Risks and decisions

- **Projection/rotation honesty:** the label is a local measurement at the bar's screen position. This is intentionally more honest than a single global scale value.
- **Engine split:** deck.gl and Leaflet stay isolated in adapters; shared behavior lives in pure functions and a presentational Svelte component.
- **Maintainability:** no engine-specific formatting logic in the visual component; no zoom-derived shortcuts; no hidden fallback to real-world map units.
