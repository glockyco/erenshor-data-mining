---
title: Website Redesign (non-map surfaces)
type: spec
status: superseded
created: 2026-06-19
superseded_by: 2026-06-25-landing-redesign-design
archived: 2026-06-25
---

# Erenshor Community Tools Website Redesign Specification

**Date:** 2026-06-19
**Status:** Superseded by `2026-06-25-landing-redesign-design` (archived 2026-06-25)
**Scope:** Full structural and visual redesign for the non-interactive-map website surfaces in `src/maps`, while keeping the interactive map applications themselves unchanged.

---

## 1. Problem

The website has grown page-by-page. Each route works in isolation, but the site now feels like a set of ad-hoc pages rather than one product:

- `/` is really a world-map preview, not a site home.
- `/mod` is an image-led companion-mod page, but only covers World Map Companion and Zone Maps Companion.
- `/adventure-guide` is a strong visual product page, but its install copy is stale and still points users through Thunderstore/BepInEx-first setup.
- `/spreadsheet` has a different voice and visual language from the rest of the site.
- `/zone-maps` is a legacy index but still gets primary navigation weight.
- The nav is a centered tab strip with no site identity, no footer, no external ecosystem links, and no clear distinction between current tools, legacy tools, data, and mods.
- Sprint and JusticeForF7 are published mods, but the website has no catalog entries, no pages, and no media for them.

The redesign should make the site feel intentional: one maintained Erenshor tool hub with maps, mods, guides, and data. It must still protect the map apps from churn.

---

## 2. Hard boundary

Do not redesign the interactive map applications:

- Leave `src/maps/src/routes/map/+page.svelte` structurally unchanged.
- Leave `src/maps/src/routes/[mapName]/+page.svelte` and `src/maps/src/routes/[mapName]/+page.ts` structurally unchanged.
- Do not change map controls, marker UI, deck/Leaflet behavior, zone rendering, or live tracking behavior as part of this redesign.

Shell rule:

- Redesign the `(app)` marketing/support shell only: `src/maps/src/routes/(app)/+layout.svelte` and its child pages.
- Do not move major visual chrome into root `src/maps/src/routes/+layout.svelte`, because that root wraps the interactive map pages too.
- Links from the redesigned shell can point to `/map` and `/{mapName}`, but the destination map surfaces keep their current full-screen/runtime layouts.

---

## 3. Product decision

Build a non-map site shell around three jobs:

1. **Use a tool** — open the world map, legacy zone maps, spreadsheets, or guide pages.
2. **Choose a mod** — understand what each mod does visually and pick the right install channel.
3. **Trust the ecosystem** — see clear links to Lunaris, Erenshor Vault, Thunderstore, and project-maintained pages.

Design register: **product/tool**. Personality: **practical expert**. Tone: specific, direct, no hype.

Visual strategy: **image-led product UI**. The screenshots/GIFs carry the delight; the interface stays restrained, dark, readable, and consistent.

---

## 4. Current route inventory

| Route | Current role | Redesign decision |
|---|---|---|
| `/` | World map preview card. | Convert to site home / tool hub. Keep world map as the primary CTA, not the entire page. |
| `/map` | Interactive world map app. | Excluded. Link to it; do not redesign it. |
| `/zone-maps` | Legacy zone-map index. | Keep, but frame as legacy/secondary. Use the shared non-map shell. |
| `/{mapName}` | Individual interactive zone map pages. | Excluded. Do not redesign. |
| `/mod` | Companion mod gallery plus stale BepInEx-first setup. | Redesign as the full mod catalog for four mod groups. Visual first, install channels second. |
| `/adventure-guide` | Dedicated Adventure Guide product page. | Keep as detail page, align it with the new shell, and replace stale install copy with Lunaris-first guidance. |
| `/spreadsheet` | Google Sheets landing with tab links. | Redesign as a data/reference page with grouped links and consistent tone. |
| `/wiki-bot` | Not present. Wiki automation exists only as CLI/backend code. | Add a public trust/explainer page for **WoWBot**, the wiki update bot account, and the data deployment workflow. |

