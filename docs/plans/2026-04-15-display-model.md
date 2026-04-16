# Adventure Guide: Display Model Design

Date: 2026-04-15

This document defines the intended behavior for every surface of the mod and
the architectural decisions required to implement it cleanly.
No code changes are made until this document is approved.

---

## 1. The architectural problem

The codebase currently has **two parallel pipelines** for implicit quests:

1. Standard: `QuestPhaseTracker` → `EffectiveFrontier` → resolvers → tracker/NAV/markers
2. Separate: `_implicitlyAvailableQuests` → `EmitImplicitCompletionMarkers`

These pipelines interact badly and require implicit-quest special-casing in
`EffectiveFrontier`, `TrackerSummaryBuilder`, and `ViewRenderer`. The root
cause is that `QuestPhaseTracker` places implicit quests in `ReadyToAccept`
(waiting for the player to "accept" them), but implicit quests can never be
accepted — so the standard pipeline produces wrong output for them and hacks
are layered on top.

**The fix belongs in exactly one place: `QuestPhaseTracker`.**

Implicit quests have no acceptance step. They skip `ReadyToAccept` and go
directly to `Accepted` when their prerequisites are satisfied. After that
single change, the entire resolution pipeline handles implicit quests
correctly without any special-casing: `EffectiveFrontier` sees `Accepted`
and resolves objectives; `TrackerSummaryBuilder` calls `BuildAccepted` and
shows the right text; `SourceResolver` emits completion targets.

**Why this is safe for markers:** `MarkerComputer.RebuildQuestMarkers` calls
`_tracker.IsActive(dbName)`, which reads `_activeQuests` — the game journal.
Implicit quests never appear in the journal. Changing the phase tracker has
zero effect on marker behavior. The existing marker paths remain correct:
- Tracked or NAV-ed → full frontier markers (via `EmitActiveQuestMarkers`)
- Untracked, in zone → turn-in markers only (via `EmitImplicitCompletionMarkers`)
- Untracked, out of zone → no markers

---

## 2. Quest classifications

| Class | Definition |
|---|---|
| **Explicit** | Has a quest giver. Player must formally accept. Appears in the game journal when active. |
| **Implicit** | No quest giver. Completable without formal acceptance. Never in the journal. 71/174 quests. |
| **Repeatable** | Either class, resets after completion. |

---

## 3. Actionability states

The mod exposes one axis: what can the player do?

| State | Meaning |
|---|---|
| **Completed** | Done |
| **Active** | Formally accepted, in the game journal |
| **Available** | Can be progressed but needs travel or a prior step |

The `[COMPLETABLE]` badge is dropped. `IsImplicitlyAvailable` (completion
target in current scene) drives the **teal color** only — a proximity hint,
not a completion guarantee. Teal + `[AVAILABLE]` = "something for this quest
is here." Plain + `[AVAILABLE]` = "you can work on this elsewhere."

---

## 4. Surface-by-surface behavior

### 4.1 Quest list panel

| Filter | Includes |
|---|---|
| Active | Formally accepted (journal) — explicit only |
| Available | Not active AND not completed — both explicit-not-yet-accepted AND all implicit |
| Completed | Completed |
| All | Everything |

**Entry color:**
- `IsImplicitlyAvailable` → teal
- Active → yellow
- Completed → green
- Otherwise → default

**Tooltip:**
- `IsImplicitlyAvailable` → "Completable here"
- Active → "Active"
- Completed → "Completed"
- Otherwise → "Available"

### 4.2 Guide window status badge

| State | Badge | Color |
|---|---|---|
| Completed | `[COMPLETED]` | green |
| Active | `[ACTIVE]` | yellow |
| `IsImplicitlyAvailable` | `[AVAILABLE]` + teal | teal |
| Default | `[AVAILABLE]` | secondary text |

`[COMPLETABLE]` is removed. `[NOT STARTED]` is removed.
The badge change is one line: `default: badge = "[AVAILABLE]"`.
The teal color is preserved via the `QuestImplicitlyAvailable` case, but it
now shows `[AVAILABLE]` text instead of `[COMPLETABLE]`.

### 4.3 Tracker overlay subtitle

The subtitle shows the most actionable next step.

| Phase | Subtitle |
|---|---|
| Accepted (explicit or implicit) | Item progress → step objective → "Turn in to {name}" |
| ReadyToAccept (explicit only, after fix) | "Talk to {giver}" |
| Completed | "Completed" |

