# Adventure Guide Angler's Ring nav investigation

## Planned commits

1. `fix(mod): promote actionable subgoals in nested item navigation`
   Make AdventureGuide attribute navigation candidates to the nearest actionable
   item or quest subgoal instead of always keeping the outer requested item as
   the goal. This keeps arrow/nav text truthful for crafting chains like The
   Angler's Ring, where the selected world target may provide an ingredient
   rather than the final crafted item.

## Acceptance

- When navigation for The Angler's Ring resolves to Spark Beetle, the nav goal
  no longer claims Spark Beetle drops Angler's Ring.
- Nested crafting and reward chains use the immediate actionable requirement as
  the nav goal text while still resolving positions from the same pruned view
  tree.
- Build and hot-deploy of AdventureGuide succeed.
