## Purpose

Records once how each quest starts and how it finishes, with the exact sources, variants, and conditions that the shipped game executes, so that every consumer reads the same quest routes.

## ADDED Requirements

### Requirement: Each quest records its start and completion routes

The clean database SHALL record every start route and every completion route of each quest with its method, its exact source (a character copy, an item, a quest, a zone, or a script), its resource variant when the route belongs to one, its dialog keyword when it has one, and its conditions as gate groups. It SHALL record only routes that the shipped code can execute.

#### Scenario: A dialog start

- **WHEN** reading A Hermit's Request
- **THEN** it starts by saying "they" to A Hermit
- **AND** that route holds only while A Hermit's Request is not done

#### Scenario: A chained start

- **WHEN** reading Repairing Orion's Ring, Part 2
- **THEN** it starts when Repairing Orion's Ring completes

#### Scenario: A turn-in completion

- **WHEN** reading Repairing Orion's Ring, Part 2
- **THEN** it finishes by turning in Unsocketed Ring, Elderstone Shard, and Chunk of Citrine Sandsilver to Parmalee Gemlyn or to Violet Smithfield

#### Scenario: A furnished room

- **WHEN** reading Lighting the Nighthollow Candle
- **THEN** it finishes at the Braxonian Flame Well in Fallen Braxonia or at a Flame Well in any of the eight Reliquary rooms
- **AND** each Reliquary route needs its room furnished with the Flame Well Seed

#### Scenario: A scripted completion

- **WHEN** reading She Sees You
- **THEN** its completion route names its script and no source character

### Requirement: A route records what it grants

Each route SHALL record whether it executes the rewards of its resource: experience, gold, an item, faction changes, and the completion of other quests. A route that completes a quest without the trade window SHALL grant none of them, whatever its resource configures.

#### Scenario: A talk completion

- **WHEN** reading A Missing Person
- **THEN** its talk completion with Cirreus Alxanth grants no experience, although its resource configures 25

### Requirement: The quest panel reads the canonical routes

The wiki quest panel SHALL take the sources, conditions, and rewards of its routes only from the canonical routes.

#### Scenario: A changed route

- **WHEN** a game update moves a quest's turn-in to another character
- **THEN** the canonical routes and the quest panel both name the new character after one clean build and one Lua generation

### Requirement: Unknown route shapes fail the build

The clean build SHALL fail and name the quest and the fact when a quest source has a method, a source kind, or a condition that the routes do not map.

#### Scenario: A new completion method

- **WHEN** the export records a completion method that the routes do not map
- **THEN** `extract build` fails and names the quest and the method