After the `QuestPhaseTracker` fix, implicit quests are always in `Accepted`
phase when their prerequisites are met, so they use the Accepted path.
The EffectiveFrontier hack (my broken earlier commit) is reverted.

### 4.4 World markers

The existing three-path marker behavior is correct: tracked/NAV-ed → full
markers, in-zone untracked → turn-in only, otherwise none.

**Disabled NPC respawn timer suppression (Erenshor-qhi):**
Both `CreateRespawnTimerEntry` overloads (lines 269 and 336) only skip markers
for `SpawnAlive` but fall through for all other non-dead states. This creates
wrong markers for two cases:

- **`SpawnUnlockBlocked`** (quest-gated NPC): produces a timer showing "0s".
  The correct `QuestLocked` marker with the unlock reason already comes from
  `CreateCharacterMarkerEntry` → `ResolveCharacterPresentation` (line 863).
  The respawn timer is a wrong duplicate.
- **`SpawnDisabled`** (generically disabled NPC): produces a "Re-enter zone"
  hint or "0s" timer. `CreateCharacterMarkerEntry` already returns null for
  this state (line 783). No useful info to show.

**Fix:** Add `if (info.State is SpawnDisabled or SpawnUnlockBlocked) return null;`
immediately after the existing `SpawnAlive` check in both overloads. Respawn
timers only make sense for `SpawnDead` (with a real timer) and
`SpawnNightLocked` (a time-based gate). All other non-alive states should
not produce a respawn timer marker.

The quest-locked NPC's unlock requirement is displayed by the *character*
marker path (`CreateActiveMarkerEntry` → `CreateCharacterMarkerEntry` →
`ResolveCharacterPresentation` → `MarkerType.QuestLocked`), which is
unaffected by this change.

### 4.5 NAV zone line lock display (Erenshor-1cg)

`ZoneRouter.FindRoute` already falls back to locked routes when no accessible
path exists (`BFS(accessibleOnly: false)`). The `Route.IsLocked` flag is set,
and `FindFirstLockedHop` identifies the blocking zone line. But
`NavigationEngine.SetTarget` does not propagate lock info to the explanation.

**Fix in `NavigationEngine.SetTarget`:** After setting `EffectiveTarget` and
`HopCount` from the locked route, check `route.IsLocked`. If locked:
1. Call `_router.FindFirstLockedHop(CurrentScene, target.Scene!)` to get the
   first locked zone line.
2. Call `_unlocks.GetRequirementReason(lockedHop.ZoneLineKey)` to get the
   human-readable reason (e.g., "Requires: Meet the Fisherman, Angler's Ring").
3. Replace the explanation's tertiary text with the lock reason.

Both `_router` (ZoneRouter) and `_unlocks` (UnlockEvaluator) are already
injected into NavigationEngine. No new dependencies.

The NAV arrow points to the locked zone line position (already works). The
explanation now tells the player what quests to complete first. The rendering
path does not change — it already displays tertiary text.

---

## 5. Detail tree — label consistency

All action labels use the natural verb phrase form with no colon.
The colon is reserved for source-type labels (§5.2) where it introduces a
category, not an instruction.

### 5.1 Step labels (`StepLabels.Format`)

| Type | Label |
|---|---|
| STEP_TALK | `Talk to {name}` |
| STEP_KILL | `Kill {name}` |
| STEP_TRAVEL | `Travel to {name}` |
| STEP_SHOUT | `Shout near {name}` |
| STEP_READ | `Read {name}` |

### 5.2 Completer labels

| Target type | Label |
|---|---|
| Character, no keyword | `Turn in to {name}` |
| Character, with keyword | `Turn in to {name} — say "{keyword}"` |
| Item | `Read {name}` |
| Zone | `Enter {name}` |
| ZoneLine | `Travel to {name}` |
| Quest | `Complete {name}` |

### 5.3 Giver labels

| Condition | Label |
|---|---|
| No keyword | `Talk to {name}` |
| With keyword | `Talk to {name} — say "{keyword}"` |

### 5.4 Item source labels (`FormatSourceLabel`)

Source labels use the `Category: {name}` form — they name the source type,
not the player action. Consistent within this category:

