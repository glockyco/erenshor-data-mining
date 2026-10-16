# Spec Delta

## Purpose

Defines how AdventureGuide decides which targets and routes are available from the gate conditions in its data, how it explains and resolves unmet gates, and the reliability and performance it must keep while doing so.

## ADDED Requirements

### Requirement: Availability follows the observable game state

AdventureGuide SHALL evaluate the observable atoms of each condition from the live game state: completed quests, inventory contents, the keyring, and the Reliquary room slots. A key atom SHALL hold when the key is on the keyring or in the inventory. A subject SHALL be available when its condition holds with every advisory atom treated as holding. Every consumer of a gate (routing, target selection, world markers, the quest detail panel, the tracker, and step scene resolution) SHALL use the same evaluation.

#### Scenario: A key moves to the keyring

- **WHEN** the player opens the Island Tomb Ghostly Key door and the game moves the key from the inventory to the keyring
- **THEN** Ghost of Wyland Sercher stays available

#### Scenario: A key is dropped before use

- **WHEN** the player destroys the Dockhouse Key before opening the dockhouse door
- **THEN** Founder becomes unavailable within the frame that follows the inventory change

### Requirement: Advisory atoms guide and never hide

AdventureGuide SHALL NOT hide, skip, or reject a target because of an advisory atom. It SHALL show each advisory atom of the target's condition as a requirement, with navigation to the characters it names.

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

When the navigation target or a hop of its route is gated by an observable atom, AdventureGuide SHALL navigate to what satisfies it: the sources of a missing item or key, the current step of a missing quest, or the Reliquary planning table for a missing furnishing. Among the groups of a condition it SHALL choose the group with the fewest unmet atoms, and among equal groups the one whose first requirement is nearest by route. When the requirement is gated itself, it SHALL repeat this choice and SHALL stop with an explanation, without navigation, when no requirement can be reached. The navigation display, the quest detail panel, and the tracker SHALL show the chain from the original step to the requirement being navigated.

#### Scenario: Island Tomb through the lighthouse

- **WHEN** the route to Occuphage needs the lighthouse entrance and the player has no Stowaway's Step Lighthouse Key
- **THEN** navigation leads to the key's source and shows that the key opens the lighthouse door

#### Scenario: Unlock by either of two routes

- **WHEN** the player navigates to a Jaws of Sivakaya target from the Duskenlight Coast without the Nighthollow Candle and without She Sees You
- **THEN** navigation leads to the requirement of the group with fewer unmet atoms and names the other group as an alternative

### Requirement: Routing excludes unusable zone lines

Cross-zone routing SHALL NOT use a zone line that the data marks unusable, even as a locked fallback. It SHALL prefer a route whose zone lines are available. When every route needs a gated zone line, it SHALL route to the first gated hop and apply the requirement guidance to that hop.

#### Scenario: Shivering Step exits

- **WHEN** the player in Shivering Step navigates to a target in Hidden Hills
- **THEN** the route leaves through Stowaway's Step and never through the unusable Shivering Step zone line to Hidden Hills

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