---

## 5. Proposed site structure

### 5.1 Primary navigation

Replace the current equal tab strip with a real site header inside `(app)/+layout.svelte`.

Recommended primary nav:

| Label | Path | Reason |
|---|---|---|
| Home | `/` | Site hub, not just map preview. |
| World Map | `/map` | Highest-value tool; direct jump into the app. |
| Mods | `/mod` | Full mod catalog and install-channel guidance. |
| Data | `/spreadsheet` | Google Sheets/reference data. |
| WoWBot | `/wiki-bot` | Explains generated wiki updates and builds trust in automated data pages. |

Secondary links live in page content and footer:

| Label | Path / URL | Placement |
|---|---|---|
| Legacy Zone Maps | `/zone-maps` | Home card, footer, and World Map cross-link. Not primary nav. |
| Adventure Guide | `/adventure-guide` | Featured from Home and Mods; not a top-level duplicate nav item. |
| Lunaris GitHub | `https://github.com/MizukiBelhi/Lunaris` | Header utility or footer ecosystem link; Mods install strip. |
| Erenshor Vault | `https://erenshorvault.app/` | Footer ecosystem link; Mods ecosystem strip. |
| Adventure Guide on Vault | `https://erenshorvault.app/mod/adventure-guide` | Adventure Guide card/detail page. |
| Thunderstore WoW_Much | `https://thunderstore.io/c/erenshor/p/WoW_Much/` | Footer ecosystem link; Mods install strip. |

Why Adventure Guide leaves primary nav: it is a mod detail page, not a separate product family beside Mods. Keep the page, but link it from Home and `/mod` where the user is already choosing tools/mods.

Why Zone Maps leaves primary nav: it is explicitly legacy. Make it discoverable without putting it on equal footing with the current world map.

### 5.2 Header shape

Use a restrained product header, not the current floating pill tab bar.

Desktop:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Erenshor Tools   Home   World Map   Mods   Data   WoWBot   Lunaris ↗      │
└────────────────────────────────────────────────────────────────────────────┘
```

Mobile:

```text
┌─────────────────────────────────────┐
│ Erenshor Tools                 Menu │
└─────────────────────────────────────┘
```

Requirements:

- Header belongs only to `(app)` pages.
- Active state is a solid/tinted pill or underline, not a full gradient tab.
- External header utility should be one link at most. Prefer `Lunaris ↗` because install confusion is the current user risk.
- Footer carries the broader ecosystem link set.

### 5.3 Footer shape

Add a simple footer to `(app)/+layout.svelte`:

```text
Erenshor Community Tools
Maps, mods, guide data, wiki automation, and references for Erenshor.

Tools: World Map · Mods · Data · WoWBot · Legacy Zone Maps
Ecosystem: Lunaris GitHub · Erenshor Vault · Thunderstore · Adventure Guide on Vault
```

Footer must not appear inside `/map` or individual zone-map app pages.

---

## 6. Page-level design

### 6.1 Home (`/`)

Goal: make `/` the site hub.

Structure:

1. **Hero:** "Erenshor Community Tools" with concise product copy.
2. **Primary visual:** current world-map screenshot using `/world-map-preview.webp`.
3. **Primary CTA:** `Open World Map` → `/map`.
4. **Secondary CTA:** `Browse Mods` → `/mod`.
5. **Tool grid:** five concise entries:
   - World Map
   - Mods
   - Data Spreadsheet
   - WoWBot
   - Legacy Zone Maps
6. **Featured mod strip:** Adventure Guide + Interactive Map Companion, using real screenshots.
7. **Ecosystem strip:** Lunaris, Erenshor Vault, Thunderstore.
8. **Trust strip:** WoWBot, data freshness, and generated wiki coverage.

Home should not become a long marketing page. It routes users quickly.

### 6.2 Mods (`/mod`)

Goal: full mod catalog for four mod groups.

Top-level mod groups:

| Group | Contains | Primary page treatment |
|---|---|---|
| Adventure Guide | Adventure Guide | Featured visual card with screenshots and Lunaris-first install. |
| Interactive Map Companion | World Map Companion + Zone Maps Companion legacy variant | One family card with variant rows. World Map is current; Zone Maps is legacy. |
| Sprint | Sprint | Utility mod card; needs captured media. |
| JusticeForF7 | JusticeForF7 | Utility mod card; needs captured before/after media. |

Do not present the Interactive Map Companion variants as unrelated top-level products. Show them as one mod family with two variants:

```text
Interactive Map Companion
Live tracking for Erenshor maps.

