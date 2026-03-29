# Adventure Guide nav target persistence

## Planned commits

1. `fix(mod): persist selected guide targets immediately`
   Audit how AdventureGuide stores current navigation and tracking targets in
   config, then write config updates at the moment the user selects or clears a
   target so crashes cannot silently discard the latest choice.

## Acceptance

- Selecting a navigation target writes the current navigation selection to the
  AdventureGuide config immediately.
- Selecting a tracking target writes the current tracking selection to the
  AdventureGuide config immediately.
- Clearing either target also persists immediately so restored state matches
  the last user action.
- No code path depends on a later shutdown or periodic save to preserve the
  current target selection.
