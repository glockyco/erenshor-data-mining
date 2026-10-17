# Proposal

## Why

Spell and skill pages share the legacy Ability infobox, which copies data into articles, hides several generated fields and classifies both types only as Abilities. Convert their game-backed roots after stances while preserving exact identities, editorial text and the existing inline tooltip surface.

## What Changes

- Add `Template:AbilityData` for explicit spell or skill stable keys. Keep `Template:Ability` a compatible parameter-only renderer.
- Reuse immutable `Data/Spells` and `Data/Skills` schemas, their existing typed relationships and their native tooltips. Publish recorded lifecycle metadata separately.
- Render complete visitor-relevant facts, including useful fields the old infobox hides, with distinct spell and skill labels and categories.
- Establish `imagecaption` as an editor-owned presentation field, seeded from the existing caption at conversion. Data remains authoritative for every game fact.
- Convert all game-backed stable-key roots with shared guarded comparison, canary, rollback and broad-approval machinery. Keep handwritten or identity-less legacy pages intact rather than guessing a replacement identity.
- Preserve exactly one keyed inline tooltip per converted entity and existing hover behavior. Add no right-click details interaction.
- Switch converted types to new compact stubs and membership-only reconciliation, then remove only spell/skill full-article generation that no longer serves conversion or rollback.

## Capabilities

### New Capabilities

- `data-backed-abilities`: Spell and skill article rendering, identity-specific hover compatibility, preserved editorial presentation and reversible conversion.

### Modified Capabilities

None. Legacy refresh and lifecycle requirements remain applicable to their existing roots and recorded dispositions.

## Impact

Changes maintained spell/skill renderer entry points, a new AbilityData wrapper and styles, lifecycle data publication, entity page composition and local parser/browser coverage. The parent owns shared conversion primitives and native guarded deploy/rollback. No replacement source selectors, Lua queries, Cargo storage, new facts inferred from article names, or changes to item details interactions are included. Planning alone authorizes no live writes.
