# test-infrastructure Specification

## Purpose
Defines the durable conventions for how this repository's own Python test suite is built, so that tests fail when the behavior they name breaks and keep passing through an unrelated, correct change elsewhere in the code they do not cover.

## Requirements

### Requirement: One double represents each external system a test replaces

A test that replaces an external system the production code talks to (for example, the wiki's write API) MUST use the one maintained double for that system. The suite MUST NOT carry more than one implementation of the same external system's behavior.

#### Scenario: Two tests exercise the same external system

- **WHEN** two tests in different files each need to run a command against a stand-in for the same external system
- **THEN** both construct the same maintained double, not two separately hand-written ones

#### Scenario: The double's behavior is checked against the real system

- **WHEN** the double's behavior for a given operation is exercised
- **THEN** a contract test runs the same operation against a real instance of that system and fails if the double's result disagrees

### Requirement: A command's collaborators are substituted through their factory

Each CLI command SHALL build each client of an external system (such as the wiki's API or Google Sheets) in one factory, and that factory SHALL accept the client as an override. A test that runs the command against a double of that client SHALL pass the double through that override, not replace the factory with a function that skips it.

#### Scenario: A test replaces a command's collaborator

- **WHEN** a test runs a CLI command against a double instead of its real collaborator
- **THEN** the double reaches the command through the factory's override, and the rest of the factory's construction runs as in production

### Requirement: Local test resources may be supplied directly

Local resources a command assembles for itself (its database connection, storage, and generator context) SHALL NOT be treated as external systems. A test whose service is itself a double SHALL be permitted to supply them directly.

#### Scenario: A doubled service receives local resources

- WHEN a test supplies a service double with a database connection, storage, or generator context
- THEN it may supply those local resources directly

### Requirement: Tests can detect forbidden collaborator construction

A test that asserts a command does not build a collaborator SHALL be permitted to replace the factory with one that fails if called.

#### Scenario: A test must prove a collaborator is never built

- **WHEN** a test asserts that a command does not build a collaborator at all, for example before a precondition fails
- **THEN** the test may replace the factory with one that fails if called

### Requirement: A test fails when the behavior it names breaks

A test for a command or function MUST be capable of failing when that command or function's real logic is replaced with one that does nothing. A test MUST assert what the unit produces at its own boundary (its return value, its written state, or the arguments it passes to an external process or to the service it adapts to) and MUST NOT assert calls between the internal parts of the unit under test.

#### Scenario: The real logic is replaced with a no-op

- **WHEN** a command's real implementation is temporarily replaced with one that performs no work and returns a fixed result
- **THEN** every test that names that command's behavior fails

#### Scenario: A CLI option stops reaching its service

- **WHEN** a CLI command stops passing one of its options to the service it adapts to
- **THEN** a test of that option fails

#### Scenario: An internal helper's arguments change

- **WHEN** a unit changes the arguments it passes between its own internal parts without changing what it produces at its boundary
- **THEN** no existing passing test for that unit starts failing

### Requirement: A text rendering detail does not stand in for the check it protects

A test that verifies a value appears in rendered console or HTML output MUST tolerate how that text happens to be laid out (wrapped, reflowed, or reworded) and MUST fail when the underlying value is wrong, independent of its rendering.

#### Scenario: Rendering changes without changing the value

- **WHEN** the wording or layout of rendered output changes but the value a test checks for is still present in it
- **THEN** the test still passes

#### Scenario: The underlying value is wrong

- **WHEN** the value a test checks for is absent or incorrect
- **THEN** the test fails regardless of how the surrounding text is laid out

### Requirement: A smoke check verifies rendered content, not a copy of today's markup

A smoke check for a generated or wiki page MUST verify that the page renders its expected content through the page's structure (an element, a field, or similar), and MUST NOT rely on a literal recorded substring of that page's current markup.

#### Scenario: A checked page's markup changes

- **WHEN** a smoke-checked page's template changes its wording or markup without changing the data it shows
- **THEN** the smoke check for that page still passes

#### Scenario: A checked page stops showing its expected content

- **WHEN** a smoke-checked page no longer renders the content it is supposed to show
- **THEN** the smoke check for that page fails
