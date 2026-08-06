---
title: Wiki Main Page Redesign
type: plan
status: active
created: 2026-08-06
parent: 2026-07-09-erenshor-planning-overview
---

# Wiki Main Page Redesign

Ship a rebuilt landing page for `Erenshor Wiki` and its `Template:Main page/styles.css`.

## Artifacts

| Path | Role |
|---|---|
| `wiki/Erenshor_Wiki.txt` | Live page source. Still the previous design. |
| `wiki/Erenshor_Wiki.styles.css` | Live stylesheet source. Still the previous design. |

A working draft in HTML and CSS, plus reference renders, sits untracked under
`.impeccable/mocks/`. Treat it as disposable scratch: it may be absent on another
machine or after a clean checkout. This plan is the durable record, so the draft is
reproducible from the structure and decisions below rather than required as input.

Preview by serving that directory over HTTP after rewriting the wiki and Steam
asset URLs to a local `img/` copy.

## Structure

Nine modules in a mosaic, the arrangement every comparable game wiki converges on.
A single organising metaphor cannot hold this corpus, because Crafting, Classes,
Items, Lore and the map are not level-banded.

1. Hero — wordmark, Steam-derived lede, fact chips, over `Site-background.jpg`.
2. Latest update — patch summary and key art.
3. New here? — five-step numbered path.
4. Browse by type — eight entity tiles.
5. Zones by level — the level track (below).
6. Classes — six classes, icon, role, one line each.
7. The world — three-image strip plus world links.
8. Guides — all nine, full width, three columns.
9. Interactive map / Watch / Things to do — even three-up.
10. Help build the wiki / Official links.

## Decisions that stand

- **Copy is sourced or deleted.** A description may only name what the target page's
  own sections contain. Steam copy, `wiki/Zones.txt`, and quoted page text are the
  other admissible sources. No scope words (`start to finish`, `every`, `full`,
  `raid-ready`) unless the source carries them.
- **Never describe Simulated Players as AI.** The Steam page states they use no LLM
  or emerging AI model, running on state machines and decision trees. Use
  "Simulated Players" on first mention.
- **Register follows Steam**: short declarative sentences, old-school MMO
  vocabulary, difficulty stated honestly, no product-design filler.
- **Level track** shows one band at a time, as `<tabber>` (TabberNeue 3.3.0). The tab
  strip is the ladder. Six bands: 1–8, 9–14, 15–20, 21–27, 28–35, 35.
- **Bands assign by median enemy level** from `wiki/Zones.txt`; the median is also the
  displayed value, under a named column. Rows sort ascending and flow column-major,
  so reading down a column stays in order.
- **Zone coverage** is 44 rows. All three Mysterious Portals appear, disambiguated by
  parent zone. Bellwain Island sits in band 1 marked `no combat`. Secluded Sanctuary
  sits in the 35 band, since its median 40 falls outside 28–35. `Prison` has no level
  data and `Sivakaya's Plane of Destruction` is unimplemented; both are omitted.
- **Colour comes from skin Codex tokens** with night-theme literal fallbacks, because
  Theme Toggle offers a day theme. Day resolves `--color-link` and
  `--border-color-base` to the same `#A65E2D`, so no state may be signalled by border
  hue alone.
- **Sanitizer limits**: `clamp()`, `min()`, `:focus-visible` and `:focus-within` are
  rejected. `minmax()`, `column-width` and `column-gap` are safe. TemplateStyles
  prefixes every selector with `.mw-parser-output`, so no rule can target `html` or
  `body`.
- **No `<evlplayer>` in the hero.** EmbedVideo renders a consent-gated placeholder;
  the trailer lives in the rail behind a poster frame.

## Tasks

- [ ] Produce a matched eight-icon tile set. Current files are inconsistent in
      silhouette, weight and bounding box (`Weapons.png` 167×184, `Armor.png` 123×184,
      `Charms.png` 512×512).
- [ ] Produce six band images for the level track. Four are currently Steam press
      screenshots with HUD visible; only `Site-background.jpg` and `Planar March.png`
      are wiki files.
- [ ] Upload both asset sets to the wiki.
- [ ] Convert `draft-main-page.html` to wikitext in `wiki/Erenshor_Wiki.txt`,
      replacing the radio-input track with `<tabber>` and restoring
      `{{NUMBEROFARTICLES}}` and `{{PAGESINCATEGORY:}}` for the counts.
- [ ] Port `draft-main-page.css` into `wiki/Erenshor_Wiki.styles.css`.
- [ ] Verify the converted wikitext renders through TemplateSandbox before any write.
- [ ] Deploy both pages. Both are cascade-protected and rejected the configured bot
      passwords previously, so expect a manual browser paste.
- [ ] Confirm the deployed page in both themes and at 414px.

## Acceptance

- Every description traces to a source; no page is described beyond its sections.
- Both themes legible, WCAG AA on body and role text.
- No horizontal overflow at 414px.
- Level track exposes one band; all 44 zone rows reachable across the six tabs.
- Zone medians ascend in reading order within every band.
- Stylesheet passes the sanitizer with no dropped rules.
