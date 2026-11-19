## MODIFIED Requirements

### Requirement: The quest panel reads the canonical routes

The wiki quest panel SHALL take the sources, conditions, rewards, and turn-in effects of its routes only from the canonical routes and their executing variants. If a turn-in kills the recipient, the panel SHALL show the death and SHALL NOT describe the recipient as attackable after the turn-in.

#### Scenario: A changed route

- **WHEN** a game update moves a quest's turn-in to another character
- **THEN** the canonical routes and the quest panel both name the new character after one clean build and one Lua generation

#### Scenario: A lethal turn-in that clears invulnerability

- **WHEN** a turn-in variant clears the recipient's invulnerability and then kills the recipient, as Flickering Souls does
- **THEN** the panel says that the recipient dies after turn-in
- **AND** it does not say that the recipient can be attacked after turn-in
