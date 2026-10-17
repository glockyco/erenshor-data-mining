# Spec Delta

## Purpose

Defines how AdventureGuide decides which targets and routes are available from the gate conditions in its data, how it explains and resolves unmet gates, and the reliability and performance it must keep while doing so.

## ADDED Requirements

### Requirement: Availability follows the observable game state

AdventureGuide SHALL evaluate observable availability from mirrored quests, inventory, keyring, room furnishings, stored Planar/rune items and supported account state through one shared evaluator. A key SHALL hold in inventory or keyring. Advisory atoms SHALL be treated as holding. Routing, source choice, markers, panels, tracker and scene resolution SHALL use this same evaluation. Unknown typed state keys SHALL fail rather than read false. Initialization and outcome effects SHALL NOT be interpreted as current-state conjunctions.

#### Scenario: A key moves to the keyring

- **WHEN** the player opens the Island Tomb Ghostly Key door and the game moves the key from the inventory to the keyring
- **THEN** Ghost of Wyland Sercher stays available

#### Scenario: A key is dropped before use

- **WHEN** the player destroys the Dockhouse Key before opening the dockhouse door
- **THEN** Founder becomes unavailable within the frame that follows the inventory change

### Requirement: Advisory atoms guide and never hide

AdventureGuide SHALL NOT hide, skip, or reject a target because of an advisory atom. It SHALL show each advisory atom of the target's condition as a requirement, with navigation to the characters it names.

Transient activation and per-spawn release advice SHALL NOT become fabricated hard completion gates. PietyTrigger's quest guard SHALL describe activation, never imply despawn after quest completion. Actual live-entity withholding SHALL remain separate. Supported persistent account claims SHALL use the common effective-state projection rather than advisory kill history.

#### Scenario: A restored god

- **WHEN** the player navigates to restored Fernalla
- **THEN** navigation leads to her placement
- **AND** the step shows that Fernalla must be defeated first, with navigation to Fernalla

### Requirement: Unavailable targets are not presented as reachable

Navigation, world markers, and source lists SHALL NOT present a target whose condition does not hold as reachable. When a step has available and unavailable targets, the guide SHALL choose among the available ones. When every target of a step is unavailable, the guide SHALL show the step as gated and name what is missing. A target whose condition can no longer hold, because it requires a completed quest to be incomplete, SHALL be shown as no longer available, without guidance.

#### Scenario: A gated quest giver

- **WHEN** Whispers of Wyland is actionable and the player has no Ghostly Key
- **THEN** the guide does not navigate to Ghost of Wyland Sercher
- **AND** it names the Ghostly Key as the missing requirement

#### Scenario: A removed character

- **WHEN** all four Shivering Step keeper quests are complete
- **THEN** no world marker points at the keepers or the first Kio

### Requirement: Navigation leads to what satisfies a gate

When the navigation target or a hop of its route is gated by an observable atom, AdventureGuide SHALL navigate to what satisfies it: the sources of a missing item or key, the current step of a missing quest, or the Reliquary planning table for a missing furnishing. Among the groups of a condition it SHALL choose the group with the fewest unmet atoms, and among equal groups the one whose first requirement is nearest by route. When the requirement is gated itself, it SHALL repeat this choice and SHALL stop with an explanation, without navigation, when no requirement can be reached. The quest panel and tracker SHALL show the next action and immediate unmet requirement on their existing surfaces, with advisory encounter navigation where applicable. Full chains SHALL remain inspectable through diagnostics. No separate guidance HUD or explanation tree SHALL be required.

#### Scenario: Island Tomb through the lighthouse

- **WHEN** the route to Occuphage needs the lighthouse entrance and the player has no Stowaway's Step Lighthouse Key
- **THEN** navigation leads to the key's source and shows that the key opens a door in Stowaway's Step

#### Scenario: Unlock by either of two routes

- **WHEN** the player navigates to a Jaws of Sivakaya target from the Duskenlight Coast without the Nighthollow Candle and without She Sees You
- **THEN** navigation leads to the requirement of the group with fewer unmet atoms and names the other group as an alternative

### Requirement: Source guidance prioritizes the player's next action

An item objective SHALL show one source preview while its picker is collapsed and the actual selected endpoint during navigation. Expanding the picker SHALL NOT repeat its preview above the choices. It SHALL show where to act, time restrictions, combat preparation and level context without standalone percentages or a large empty action column. Fishing and mining levels SHALL be identified as area levels, not skill requirements. Alternative sources SHALL remain accessible in a collapsed picker, including quest rewards, ingredients and item-use workflows. Choosing a source SHALL start navigation for that objective without depending on an already active route. The choice SHALL survive prerequisite navigation and scene refreshes, and SHALL NOT constrain another objective.

Source choice and prerequisite traversal SHALL retain canonical acquisition, actual location, variant, operation and material-slot identities. No-location sources SHALL remain explanatory/non-navigable without fabricated endpoints. Nested recipe, reward and item-use children SHALL retain the original goal and explicit source selection. Operation inputs SHALL appear as timing/preparation/children, not unconditional availability blocks. Output quality SHALL match the requested result.