Current: World Map Companion
- Tracks player, NPCs, enemies, and pets on the interactive world map.
- Install on Thunderstore.

Legacy: Zone Maps Companion
- Tracks player location on legacy per-zone maps.
- Website-only legacy availability.
```

Install channels are card actions, not the page's main structure.

Card actions:

| Mod group | Primary action | Secondary action |
|---|---|---|
| Adventure Guide | Install with Lunaris | View on Erenshor Vault; Thunderstore fallback |
| Interactive Map Companion | Install World Map Companion on Thunderstore | Open World Map; show legacy Zone Maps status |
| Sprint | Install on Thunderstore | Media capture pending until screenshot/clip exists |
| JusticeForF7 | Install on Thunderstore | Media capture pending until before/after images exist |

Required links:

- Lunaris GitHub: `https://github.com/MizukiBelhi/Lunaris`
- Erenshor Vault root: `https://erenshorvault.app/`
- Adventure Guide on Vault: `https://erenshorvault.app/mod/adventure-guide`
- Adventure Guide on Thunderstore: `https://thunderstore.io/c/erenshor/p/WoW_Much/AdventureGuide/`
- World Map Companion on Thunderstore: `https://thunderstore.io/c/erenshor/p/WoW_Much/InteractiveMapCompanion/`
- Sprint on Thunderstore: `https://thunderstore.io/c/erenshor/p/WoW_Much/Sprint/`
- JusticeForF7 on Thunderstore: `https://thunderstore.io/c/erenshor/p/WoW_Much/JusticeForF7/`
- WoW_Much Thunderstore profile: `https://thunderstore.io/c/erenshor/p/WoW_Much/`

### 6.3 Adventure Guide (`/adventure-guide`)

Goal: keep the strong image-led product page, but align install copy and shell.

Keep:

- `/adventure-guide-window.webp`
- `/adventure-guide-nav.webp`
- `/adventure-guide-markers.webp`
- Detailed feature sections around quest UI, `[NAV]`, item sources, pathing, and world markers.

Change:

- Replace the pinned versioned Thunderstore download URL with channel-aware install actions.
- Primary install: Lunaris Plugin Installer.
- Copy must say the in-game UI uses **Plugin Installer**, **Installed**, and **Available** tabs. Do not say users install "from Erenshor Vault" inside the game UI.
- Add links to Lunaris GitHub and Adventure Guide's Vault web listing.
- Keep Thunderstore as fallback only.
- Remove setup walkthroughs that explain DLL placement or BepInEx folder structure.

### 6.4 Data (`/spreadsheet`)

Goal: make the spreadsheet page consistent with the rest of the product.

Change:

- Rename nav label from `Spreadsheet` to `Data`.
- Page title: `Erenshor Data`.
- Keep the screenshot `/spreadsheet.png`.
- Replace whimsical copy with direct product copy.
- Group direct links into categories instead of one flat emoji grid:
  - Items & Drops
  - Characters & Combat
  - Quests & Dialog
  - World & Travel
  - Resources & Secrets
