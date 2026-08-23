## Purpose

Defines when a command may report success, where a failure must be reported, and what an error handler may not convert a failure into, so that no pipeline persists or publishes work derived from input it did not have.

## ADDED Requirements

### Requirement: Success means the whole job was done

A command SHALL report success only when every unit of work it accepted completed. When one or more units fail, the command SHALL fail and SHALL name every unit that failed and why.

A command MAY continue past a failed unit in order to collect the full set of failures. Continuing SHALL NOT change the outcome it reports.

#### Scenario: One unit of a batch fails

- **WHEN** a command processes several units and one of them raises
- **THEN** the command fails
- **AND** its report names every unit that failed and the cause of each

#### Scenario: Every unit succeeds

- **WHEN** every unit completes
- **THEN** the command reports success
- **AND** its output is identical to the output it produced before this requirement existed

#### Scenario: Artifacts from completed units

- **WHEN** a command fails after some units already wrote output
- **THEN** the report states that the output is partial
- **AND** the command does not describe the run as complete

### Requirement: A measurement that could not be taken is not a result

When a comparison, hash, or other measurement raises, the failure SHALL be reported. It SHALL NOT be recorded as a value that indicates no difference, no change, or equality.

An error is not evidence of sameness. Recording it as sameness removes the item from the work the difference was meant to select.

#### Scenario: A comparison raises

- **WHEN** comparing two items raises
- **THEN** the failure is reported
- **AND** the pair is not classified as unchanged or equal

#### Scenario: A comparison finds no difference

- **WHEN** the comparison completes and finds no difference
- **THEN** the pair is classified as unchanged

#### Scenario: Selection driven by comparison

- **WHEN** a command selects items to publish based on whether they changed
- **THEN** an item whose comparison failed is never treated as one that needs no publishing

### Requirement: Absent input does not become empty input

When a required input is missing, unreadable, or malformed, the operation that needs it SHALL fail and name the input and the location. It SHALL NOT substitute an empty value.

An operation SHALL NOT write a replacement for an input it failed to read.

#### Scenario: A required file is malformed

- **WHEN** an operation reads a required structured file and the content is not valid
- **THEN** the operation fails and names the file and the reason

#### Scenario: A required file is absent

- **WHEN** a required input file does not exist
- **THEN** the operation fails and names the expected location

#### Scenario: Regenerating what could not be read

- **WHEN** an operation would write a file whose previous content it failed to read
- **THEN** it does not write the file

#### Scenario: Generation that depends on optional input

- **WHEN** generated output would omit content because its input is absent
- **THEN** generation fails rather than emitting output missing that content

### Requirement: A remote lookup failure is not an empty answer

When a lookup against a remote service fails, the failure SHALL be reported. The result SHALL NOT be treated as an empty collection.

A version, revision, or sequence number SHALL NOT be derived from a collection that a failed lookup produced.

#### Scenario: The registry is unreachable

- **WHEN** a lookup of published versions fails
- **THEN** the command fails and names the service and the cause
- **AND** it does not compute a version from an empty list

#### Scenario: The registry reports no versions

- **WHEN** a lookup succeeds and reports that nothing is published
- **THEN** the command proceeds with the first version

### Requirement: A missing external program is named where it is detected

Before invoking an external program, code SHALL confirm the program is resolvable, and SHALL fail with a message naming the program and how the environment supplies it.

A missing program SHALL NOT surface as a timeout, a generic startup failure, or an unhandled interpreter error.

#### Scenario: A helper invokes an absent program

- **WHEN** code invokes an external program that is not resolvable
- **THEN** it fails immediately with a message naming the program

#### Scenario: Waiting on a service that cannot start

- **WHEN** a service cannot start because a program it needs is absent
- **THEN** the failure names the absent program
- **AND** the command does not wait for a timeout before reporting

#### Scenario: An error while observing a running operation

- **WHEN** reading the progress or log of a running operation fails
- **THEN** the failure is reported with its cause rather than polled past until a timeout

### Requirement: Ambiguity is an error, not absence

When discovery finds more than one candidate and cannot choose, it SHALL fail and name every candidate. It SHALL NOT return absence, and it SHALL NOT select one.

Absence and ambiguity have different remedies, so they SHALL NOT produce the same report.

#### Scenario: Several installations match

- **WHEN** discovery finds more than one installation for the requested application
- **THEN** it fails and names every candidate

#### Scenario: Nothing matches

- **WHEN** discovery finds no installation
- **THEN** it reports that none was found, distinctly from the ambiguous case

#### Scenario: A record cannot be read

- **WHEN** an installation record exists but cannot be read
- **THEN** the failure names the record rather than reporting the installation as absent

### Requirement: State-changing commands declare their preconditions

Every command that creates, publishes, deploys, uploads, or otherwise mutates state outside the process SHALL declare its preconditions through the precondition framework, so its inputs are checked before it begins.

A precondition check SHALL preserve the cause it observed. It SHALL NOT report a generic condition in place of the error it caught.

#### Scenario: A state-changing command runs

- **WHEN** a command that mutates external state is invoked
- **THEN** its declared preconditions run before any work begins
- **AND** a failing precondition stops the command before it mutates anything

#### Scenario: A check catches an error

- **WHEN** a precondition check catches an error while probing
- **THEN** the reported result names the error it caught
- **AND** it does not substitute an unrelated generic reason

#### Scenario: A read-only command

- **WHEN** a command only reads and reports
- **THEN** it is not required to declare preconditions
