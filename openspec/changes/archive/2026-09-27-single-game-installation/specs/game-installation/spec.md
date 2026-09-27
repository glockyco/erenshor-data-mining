## Purpose

Defines where the game files of a variant live, what puts them there, how the tooling finds them, and what it reports when it cannot.

## ADDED Requirements

### Requirement: One installation for each variant

The game files of a variant SHALL live in exactly one place: the installation that the Steam client inside the CrossOver bottle maintains for that variant's application id.

The tooling SHALL NOT download, copy, or otherwise create game files anywhere else. Derived output SHALL be written outside that installation.

#### Scenario: A variant is extracted

- **WHEN** extraction runs for a variant
- **THEN** it reads the installation that the Steam client maintains for that variant's application id

#### Scenario: Derived output

- **WHEN** the pipeline produces an extracted project, a database, images, or any other derived artifact
- **THEN** it writes outside the installation
- **AND** the installation is unchanged

#### Scenario: Several variants

- **WHEN** more than one variant is installed
- **THEN** each resolves to its own installation through its own application id
- **AND** no variant reads another variant's files

### Requirement: Steam installs and updates the game

Installing or updating game files SHALL be performed by the Steam client inside the bottle. The tooling SHALL NOT provide a command that downloads game content.

A downloader that writes to a location of its own choosing produces a second copy, and a second copy can hold a different build than the one the pipeline reads.

#### Scenario: A variant is not installed

- **WHEN** a command needs a variant whose application id is not installed
- **THEN** it fails and reports that the variant must be installed through the Steam client
- **AND** it does not offer to download the files

#### Scenario: Game files are out of date

- **WHEN** an installation is behind the current build
- **THEN** bringing it current is the Steam client's responsibility
- **AND** the tooling reads whatever build is installed

### Requirement: The installation is found by application id

Discovery SHALL locate a variant's installation by reading the Steam application manifest for its application id and resolving the installation directory that manifest records.

Discovery SHALL NOT match a hardcoded installation directory name, and SHALL NOT accept a configured path as an alternative to discovery.

#### Scenario: The manifest names the directory

- **WHEN** discovery runs for a variant
- **THEN** it resolves the installation from the directory recorded in the manifest for that variant's application id

#### Scenario: Several applications share the bottle

- **WHEN** the bottle holds applications other than the requested variant
- **THEN** discovery selects the one whose manifest matches the requested application id

#### Scenario: The directory is renamed upstream

- **WHEN** the recorded installation directory changes
- **THEN** discovery still resolves the installation without a configuration change

### Requirement: An unusable installation is reported, not worked around

Discovery SHALL accept a candidate only when its managed assembly directory exists. When no installation is found, when more than one matches, or when a manifest cannot be read, discovery SHALL fail with a report that names the variant and its application id and distinguishes those three conditions.

Absence, ambiguity, and an unreadable record have different remedies, so they SHALL NOT produce one report.

#### Scenario: Nothing is installed

- **WHEN** no installation exists for the variant's application id
- **THEN** the failure names the variant and its application id
- **AND** states that the variant must be installed through the Steam client

#### Scenario: Several installations match

- **WHEN** more than one installation matches the application id
- **THEN** the failure names every candidate

#### Scenario: The manifest cannot be read

- **WHEN** a manifest exists but cannot be read
- **THEN** the failure names the manifest rather than reporting the installation as absent

#### Scenario: The installation is incomplete

- **WHEN** a candidate lacks its managed assembly directory
- **THEN** it is rejected and the failure says what was missing

### Requirement: An unsupported environment fails immediately

The tooling SHALL support macOS with a CrossOver bottle. Where the game installation cannot be discovered because the environment is not that one, the tooling SHALL fail and say so.

It SHALL NOT offer a configured path, an environment variable, or any other alternative that stands in for an installation the project does not support.

#### Scenario: An environment without CrossOver

- **WHEN** a command that needs game files runs where the bottle cannot exist
- **THEN** it fails and states the supported environment

#### Scenario: No alternative is offered

- **WHEN** an installation cannot be discovered
- **THEN** the report does not suggest configuring a path to game files