- Use consistent icon treatment if icons remain. Avoid a mixed emoji style unless the whole design system commits to it.
- Keep the Google Sheet CTA prominent.

### 6.5 Legacy Zone Maps (`/zone-maps`)

Goal: keep the legacy index useful without competing with the current world map.

Change:

- Title: `Legacy Zone Maps`.
- Body copy should say the unified World Map is recommended for current use.
- Keep the zone thumbnail grid; it is useful.
- Add a prominent `Open World Map` action near the top.
- Reduce decorative hover effects that feel different from the rest of the site.

Do not alter individual `/{mapName}` map pages as part of this redesign.

### 6.6 WoWBot (`/wiki-bot`)

Goal: explain the wiki automation without pretending there is a chat bot or live public service. Public name: **WoWBot**. Technical source: `src/erenshor/cli/commands/wiki.py`, where the `erenshor wiki` CLI fetches existing MediaWiki pages, generates content from the clean database, preserves manual wiki fields where configured, and deploys generated pages through the WoWBot MediaWiki bot account.

Trust framing:

- WoWBot account: `https://erenshor.wiki.gg/wiki/User:WoWBot`
- WoWBot contributions: `https://erenshor.wiki.gg/wiki/Special:Contributions/WoWBot`
- Maintainer account: `https://erenshor.wiki.gg/wiki/User:WoWMuch`
- Maintainer contributions: `https://erenshor.wiki.gg/wiki/Special:Contributions/WoWMuch`
- Copy may state that WoWBot is maintained by WoWMuch, an Erenshor Wiki administrator, but the tone should be operational and factual rather than self-promotional.

Structure:

1. **Hero:** `WoWBot` with a short trust statement: generated Erenshor wiki data, reviewed and deployed by a dedicated bot account from the same extraction pipeline that powers maps and sheets.
2. **Workflow diagram:** `Extract game data → Build clean database → Fetch wiki pages → Generate updates → Review diffs → Deploy as WoWBot`.
3. **What it updates:** items, characters, abilities/spells/skills, stances, zones, and generated overview pages where supported.
4. **What it preserves:** manual wiki notes/overrides, categories, and intentionally curated content when the preservation rules apply.
5. **Safety notes:** generated files are local first, deployment is explicit, edits are attributable to WoWBot's contribution history, and Cargo table declaration changes require human table recreation/switch-in.
6. **Links:** Erenshor Wiki, WoWBot profile, WoWBot contributions, WoWMuch profile, WoWMuch contributions, Data page, and source/context links only if intended for users.

Visual treatment:

- Use the same dark product shell, but make this page more diagram-led than screenshot-led.
- A compact pipeline diagram or stepped process panel is more useful than a generic bot mascot.
- If an illustration is desired later, use an automation/data motif: database cylinder, diff document, wiki page, upload arrow. Avoid cute robot art unless the whole site adopts that brand voice.

---

## 7. Mod catalog content model

The current `src/maps/static/mods-metadata.json` lists only World Map Companion and Zone Maps Companion. Replace it with a media-aware catalog that can represent all four mod groups and the Interactive Map Companion variants.

Suggested shape:

```ts
type ModGroupId = 'adventure-guide' | 'interactive-map-companion' | 'sprint' | 'justice-for-f7';
type ModVariantStatus = 'current' | 'legacy';
type InstallChannelType = 'lunaris' | 'vault' | 'thunderstore' | 'websiteLegacy';
type InstallChannelStatus = 'recommended' | 'fallback' | 'primary' | 'legacy';
type MediaKind = 'image' | 'video';
type MediaStatus = 'available' | 'needed';

interface ModMedia {
    src?: string;
    kind: MediaKind;
    status: MediaStatus;
    alt: string;
    role: 'icon' | 'primary' | 'supporting' | 'before' | 'after' | 'poster';
    captureBrief?: string;
}

interface InstallChannel {
    type: InstallChannelType;
    status: InstallChannelStatus;
    label: string;
    href?: string;
    note?: string;
}

interface ModVariant {
    id: string;
    displayName: string;
    status: ModVariantStatus;
    summary: string;
    features: string[];
    media: ModMedia[];
    channels: InstallChannel[];
}

interface ModGroup {
    id: ModGroupId;
    displayName: string;
    summary: string;
    category: 'guide' | 'map' | 'movement' | 'screenshots';
    featured: boolean;
    variants: ModVariant[];
}
```

