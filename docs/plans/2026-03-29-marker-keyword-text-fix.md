# Adventure Guide marker keyword text fix

## Planned commits

1. `fix(mod): show interaction verbs on actionable markers`
   Keep active markers aligned with resolved actionable targets, but render the
   marker sub-text from the target interaction when that interaction carries
   essential semantics such as a dialog keyword. This ensures markers remain
   truthful and actionable for give-item NPCs like Liani Bosh.

## Acceptance

- Liani Bosh's marker for The Angler's Ring mold no longer says only
  `Collect Mold: Angler's Ring`.
- The marker instead reflects the required interaction semantics, including the
  keyword when the underlying `GIVES_ITEM` edge provides one.
- AdventureGuide builds and hot-deploys successfully.
