## Purpose

Keep an auditable record of each game's tooltip text and detect missing or changed wiki tooltip facts before articles are published.

## ADDED Requirements

### Requirement: Game tooltip evidence covers the build

A complete collection SHALL record the exact text and field color state written by the game's item window, spellbook, spell details window, and skillbook for every corresponding game entity in the selected build. A reachable stance SHALL use the skillbook text of its activating skill. Each observation SHALL identify its game build, source window, game identity, wiki stable key, and item quality when applicable. Missing entities, duplicate identity matches, failed window calls, and incomplete collections SHALL be reported, not treated as empty text.

#### Scenario: A spell and its item effect have different windows

- **WHEN** a spell appears in the spellbook and as an item's effect
- **THEN** the evidence keeps both window texts with their source and display context

#### Scenario: One item window fails

- **WHEN** the game cannot display one item during collection
- **THEN** the collection names that item and cannot count as complete

#### Scenario: A stance has no activating skill

- **WHEN** no skill in the build activates a stance
- **THEN** that stance has no wiki tooltip target
- **AND** the coverage report names the excluded stance and its reason

### Requirement: Game markup is checked before comparison

The check SHALL parse the game's TextMeshPro line breaks and supported rich text into ordered lines of plain-text spans with typed tones. It SHALL keep meaningful blank lines and source order. Unsupported tags, unsupported colors, invalid nesting, and unsafe markup SHALL fail with the entity, field, and source text named. It SHALL never compare raw markup with rendered HTML or discard an unknown tag.

#### Scenario: A modifier uses color markup

- **WHEN** a game field contains `Haste <color=#00FF00>+3</color>%`
- **THEN** its parsed line retains the words, plus sign, percent sign, and positive tone

#### Scenario: The game adds a new tag

- **WHEN** a field includes an unsupported TextMeshPro tag
- **THEN** the check fails and names its entity and field

### Requirement: Every wiki tooltip is compared with its game source

A complete check SHALL render the selected build's generated article text and generated data modules through local MediaWiki. It SHALL compare the visible game-fact lines and semantic tones of every item, spell, skill, and reachable stance tooltip with the matching game evidence. It SHALL check all eight equipment quality cards against their matching game item quality. Presentation-only icons, links, and layout SHALL not count as fact text. No tooltip, source entity, card, line, or tone SHALL disappear silently. A report SHALL give totals by kind and each difference by stable key, card, source window, and line.

#### Scenario: An equipment quality card is present

- **WHEN** an equipment tooltip shows its Blessed card
- **THEN** its facts are compared with the game's Blessed instance of that item
- **AND** the wiki's separate card label does not count as an extra game fact

#### Scenario: A wiki tooltip drops a fact

- **WHEN** a spell's rendered tooltip omits its game resist type
- **THEN** the report names the spell, source window, and missing line
- **AND** the check fails

#### Scenario: A wiki data module is missing

- **WHEN** a generated spell cannot render with the selected build's data modules
- **THEN** the check names the spell and missing dependency
- **AND** the check fails instead of skipping the spell

### Requirement: Comparison exceptions are narrow and visible

The check SHALL accept only three intentional wiki differences: separate equipment quality cards, damage-over-time wording `/ 3 sec` in place of `/ tick`, and the wiki's weapon-damage-divided-by-delay Base DPS in place of the character-dependent game value. The check SHALL list each applied exception in its report. It SHALL exclude the item's game Base DPS value and explicitly named player-dependent or control-hint lines from comparison, not the surrounding facts. It SHALL report each excluded field, its reason, and its count. An unrecognized line SHALL fail, not become a new exception by default.

#### Scenario: Damage over time differs only in units

- **WHEN** the game reads `Damage: 12 / tick` and the wiki reads `Damage: 12 / 3 sec`
- **THEN** the check accepts and records that exact wording change

#### Scenario: A player-dependent field appears

- **WHEN** a spell detail line scales Mana Regen by the viewer's level
- **THEN** the check excludes only that named game field and reports the exclusion
- **AND** another missing spell line still fails

#### Scenario: A fourth difference appears

- **WHEN** a wiki tooltip adds an unexplained fact or changes a non-excluded tone
- **THEN** the check names the difference and fails

### Requirement: Article publication requires current-build parity

The article deploy command, including its dry run, SHALL fail before any article write if a planned article write exists and the selected build has no complete, passing tooltip parity report for its current game evidence, generated articles, data modules, and tooltip sources. A report from a different build or changed inputs SHALL not pass this gate. This gate SHALL not replace the existing live render, revision, and link checks. The parity check SHALL run locally and SHALL not write to the live wiki.

#### Scenario: A changed tooltip template has not been checked

- **WHEN** a tooltip template changes after a passing report and an article deploy is planned
- **THEN** the deploy refuses the stale report and writes no article

#### Scenario: A mismatch remains after a game update

- **WHEN** current-build parity finds an unexplained difference and a deploy is planned
- **THEN** the dry run and the real deploy fail and name the report

#### Scenario: Nothing needs publication

- **WHEN** the article deploy has no planned writes
- **THEN** it does not require a new parity report