Initial catalog facts:

| Group | Variant(s) | Media | Install channels |
|---|---|---|---|
| Adventure Guide | Adventure Guide | Available: `adventure-guide-window.webp`, `adventure-guide-nav.webp`, `adventure-guide-markers.webp`, `og-adventure-guide.png`; source icon: `src/mods/AdventureGuide/vault/icon.png` | Recommended: Lunaris. Web listing: Erenshor Vault. Fallback: Thunderstore. Vault version observed: `v2026.618.1`. |
| Interactive Map Companion | World Map Companion | Available: `world-map-preview.webp`, `world-map-companion.mp4`, `world-map-companion.gif`; source icon: `src/mods/InteractiveMapCompanion/thunderstore/icon.png` | Primary public package: Thunderstore. Link to `/map`. |
| Interactive Map Companion | Zone Maps Companion | Available: `zone-maps-companion.gif` | Legacy website-only status. Link to `/zone-maps` if retained. |
| Sprint | Sprint | Interim icon: `src/mods/Sprint/thunderstore/icon.png`; needed: sprint in-game media | Primary public package: Thunderstore. Thunderstore version observed: `2026.217.0`. |
| JusticeForF7 | JusticeForF7 | Interim icon: `src/mods/JusticeForF7/thunderstore/icon.png`; needed: before/after media | Primary public package: Thunderstore. Thunderstore version observed: `2026.217.0`. |

---

## 8. Media plan

Do not fake screenshots. If Sprint or JusticeForF7 media is unavailable, the implementation should either capture it before launch or mark the card as intentionally text/icon-led with a visible media backlog in the plan, not in public UI.

Existing mod icons are intentional interim media, not broken fallbacks. Sprint's pixel-art icon can carry an early utility card while capture media is produced. JusticeForF7's F7-key icon can anchor the card, but the polished launch still needs before/after imagery because the mod's value proposition is visual cleanliness.

Icon integration:

- Each mod card should have a small icon lockup in the header: 40-56px icon, mod name, status badge, and install-channel badge.
- Featured cards still lead with screenshots/video; icons add identity and help users scan the catalog.
- Utility cards without screenshot media can use the icon as the primary visual temporarily, but they should look intentional: centered icon tile, concise feature copy, and a `Media capture planned` implementation note only in developer docs, not public UI.
- Prefer copying published icons into `src/maps/static/mod-icons/` or generating that directory from `src/mods/*/{thunderstore,vault}/icon.png` so the website does not depend on source-package paths at runtime.

### 8.1 Sprint media brief

Needed assets:

- `/sprint-preview.webp`
- Optional `/sprint-demo.mp4`

Recommended capture:

- A readable in-game path/road scene.
- Same character moving with sprint enabled.
- Visual emphasis on speed without UI clutter.
- If video: 4-8 seconds, loopable, no rapid camera movement.
- If still: show a clear running pose and caption the value: `Hold Shift to move faster`.

Card copy:

```text
Sprint
Hold Shift, or your configured key, to run faster. No stamina system, no cooldowns, just movement speed that respects existing buffs and debuffs.
```

### 8.2 JusticeForF7 media brief

Needed assets:

- `/justice-for-f7-before.webp`
- `/justice-for-f7-after.webp`
- Optional `/justice-for-f7-comparison.mp4`

Recommended capture:

