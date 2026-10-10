# Spec Delta

## Purpose

Defines the durable conventions for how this repository's own Python test suite is built, so that tests fail when the behavior they name breaks and keep passing through an unrelated, correct change elsewhere in the code they do not cover.

## ADDED Requirements

### Requirement: One double represents each external system a test replaces

A test that replaces an external system the production code talks to (for example, the wiki's write API) MUST use the one maintained double for that system. The suite MUST NOT carry more than one implementation of the same external system's behavior.

#### Scenario: Two tests exercise the same external system

- **WHEN** two tests in different files each need to run a command against a stand-in for the same external system
- **THEN** both construct the same maintained double, not two separately hand-written ones

#### Scenario: The double's behavior is checked against the real system

- **WHEN** the double's behavior for a given operation is exercised
- **THEN** a contract test runs the same operation against a real instance of that system and fails if the double's result disagrees

### Requirement: A command's collaborators are injected, not bound by import path

Each CLI command MUST build its collaborators (external clients, services) in one place, and a test MUST substitute a double by replacing that one place, not by patching the command module's internal factory function at its exact import path.

#### Scenario: A test replaces a command's collaborator

- **WHEN** a test runs a CLI command against a double instead of its real collaborator
- **THEN** the test supplies the double through the one object the command's collaborators are built from

#### Scenario: An internal factory function is renamed

- **WHEN** the name of the function that builds a command's collaborator changes, with no change to the command's observable behavior
- **THEN** no existing test fails because of that rename alone

### Requirement: A test fails when the behavior it names breaks

A test for a command or function MUST be capable of failing when that command or function's real logic is replaced with one that does nothing. A test MUST NOT assert only that an internal collaborator was called, nor pin an exact internal argument list or keyword-argument mapping that an unrelated, behavior-preserving change can alter.

#### Scenario: The real logic is replaced with a no-op

- **WHEN** a command's real implementation is temporarily replaced with one that performs no work and returns a fixed result
- **THEN** every test that names that command's behavior fails

#### Scenario: An unrelated internal argument is added

- **WHEN** a command gains an additional internal call argument that does not change its observable behavior
- **THEN** no existing passing test for that command starts failing solely because of the new argument

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