Top-level choices SHALL group one acquisition in one material-use context while retaining every original source, fact and location identity. Location details SHALL group only physically equivalent endpoints with the same actor and semantic gate context. Only an endpoint's own provenance scope may be rebound after physical equivalence. External scopes, independent gate families, OR groups, time, probability and preparation differences SHALL remain meaningful. Distinct furnished-room slots and different actors sharing a name SHALL remain separate. Selecting an acquisition SHALL evaluate its allowed real members, not pin an arbitrary duplicate placement.

#### Scenario: Browsing does not rewrite tracker guidance

- **WHEN** the player opens or closes the guide or selects another entry while navigating
- **THEN** the tracker retains the same originating quest and next action
- **AND** neither tracking nor navigation changes merely because an entry is visible

#### Scenario: Repeated physical placements

- **WHEN** one acquisition has many placements or two provenance rows describe the same furnished-room location
- **THEN** the picker shows one acquisition choice with optional location details
- **AND** all underlying endpoint identities remain available for eligibility and navigation
- **AND** every distinct room requirement remains visible

#### Scenario: A night-only fishing source

- **WHEN** a player selects a night-only Moongill source during the day
- **THEN** the default guidance names the zone and the night window
- **AND** it does not display an unconditional chance, a zero daytime chance or an expanded list of alternatives
- **AND** source details retain its chance per successful catch

#### Scenario: Changing the selected source

- **WHEN** a player chooses another source with no navigation already active
- **THEN** navigation starts for that source and the displayed summary matches the actual endpoint
- **AND** a gated source leads to its unmet prerequisite rather than presenting the locked target as reachable

#### Scenario: Conditional combat preparation

- **WHEN** a selected drop source requires a per-spawn trade, weather or ward deaths to become vulnerable
- **THEN** the source explains that preparation separately from its loot chance
- **AND** a completed trade quest is not treated as proof that every future spawn is vulnerable
- **AND** distinct required ward placements retain their required count even when they share a character template

### Requirement: Routing excludes unusable zone lines

Cross-zone routing SHALL NOT use a zone line that the data marks unusable, even as a locked fallback. It SHALL prefer a route whose zone lines are available. When every route needs a gated zone line, it SHALL route to the first gated hop and apply the requirement guidance to that hop. When the target's placement names its entrances, the route SHALL enter the target's scene through the entrance with the cheapest route, and that entrance counts as a hop of the route.

Every destination consumer SHALL use central `ZoneGraph.ResolveDestination`, including rebuild, entry selection, placement routes and navigation selection, labels and landing calculations. Static lines SHALL retain their existing destinations. A bound stored-return line SHALL resolve only from a nonempty known live saved zone and finite saved landing. Invalid state SHALL remove it from accessible and locked fallback routes. Serialized Hidden and invented zero landing SHALL never be fallbacks. The existing adjacency lifecycle SHALL rebuild on relevant tracked account, character and scene changes without a second route cache.

#### Scenario: Shivering Step exits

- **WHEN** the player in Shivering Step navigates to a target in Hidden Hills
- **THEN** the route leaves through Stowaway's Step and never through the unusable Shivering Step zone line to Hidden Hills

#### Scenario: Occuphage from Blacksalt Strand

- **WHEN** the player in Blacksalt Strand holds the Stowaway's Step Lighthouse Key and navigates to Occuphage
- **THEN** the route leads through Stowaway's Step to the lighthouse zone line and not to the closer Island Tomb entrance on the beach

### Requirement: Gate evaluation is deterministic and fails safe

The same game state and data SHALL produce the same availability, the same requirement chain, and the same chosen target. An error in evaluating one quest SHALL NOT stop the guide from serving other quests, and SHALL be reported once through the diagnostics. The diagnostics SHALL dump, for a named subject, its condition, the value of each observable atom, and the requirement chain the guide follows.

#### Scenario: Inspecting a gate

- **WHEN** a developer asks the diagnostics about Founder
- **THEN** the dump lists the Dockhouse Key atom, whether the keyring or the inventory satisfies it, and the requirement chain

### Requirement: Gate evaluation meets performance budgets

With twelve tracked quests and one navigated quest, in Stowaway's Step and in Shivering Step, AdventureGuide SHALL meet these budgets on the main variant, measured in the running game. The baseline is the mod built before this change in the same scene and state.

- The average per-frame cost of the guide's update SHALL exceed the baseline by at most 0.1 ms, and its managed allocation per steady frame SHALL NOT exceed the baseline's.
- Over ten quest completions or ten inventory changes, the guide's average work per event SHALL exceed the baseline's average by at most 1 ms, and its slowest event SHALL exceed the baseline's slowest by at most 2 ms. A keyring change SHALL cost no more than an inventory change.
- A scene load SHALL spend at most 20 ms more in the guide than the baseline.

#### Scenario: A burst of inventory changes

- **WHEN** the player loots ten items in a row with twelve tracked quests
- **THEN** the slowest frame spends at most 2 ms more in the guide than the slowest frame of the baseline