- Same camera angle before and after pressing F7.
- Before: nameplates, damage numbers, cast bars, target rings, or loot prompts visible.
- After: clean scene with those world-space UI elements hidden.
- Best treatment: side-by-side before/after comparison or draggable comparison if implemented accessibly.

Card copy:

```text
Justice for F7
Press F7 for truly clean screenshots. Extends Hide UI to remove nameplates, damage numbers, target rings, XP orbs, cast bars, loot prompts, and other world-space text.
```

---

## 9. Visual design system

### 9.1 Scene sentence

Players use this site while playing Erenshor or preparing a play session, usually with the game, mod manager, Discord, or a browser tab already open. The UI should feel like a reliable companion dashboard: dark, legible, media-rich, and fast to scan.

### 9.2 Color and tone

Keep the dark slate base because it matches the current map/tool experience and supports screenshots well.

Token direction:

| Role | Tailwind direction | Use |
|---|---|---|
| Page background | `slate-950` | All non-map pages. |
| Primary panel | `slate-900` + `slate-700` border | Hero media, featured cards. |
| Secondary panel | `slate-800/70` | Supporting cards, footer, data groups. |
| Body text | `slate-300` | Main prose. |
| Muted text | `slate-400` only where contrast passes | Helper copy. |
| Headings | `slate-100` / `white` | Page and section headings. |
| Primary action | purple-to-pink gradient or solid purple | Existing brand accent, used sparingly. |
| Recommended | emerald | Lunaris/current/recommended states. |
| Fallback | amber | Thunderstore fallback / alternate path. |
| Legacy | slate | Zone Maps legacy state. |

Do not use gradient text. Do not add parchment/cream fantasy styling. Images supply the game texture.

### 9.3 Typography

- Keep one sans-serif/system stack unless the project intentionally adds a type system later.
- Product pages should use a tighter scale than marketing pages.
- Body line length: 65-75ch.
- Use `text-wrap: balance` for `h1`/`h2` where supported.
- Avoid tiny uppercase section kickers as repeated scaffolding.

### 9.4 Components to standardize

Create or converge on shared components under `src/maps/src/lib/components/site/`:

| Component | Purpose |
|---|---|
| `SiteHeader.svelte` | Non-map header/nav only. |
| `SiteFooter.svelte` | Ecosystem links and secondary navigation. |
| `PageHero.svelte` | Consistent page hero with title, body, CTAs, optional media. |
| `MediaCard.svelte` | Image/video card with alt text, status badges, and action strip. |
| `ModCard.svelte` | Catalog card built from mod metadata. |
| `StatusBadge.svelte` | Recommended/fallback/legacy/current states. |
| `ExternalLink.svelte` | Consistent external-link affordance and `rel` handling. |
| `SectionHeader.svelte` | Consistent section title/body rhythm without repeated eyebrow labels. |

No component should be designed around one page's copy. The point is consistency across Home, Mods, Adventure Guide, Data, and Legacy Zone Maps.

### 9.5 Motion

- Keep motion short: 150-250 ms for hover/focus/disclosure.
- Media previews can animate, but must have static fallbacks and respect `prefers-reduced-motion`.
- No orchestrated page-load sequences.
- No hover-only access to essential text/actions.

---

## 10. Structural recommendations

### 10.1 Separate non-map site shell

Use the existing route group boundary:

- Keep full-screen map apps outside `(app)`.
- Redesign only `src/maps/src/routes/(app)/+layout.svelte` for the site header/footer.
- If shared CSS variables are added, ensure they do not break map page layout assumptions.

### 10.2 Data-driven mods page

The Mods page should render from metadata, not hardcoded per-card markup. That keeps channel changes and media additions cheap.

Minimum data fields:

- display name
- summary
- feature list
- media list
- install channels
- status badges
- detail route/link
- category/family

### 10.3 Dedicated pages vs catalog cards

Keep Adventure Guide as the only dedicated mod detail page for now because it already has enough media and configuration depth.

