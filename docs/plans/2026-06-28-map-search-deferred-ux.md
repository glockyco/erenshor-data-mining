---
title: Map Search — Deferred UX Improvements
type: note
status: draft
created: 2026-06-28
parent: 2026-06-28-map-search-ux-improvements
---

# Map Search — Deferred UX Improvements

Two search-palette improvements researched during the
`2026-06-28-map-search-ux-improvements` design but deferred. Captured here as
backlog so the rationale isn't lost; graduate to a spec when prioritized.

## Per-category empty state

When the user filters to a category (e.g. "Drops") and gets zero results,
show a targeted empty state: "No items match '<query>'" with a hint to try
"All" or another category.

**Why deferred:** the chip counts already signal zero before the user
selects a category, and the generic empty state ("No results found for
'<query>'") is adequate. Targeted copy is a polish layer, not a gap.

## Recent searches

Persist the last 3–5 searches in `localStorage`; show them as quick-pick
rows when the palette opens with an empty query.

**Why deferred:** the palette already opens empty and ready to type, which
is the common path. Recent searches benefit repeat power users hunting the
same item across sessions — useful, but not blocking the core experience.
Documented as a power-user accelerator in command-palette best practices
([Superhuman](https://blog.superhuman.com/how-to-build-a-remarkable-command-palette/)).
