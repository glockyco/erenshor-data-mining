# Spec Delta

## Purpose

Render spell and skill articles by exact stable identity while retaining editorial text, native inline tooltip interactions and reversible publication.

## ADDED Requirements

### Requirement: One new ability template resolves exact spell or skill identity

The wiki SHALL provide AbilityData requiring an explicit spell or skill stable key. It SHALL resolve the corresponding data record without guessing by page title or display name. Legacy Ability SHALL remain compatible and parameter-only.

#### Scenario: Two effects share one page

- WHEN a page contains separate caster and effect keys with the same displayed name
- THEN each root renders its own exact data and effects
- AND neither root is substituted for the other

#### Scenario: Wrong-kind or missing key

- WHEN AbilityData has a missing, unknown or stance key
- THEN it shows an identity diagnostic and invalid-identity tracking category
- AND does not choose another record on the page

### Requirement: Ability rendering exposes useful native facts

Converted pages SHALL retain current visible game facts and show applicable class levels, targeting, range, resist modifiers, skill requirements, mana restoration and stacking lines. Spell and skill labels SHALL match their entity kind. Implementation-only flags SHALL NOT become public rows solely because they exist in data.

#### Scenario: Skill has equipment and position requirements

- WHEN a skill requires a particular weapon or shield and being behind a target
- THEN its page shows those requirements and uses Skill Type rather than Spell Type

#### Scenario: Skill power is not spell damage

- WHEN a native skill power value has a meaning specific to its skill type
- THEN rendering preserves that meaning rather than automatically labeling it spell target damage

### Requirement: Native units and effects remain distinct

Rendering SHALL preserve the different native units for spell cooldown, skill cooldown, spell charge time and duration ticks. Linked effects, caster variants, summoned entities and procs SHALL retain their exact identities without name fallback or page-title deduplication.

#### Scenario: Fractional skill cooldown

- WHEN a skill has a cooldown of 800 ticks
- THEN its page shows 13.33 seconds rather than 800 seconds or a rounded 13 seconds

#### Scenario: Skill applies multiple effect kinds

- WHEN a skill applies an effect, changes a stance and casts on a target
- THEN the page preserves all three relationships and their respective identities

### Requirement: Spell and skill categories are accurate

Spell roots SHALL emit Abilities and Spells, and skill roots SHALL emit Abilities and Skills, in article namespace only. Shared pages SHALL retain the union of their roots' categories.

#### Scenario: A shared page contains both kinds

- WHEN a page contains a converted spell and a converted skill
- THEN it belongs to both Spells and Skills as well as Abilities
- AND a template documentation page does not receive those article categories

### Requirement: Captions and prose remain editor owned

AbilityData SHALL preserve exact imagecaption values and surrounding prose. An explicit blank caption SHALL suppress the data caption default. Unsupported factual parameters SHALL NOT override game facts and SHALL be tracked. A presentation control SHALL NOT change lifecycle state.

#### Scenario: Existing generated caption becomes owned presentation

- WHEN an existing root carries a status-message caption
- THEN conversion preserves its raw value without using text similarity to erase it
- AND future game-data changes do not rewrite that article field

#### Scenario: Unexpected editorial fact differs from data

- WHEN a current-generation legacy root has an unresolved differing factual parameter
- THEN conversion blocks and reports it for source correction or explicit editorial migration
- AND does not silently replace the text

### Requirement: Ability relationships reuse published facts

Ability pages SHALL consume canonical generated class and source relations without independently selecting them in Lua. Existing complete Spells and Skills structures SHALL remain compatible. New lifecycle metadata SHALL use a narrow supplement rather than a duplicate complete entity schema.

#### Scenario: A skill is an item effect

- WHEN Skills data contains an items-with-effect relation
- THEN the converted skill page displays that relation even if its legacy article field was blank
- AND the renderer does not discover the relation by querying or scanning item records

### Requirement: Inline and hover tooltips remain exact

Each converted root SHALL expose exactly one inline tooltip with its native kind and exact root stable key. Existing semantic hover and focus interactions SHALL select that card on multi-root pages. The inline spell tooltip SHALL remain the details surface without a new right-click action.

#### Scenario: Hover targets one caster variant

- WHEN a semantic ability link requests a particular stable key on a shared page
- THEN the hover card matches that key and not the first card by display name

#### Scenario: Item already shows a spell tooltip

- WHEN a converted spell tooltip is used below an item
- THEN its details remain visible inline
- AND no right-click-for-details interaction is added

### Requirement: Historical and manual pages retain their dispositions

Recorded historical spells SHALL retain their notices even when still exported. Identity-less, mapping-excluded or manual legacy roots SHALL remain readable and unchanged unless separately reviewed. Conversion coverage SHALL distinguish complete eligible current-generation cutover from retained legacy compatibility users.

#### Scenario: A removed historical skill has no current stable key

- WHEN an unkeyed removed-skill root has no proven current identity
- THEN it remains on the legacy renderer with its exact content and notice
- AND conversion neither assigns a name-matched identity nor counts the root as converted

#### Scenario: A historical spell still has current exported data

- WHEN a spell key has a recorded removed state
- THEN its converted page shows that state once
- AND data-table presence does not reclassify it as active

### Requirement: Full-corpus and real-data acceptance gate broad writes

Broad conversion SHALL require reviewed legacy-versus-candidate production text parses for every eligible page and complete dispositions for all live legacy users. Real generated dependencies and worst-case pages SHALL leave at least 25 percent headroom under observed enforcing page, Lua and parser limits. Local browser screenshots SHALL precede live reader approval.

#### Scenario: Only a representative canary has been compared

- WHEN production comparisons omit another eligible page or leave a dependency check provisional
- THEN broad conversion is blocked
- AND the report identifies incomplete coverage rather than reporting success

### Requirement: Ability conversion uses guarded reversible publication

Writes SHALL require a reviewed complete dry run and explicit approval, guard fetched revisions and save rollback text before writing. Broad approval SHALL be separate from successful canary and demonstrated rollback approval. Companions SHALL be removed only with exact identity and checkpointed bot ownership proof.

#### Scenario: Manual companion would duplicate a keyed tooltip

- WHEN an unowned manual tooltip would conflict with the converted root's inline card
- THEN conversion blocks for editorial resolution rather than deleting it or publishing ambiguous hover output

#### Scenario: A page changes after review

- WHEN the live revision or approved source/data hashes change
- THEN the planned write is refused and its review must be refreshed

### Requirement: Converted ability updates preserve article bytes

After verified eligible cutover, new spell/skill pages SHALL use compact identity stubs and existing articles SHALL reconcile only membership changes. Unchanged membership SHALL return unchanged bytes. Removed identities SHALL require lifecycle handling. Type-specific legacy generation SHALL be removed only after complete eligible coverage and rollback acceptance, without removing manual users' renderer.

#### Scenario: Spell damage changes without membership changes

- WHEN a data update changes spell damage but not page identity membership
- THEN data deployment changes the rendered damage without rewriting article text

#### Scenario: Legacy-only articles remain

- WHEN all eligible current-generation roots are converted but handwritten legacy users remain
- THEN the cutover receipt reports both populations accurately
- AND legacy Ability remains available without retaining obsolete full-article generation
