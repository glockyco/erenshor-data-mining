# Adventure Guide marker actionability fix

## Planned commits

1. `fix(mod): derive active quest markers from resolved frontier targets`
   Stop maintaining a parallel marker-only interpretation of active quest state.
   Active quest markers should come from the same pruned frontier and resolved
   actionable subgoals that navigation and tracker now use, so NPC markers do
   not advertise turn-ins or direct quest items before their true prerequisite
   source step is actionable.

## Acceptance

- Liani Bosh no longer shows a turn-in style marker for Angler's Ring while the
  actionable step is still obtaining the mold from her.
- Active quest markers reflect the same actionable subgoal truth as nav and
  tracker for nested crafting and blocker chains.
- AdventureGuide builds and hot-deploys successfully.