### Requirement: Common account initialization projects effective completion

AdventureGuide SHALL compile static reverse reachability of supported positive `scene_awake_quest_completed` and `scene_awake_account_claimed` implications, including account/character cycles. Effective state SHALL be the OR of reachable raw true sources. Supported initialization guards and results SHALL be true. Unsupported event semantics SHALL fail loading. Host-death outcomes SHALL NOT participate in current-state closure.

Raw active/completed mirrors and `IsGameQuestCompleted` SHALL remain raw. Only quests explicitly bound by common initialization/completion rows SHALL use projected completion before active/implicit status selection. Account state SHALL read the already-loaded `GameData.AccountClaimedReliquary`. Saved return zone and landing SHALL read GameData.ReliqDest and GameData.ReliqLanding through supported typed keys. The guide SHALL NOT parse saves, invoke LoadReliquary or mutate flags, quests or saves.

#### Scenario: Fresh account

- **WHEN** the raw account claim is false and the character has not completed the claim quest
- **THEN** the claim encounter remains available

#### Scenario: Claimed account before scene Awake

- **WHEN** the account is claimed and a new character has not completed CLAIMRELIQUARY
- **THEN** the guide treats the bound completion as satisfied without proposing another fight
- **AND** the raw character quest mirror remains unfinished

#### Scenario: Legacy character before scene Awake

- **WHEN** raw account claim is false and the character completed CLAIMRELIQUARY
- **THEN** the explicit Awake implication projects effective account claim and suppresses a repeat fight
- **AND** no game flag or save is changed

#### Scenario: False availability and true outcome

- **WHEN** the loaded contract contains false account availability and a true host-death outcome
- **THEN** the outcome does not make current availability contradictory or imply that a death already happened

### Requirement: Stored-slot instructions preserve typed portal roles

AdventureGuide SHALL read the stored Planar and six rune slots through the existing shared slot mirror, never substitute inventory possession or completed quests. It SHALL display the generated instruction from common typed role/destination metadata. Six identical rune actions SHALL display once while preserving six alternative gate identities. Native slot IDs and UI-specific slot-to-destination maps SHALL NOT be displayed or used. Removing/replacing a stored item SHALL invalidate the existing consumers.

#### Scenario: Dedicated portal

- **WHEN** a dedicated portal's required item is absent from its exact slot
- **THEN** guidance names the item and actual destination's planning-table slot
- **AND** carrying the item or completing its quest does not open the route

#### Scenario: Rune portal

- **WHEN** a rune is installed in any one of the six rune slots
- **THEN** its actual portal becomes available and one generic rune-slot action describes the requirement

### Requirement: Account and saved-return changes invalidate existing consumers

Tracker update/load boundaries SHALL compare the supported account flag and saved return state, increment the existing Version and invalidate route/display consumers once per observed change. Warm polling SHALL remain allocation-free. No availability-result cache or new kill-history cache SHALL be introduced. Static implication indices and bounded identity/presentation caches SHALL remain permitted. Unobservable transient advice and required counts SHALL be preserved.

#### Scenario: Character switch changes the return

- **WHEN** character A's saved zone/landing changes to character B's different valid zone/landing
- **THEN** routing, labels and landing calculations use B's state after existing invalidation
- **AND** empty, unknown or nonfinite state produces no accessible or locked fallback edge

### Requirement: Crafted sources navigate missing ingredients

Choosing a crafted source SHALL retain that recipe and the original goal while navigation follows a missing input's acquisition. Held quantities SHALL satisfy input requirements cumulatively across repeated native material slots. Resolved prerequisite steps SHALL target the actual input item so needed-item and corpse tracking follow the current acquisition.

#### Scenario: A crafted key needs repeated materials

- **WHEN** the selected key recipe requires the same material in two native slots and inventory covers only the first slot
- **THEN** navigation follows a source for the remaining material quantity
- **AND** the recipe remains selected until its prerequisites and crafting action are satisfied
- **AND** a scene change does not replace the original crafted-key goal

### Requirement: Final evidence covers the complete consumer

Final acceptance SHALL separately establish implementation, refreshed exported data, integrated generated data and host proof. A common-producer fixture SHALL pass through actual Python generation and the C# parser/evaluator, preserving false values, phases, scopes and exact root/four-support identities. Old schema data, handwritten JSON alone, a source packet or baseline CI SHALL NOT prove the production cutover. Existing performance budgets SHALL be repeated after slot, account and saved-return observations, with twelve identical tracked quests, Alice's Necklace step 2, both baseline scenes, 600 actual ticks, ten patch-plus-tick events, five scene-handler samples and separate real repaint samples. GC.GetTotalMemory SHALL use a positive control without gen-0 collection and SHALL NOT be described as exact per-thread allocation or whole-scene timing.

#### Scenario: Pending host proof

- **WHEN** offline implementation exists but geometry, nested-source or account/return host checks lack authorized runtime evidence
- **THEN** the affected proof remains incomplete and the change is not archived
- **AND** no game launch, account mutation, release or publication follows automatically