| Edge type | Label |
|---|---|
| DropsItem | `Drops from: {name}` |
| SellsItem | `Vendor: {name}` |
| GivesItem, no keyword | `Talk to {name}` |
| GivesItem, with keyword | `Talk to {name} — say "{keyword}"` |
| Contains | `Collect from: {name}` |
| YieldsItem (mine) | `Mine at: {name}` |
| YieldsItem (water) | `Fish at: {name}` |
| Produces | `Crafted via: {name}` |

Note: GivesItem uses the instruction form (not `Category: {name}`) because
the player must perform a specific action to obtain the item.

### 5.5 Unlock condition labels

| Condition | Label |
|---|---|
| Quest (check_type=0) | `Requires: {quest name}` |
| Item (check_type=1) | `Requires: {item name}` |

9 door-type unlock conditions exist in the data. Every door has a
`key_item_key` referencing the item needed to open it. The fix is at compile
time: when the unlock condition source is a door node, the compiler resolves
the door's `key_item_key` to the key item's node_id and emits
`check_type=1` (item possession) with the key item as the source. After
recompilation, no door nodes appear as unlock condition sources — they become
ordinary item-possession checks. The label becomes `Requires: {key item name}`
(e.g., "Requires: Dockhouse Key") and evaluation uses the existing
`FindItemIndex` + `GetItemCount > 0` path. No C# changes needed.

Doors without a `key_item_key` (none exist in the current data) would keep
`check_type=0` and evaluate as blocked — the safe default for unmodeled gating.

---

## 6. Detail tree — node expansion

**Current state:** Only `SpecTreeKind.Item` nodes expand (via `GetChildren`).
All other kinds return empty. Unlock conditions are separately expandable via
`GetUnlockChildren` for any node with a predicate.

**Required:** Prerequisite nodes must expand to show the prerequisite quest's
full requirement tree. This lets players traverse the full dependency chain
and understand what they need to complete before the current quest becomes
available.

`GetChildren` for `SpecTreeKind.Prerequisite`: call
`GetRootChildren(prereqQuestIndex)` where `prereqQuestIndex` is derived from
`FindQuestIndex(parent.NodeId)`.

Other kinds (`Giver`, `Completer`, `Step`, `Source`) already expose their
unlock requirements via `GetUnlockChildren`. No additional child expansion
is needed for those kinds beyond what `GetUnlockChildren` provides.

---

## 7. GivesItem keyword gap

When a `GivesItem` edge has a keyword (player must say a phrase), the keyword
is stripped at the compiler stage and the label shows `Talk to {name}` instead
of `Talk to {name} — say "{keyword}"`.

**Three-layer fix:**
1. `compiler.py`: add `keyword: str | None = None` to `SourceSite`; copy
   `edge.keyword` for GivesItem edges in `_compile_item_sources`.
2. `CompiledGuide.cs`: add `string? Keyword` to `SourceSiteEntry`; load from JSON.
3. `SpecTreeProjector.FormatSourceLabel`: pass `source.Keyword` instead of
   `null` to `FormatKeywordLabel` for `EdgeGivesItem`.

---

## 8. Code changes summary

| # | File(s) | Change |
|---|---|---|
| A | `QuestPhaseTracker.cs` | Implicit quests skip ReadyToAccept → go directly to Accepted |
| B | `EffectiveFrontier.cs` | Revert the earlier implicit-quest guard (the phase tracker fix makes it unnecessary) |
| C | `EffectiveFrontierTests.cs` | Update the two implicit-quest tests to expect Accepted-phase entries |
| D | `ViewRenderer.cs` | `[NOT STARTED]` → `[AVAILABLE]`; `[COMPLETABLE]` → `[AVAILABLE]` (teal color kept) |
| E | `StepLabels.cs` | Standardize Kill/Travel/Read labels to no-colon form |
| F | `SpecTreeProjector.cs` | Fix completer labels (colon removal); add Prerequisite expansion in GetChildren; pass keyword for GivesItem |
| G | `compiler.py` | Add keyword to SourceSite; populate from GivesItem edges; resolve door unlock conditions to key-item possession checks |
| H | `CompiledGuide.cs` | Add Keyword to SourceSiteEntry |
| I | `MarkerComputer.cs` | Suppress respawn timer markers for `SpawnDisabled` in both `CreateRespawnTimerEntry` overloads |
| J | `NavigationEngine.cs` | Annotate NAV explanation with zone line lock reason when route goes through locked zone line |

---

## 9. Out of scope

- Quest target explosion (Erenshor-zf8) — deferred