Add WoWBot as a dedicated trust/data-pipeline page. It is not a mod detail page; it explains how generated wiki content is produced, reviewed, and deployed through the dedicated bot account.

Do not add separate pages for Sprint or JusticeForF7 until they have enough media/config content to justify it. The Mods card can carry their core value and Thunderstore link.

Interactive Map Companion should remain a family card unless a future release needs a dedicated guide page.

---

## 11. SEO and metadata

Update route metadata to match the new structure:

| Route | Title direction | Description direction |
|---|---|---|
| `/` | `Erenshor Community Tools – Maps, Mods, Guides & Data` | Broad hub for maps, mods, Adventure Guide, and spreadsheets. |
| `/mod` | `Erenshor Mods – Adventure Guide, Live Maps, Sprint & F7 Screenshots` | Full mod catalog with Lunaris, Erenshor Vault, and Thunderstore install paths. |
| `/adventure-guide` | `Erenshor Adventure Guide – Quest Companion Mod` | Keep feature-rich quest companion description, but mention Lunaris install. |
| `/spreadsheet` | `Erenshor Data – Items, Drops, Quests & Spawns` | Reference data extracted from game files. |
| `/zone-maps` | `Erenshor Legacy Zone Maps` | Legacy per-zone maps with current World Map recommendation. |
| `/wiki-bot` | `Erenshor WoWBot – Generated Wiki Data Pipeline` | Explains fetch/generate/review/deploy workflow, generated wiki coverage, bot-account attribution, and manual-content preservation. |

Breadcrumb JSON-LD should keep matching visible route labels.

---

## 12. Implementation scope

Expected files:

- `src/maps/src/routes/(app)/+layout.svelte`
  - Replace centered tab strip with non-map site header and footer.
  - Keep shell scoped to `(app)` only.
- `src/maps/src/routes/(app)/+page.svelte`
  - Convert from world-map-only landing to site home/tool hub.
- `src/maps/src/routes/(app)/wiki-bot/+page.svelte`
  - Create the WoWBot trust page with workflow diagram, coverage, preservation, safety notes, contribution links, and maintainer context.
- `src/maps/src/routes/(app)/mod/+page.svelte`
  - Render full mod catalog for Adventure Guide, Interactive Map Companion, Sprint, and JusticeForF7.
  - Use media/channel metadata and image-led cards.
- `src/maps/src/routes/(app)/mod/+page.server.ts`
  - Load updated catalog shape.
- `src/maps/static/mods-metadata.json`
  - Replace two-entry metadata with four mod groups and Interactive Map Companion variants.
- `src/mods/mods-config.yaml`
  - Update the upstream mod metadata source if the publish/generation pipeline still derives `mods-metadata.json` from it.
  - Add Sprint and JusticeForF7 entries so regenerated metadata does not drop them.
- `src/maps/src/routes/(app)/adventure-guide/+page.svelte`
  - Align with new design system and Lunaris-first install copy.
  - Remove pinned versioned Thunderstore URL from public CTAs.
- `src/maps/src/routes/(app)/spreadsheet/+page.svelte`
  - Convert to consistent Data page with grouped sheet links.
- `src/maps/src/routes/(app)/zone-maps/+page.svelte`
  - Align legacy index with new shell and copy.
- `src/maps/src/lib/components/site/*.svelte`
  - Add shared site components as needed, including media cards, status badges, page heroes, external links, and diagram/step components for WoWBot.

Media and icon assets to add before launch if available:

Icon assets to expose through the website:

- `src/maps/static/mod-icons/adventure-guide.png`
- `src/maps/static/mod-icons/interactive-map-companion.png`
- `src/maps/static/mod-icons/sprint.png`
- `src/maps/static/mod-icons/justice-for-f7.png`

- `src/maps/static/sprint-preview.webp`
- `src/maps/static/sprint-demo.mp4` optional
- `src/maps/static/justice-for-f7-before.webp`
- `src/maps/static/justice-for-f7-after.webp`
- `src/maps/static/justice-for-f7-comparison.mp4` optional

