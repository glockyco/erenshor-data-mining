## Purpose

Defines safe ownership and shutdown behavior for processes and mutable filesystem state created by local refresh commands.

## Requirements

### Requirement: Commands own the processes that they create

A long-running refresh command SHALL remain the authoritative owner of each process that it creates. It SHALL NOT require a later search by port, process age, or command substring to stop those processes.

#### Scenario: Game session exits normally

- **WHEN** the launched game and its child processes exit
- **THEN** the launch command exits
- **AND** no process created for that launch remains running

#### Scenario: Game session is interrupted

- **WHEN** the user interrupts a running game launch
- **THEN** the command requests graceful termination of its owned process tree
- **AND** it uses forced termination only for an owned process that does not exit within the bounded grace period
- **AND** it does not terminate an unrelated CrossOver process

#### Scenario: Maps server is interrupted

- **WHEN** the user interrupts a running maps development server
- **THEN** the command terminates the server process that it created
- **AND** no process from that server remains listening on its configured port

### Requirement: External applications retain their own lifecycle

The refresh workflow SHALL NOT terminate an external application or service that it did not start and supervise.

#### Scenario: Unity Hub was already running

- **WHEN** a refresh command completes while Unity Hub or its licensing service is running
- **THEN** the refresh command leaves that application or service running

### Requirement: Recovery identifies exact stale resources

Recovery diagnostics SHALL identify stale resources by an identity recorded by their creating command. Recovery SHALL fail closed when it cannot prove ownership.

#### Scenario: Recorded process identity is stale

- **WHEN** a recorded process identifier now belongs to a different process
- **THEN** recovery does not terminate that process
- **AND** recovery reports the identity mismatch

#### Scenario: No ownership record exists

- **WHEN** a possible game, console, or development-server process exists without an ownership record
- **THEN** recovery reports the process for manual inspection
- **AND** recovery does not terminate it

### Requirement: Routine teardown is not an agent step

Agent guidance SHALL describe resource cleanup as part of each owning command. It SHALL NOT require a routine end-of-session command that searches global workstation state.

#### Scenario: Agent reads refresh workflow guidance

- **WHEN** an agent loads the `refreshing-game-data` skill
- **THEN** the skill does not instruct the agent to run the removed teardown script
- **AND** it explains how to inspect an explicitly reported cleanup failure
