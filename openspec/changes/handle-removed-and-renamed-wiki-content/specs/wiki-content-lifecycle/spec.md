## Purpose

Records what happens to wiki pages when game content is removed, renamed, or still present but no longer obtainable. It keeps older links useful and makes retired pages visible to editors.

## ADDED Requirements

### Requirement: Removed content keeps its page and a clear notice

The wiki SHALL retain a page about removed content and display `Historical Content` on it. The notice SHALL link the relevant update notes when known and put the page in `Category:Removed Content`. It SHALL leave the rest of the page available to readers.

#### Scenario: A stance loses its activating skill

- **WHEN** generation stops producing `Reckless` and `Stance: Reckless` after the Planar March update
- **THEN** both existing pages remain readable with a `Historical Content` notice and appear in `Category:Removed Content`
- **AND** each notice links the Planar March notes and gives the update date

#### Scenario: An editor uses the notice without a known update

- **WHEN** an editor marks removed content whose removal update is not known
- **THEN** the notice states that the content is no longer in the game without inventing an update or date
- **AND** the page appears in `Category:Removed Content`

#### Scenario: A handwritten note is on an old scroll page

- **WHEN** generation no longer produces `Spell Scroll: Mana Burst`, `Spell Scroll: Mana Call`, or `Spell Scroll: Mana Flood`
- **THEN** each live page keeps its other text and receives the removed-content notice
- **AND** none of the three pages is deleted or replaced by a generated article

### Requirement: Present but unobtainable content is distinguished from removal

The wiki SHALL use a distinct `Historical Content` message for content that still exists in game data but cannot be obtained. It SHALL place such a page in `Category:Unobtainable Content` and keep an editor's explanation of why it is unobtainable.

#### Scenario: An old crafting result remains in game data

- **WHEN** an editor marks `Pristine Ceremonial Ring` or `Unusual Copper Sceptre` as unobtainable
- **THEN** the notice says that the item can no longer be obtained, not that it is no longer in the game
- **AND** the crafting explanation remains available on the page

### Requirement: Generated articles display recorded lifecycle facts

For a page that generation still produces, the wiki SHALL place known lifecycle facts in its infobox fields and render the matching notice. It SHALL not infer removal merely because an item cannot be obtained.

#### Scenario: An unobtainable item still has game data

- **WHEN** generation writes `Pristine Ceremonial Ring` with a recorded unobtainable state
- **THEN** its item infobox carries the recorded state and any known update, date, and patch-notes link
- **AND** the page shows the unobtainable notice and joins `Category:Unobtainable Content`

#### Scenario: A recorded removed spell is still exported

- **WHEN** generation writes `Mana Burst` with a recorded removed state
- **THEN** its ability infobox carries that state and the page shows the removed notice

### Requirement: Renamed content keeps old links working

When an entity retains its stable identity but changes page title, the wiki SHALL redirect the old title to the new title. It SHALL not label that old title as removed content.

#### Scenario: The Reckless skill book changes title

- **WHEN** `item:skillbook - stance - reckless` changes from `Skill Book: Reckless Stance` to `Skill Book: Reckless Strike`
- **THEN** the old title redirects to `Skill Book: Reckless Strike`
- **AND** the current item page remains the destination

### Requirement: Previously generated pages that lose generation are reported

A full article review SHALL list existing live pages created by WoWBot when current generation no longer produces their titles. For each page it SHALL report the old title, known stable identity, current title if one exists, and whether the reviewed notice or redirect is pending or already live. An unexplained title or incomplete review SHALL be a failure. It SHALL not delete or silently replace old pages. A partial run SHALL not present itself as a complete review.

#### Scenario: Removal and rename appear in the same review

- **WHEN** current generation omits the live WoWBot pages `Reckless`, `Stance: Reckless`, and `Skill Book: Reckless Stance`
- **THEN** the review lists all three titles
- **AND** it identifies the skill book as a rename to `Skill Book: Reckless Strike`
- **AND** it identifies the other two as pages needing removal review

#### Scenario: A reviewed redirect is not yet live

- **WHEN** the old skill-book title still holds an article and the reviewed target exists
- **THEN** the review reports a pending redirect instead of claiming it is already live

#### Scenario: A page was written by a person

- **WHEN** a live page was not created by WoWBot and generation does not produce it
- **THEN** it is not reported as a retired WoWBot page

#### Scenario: A live page cannot be checked

- **WHEN** the review cannot confirm the live status or creator of a candidate page
- **THEN** it reports that the review is incomplete instead of treating the missing result as no retired page