Explicit exclusions:

- `src/maps/src/routes/map/+page.svelte`
- `src/maps/src/routes/[mapName]/+page.svelte`
- `src/maps/src/routes/[mapName]/+page.ts`
- Map runtime components under `src/maps/src/lib/components/map/`

---

## 13. Acceptance criteria

1. `/` is a site hub, not only a world-map preview.
2. The non-map shell has consistent header/nav/footer and does not wrap `/map` or `/{mapName}` pages.
3. Primary nav is Home, World Map, Mods, Data, and WoWBot.
4. Legacy Zone Maps and Adventure Guide remain discoverable without being redundant top-level nav items.
5. `/wiki-bot` explains WoWBot honestly as a fetch/generate/review/deploy pipeline, not as a chat-bot feature.
6. `/mod` includes all four mod groups: Adventure Guide, Interactive Map Companion, Sprint, JusticeForF7.
7. Interactive Map Companion is represented as one family with current World Map Companion and legacy Zone Maps Companion variants.
8. `/mod` remains image-led; install channels are secondary action strips/notes.
9. Mod icons appear as consistent card identity elements and Sprint/JusticeForF7 can use their icons as interim media until capture assets exist.
10. Adventure Guide links to Lunaris GitHub, Erenshor Vault, Adventure Guide on Vault, and Thunderstore fallback.
11. Sprint and JusticeForF7 have either real media assets or an implementation-blocking media capture task; they do not ship as empty visual holes.
12. `/adventure-guide` no longer presents stale BepInEx-first setup as the primary install flow.
13. `/spreadsheet` uses a consistent product tone and grouped data links.
14. `/zone-maps` is framed as legacy and points users toward the current World Map.
15. No page includes DLL-placement walkthroughs.
16. Every external link names its destination and uses safe external-link handling.
17. Images/videos/icons have descriptive alt text or equivalent nearby text.
18. Motion respects `prefers-reduced-motion`.
19. The Svelte check and production maps build pass.

---

## 14. Verification plan

Run after implementation:

```bash
pnpm --dir src/maps check
uv run erenshor maps build --force
```

Browser review:

1. Open `/` desktop and mobile; confirm it reads as a site hub and primary CTA opens `/map`.
2. Open `/mod`; confirm four mod groups are present, mod icons are visible, and media hierarchy is clear.
3. Confirm Interactive Map Companion is a family with World Map current and Zone Maps legacy variants.
4. Confirm Sprint and JusticeForF7 use intentional icon-based interim visuals or real captured media, not broken/missing media UI.
5. Confirm Lunaris GitHub and Erenshor Vault links are visible where install/ecosystem context appears.
6. Open `/wiki-bot`; confirm it explains WoWBot, links to the bot and maintainer contribution histories, and presents fetch/generate/review/deploy workflow instead of a chat-bot feature.
7. Open `/adventure-guide`; confirm Lunaris-first install copy and no stale pinned versioned download CTA.
8. Open `/spreadsheet`; confirm grouped data links and consistent tone.
9. Open `/zone-maps`; confirm legacy framing and World Map CTA.
10. Open `/map`; confirm the interactive map app is still full-screen and not wrapped by the new non-map shell.
11. Open one `/{mapName}` page; confirm individual zone map layout is unchanged.
12. Keyboard-tab through every non-map page; confirm visible focus states.
13. Enable reduced-motion preference; confirm media/motion alternatives do not hide content.

---

## 15. Out of scope

- Redesigning `/map` or individual `/{mapName}` map applications.
- Changing map marker behavior, live tracking protocol, or map data loading.
- Building an Erenshor Vault API client.
- Publishing new mod packages.
- Adding dedicated detail pages for Sprint or JusticeForF7 before media and content justify them.
- Creating synthetic screenshots that imply observed in-game behavior.
