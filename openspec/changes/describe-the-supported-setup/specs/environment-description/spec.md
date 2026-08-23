## Purpose

Defines what the repository states about where things are, how it is configured, and how it is run, and requires those statements to agree with the code and with each other.

## ADDED Requirements

### Requirement: Documented configuration precedence matches the loader

Any document describing configuration precedence SHALL list the layers the loader implements, in the order it applies them, and SHALL NOT list a layer that does not exist.

A document SHALL advertise an environment variable only when the package reads it. A variable the package reads SHALL be documented where a reader configuring the project will find it.

#### Scenario: A documented layer

- **WHEN** a document lists a configuration layer
- **THEN** the loader applies that layer at the stated position

#### Scenario: An advertised variable

- **WHEN** a document advertises an environment variable
- **THEN** the package reads that variable

#### Scenario: A variable the code reads

- **WHEN** the package reads an environment variable that affects configuration
- **THEN** a document states its name and effect

### Requirement: One documented way to run the game locally

Documents SHALL describe the supported way to launch the game on this platform and SHALL NOT offer an alternative the code does not implement.

Where the code accepts exactly one program to perform a step, documents SHALL name that program rather than a category of programs.

#### Scenario: The launch prerequisite

- **WHEN** a document states what is required to launch the game on macOS
- **THEN** it names the compatibility layer the launcher actually invokes
- **AND** it does not present other runtimes as supported

#### Scenario: Obtaining a prerequisite tool

- **WHEN** a document states that an external tool is required
- **THEN** it states how this environment supplies the tool

### Requirement: A document names only things that exist

A document SHALL reference only files, directories, commands, and configuration keys that exist. A reference that no longer resolves SHALL be corrected or removed.

#### Scenario: A referenced path

- **WHEN** a document names a file or directory
- **THEN** that path exists in the repository

#### Scenario: A referenced command

- **WHEN** a document shows a command
- **THEN** the command exists in the current command surface

### Requirement: Documents describe current behaviour

An active document SHALL describe how the project works now. It SHALL NOT describe what changed, what was removed, what it used to do, or what is deprecated.

This applies to documents that describe the project. It does not apply to planning artifacts that record a decision and its date, and it does not apply to a statement required by the compatibility requirement below.

#### Scenario: A statement about the past

- **WHEN** an active document explains a previous behaviour or a transition
- **THEN** that explanation is removed and the current behaviour is stated as the only behaviour

#### Scenario: A superseded document

- **WHEN** a document exists only to record what an earlier design got wrong
- **THEN** it is removed rather than kept as guidance

#### Scenario: Naming what the code still accepts

- **WHEN** a statement names an older client, format, or version in order to say what the code accepts today
- **THEN** it is current behaviour and is kept

### Requirement: A compatibility surface states who it serves

Where the project keeps an interface for clients it no longer produces, the code that provides it SHALL record who it serves and why it is kept. A document a user reads SHALL state the same thing.

Such an interface is indistinguishable from an oversight once the person who kept it stops reading the repository. The record SHALL also state what would allow its removal, and SHALL say so plainly when no such condition is planned.

#### Scenario: An interface for a client the project no longer ships

- **WHEN** the project accepts connections, formats, or messages from a client it no longer builds or publishes
- **THEN** the code providing it records who it serves and why
- **AND** a user-facing document states the same

#### Scenario: The condition for removal

- **WHEN** a compatibility surface is documented
- **THEN** the record states what would allow it to be removed
- **AND** where nothing is planned, it says the surface is kept indefinitely

#### Scenario: An undocumented compatibility surface

- **WHEN** an interface exists only for clients the project no longer produces and carries no such record
- **THEN** it cannot be distinguished from an oversight and the record is added

#### Scenario: Handling for a client that never used the interface

- **WHEN** a compatibility surface carries handling for a message, format, or client that no released version ever sent to it
- **THEN** that handling is removed
- **AND** the surface keeps only what the clients it names actually send

### Requirement: A machine-specific value has one definition

A path, directory root, or other environment-specific constant SHALL be defined once. A module that needs it SHALL import it from the module that owns it.

Two definitions of one fact can disagree, and nothing reports the disagreement.

#### Scenario: A second module needs a constant

- **WHEN** a module needs an environment-specific constant that another module defines and exports
- **THEN** it imports the constant rather than defining its own

#### Scenario: The value changes

- **WHEN** the correct value of such a constant changes
- **THEN** one edit changes it everywhere it is used
