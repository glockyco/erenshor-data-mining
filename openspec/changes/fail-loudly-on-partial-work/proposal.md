## Why

Several pipelines continue past a failure and then report success. A zone capture that raises is logged and skipped while the command prints that the capture pipeline completed. An image whose perceptual hash cannot be computed is recorded as unchanged, so a changed image is excluded from upload. A release version lookup that hits a network error selects the next revision from an empty list, which can reuse a published revision. A Unity manifest that is corrupt is read as empty and then rewritten from the incomplete reading.

These share one architectural defect: an error handler converts a failure into a value the caller cannot distinguish from a real result. The pipeline then persists or publishes work derived from input it never had. The repository already states a preference for fail-closed automation, and a precondition framework exists, but the framework is applied to roughly half the commands that write, publish, or deploy.

## Goals

- A command reports success only when it did the whole job it was asked to do.
- A failure is reported where it is detected, naming the operation and the cause.
- A measurement that could not be taken is never recorded as a negative result.
- Absent or unreadable input never becomes empty input that later gets written back.
- Every command that creates, publishes, deploys, or mutates state declares its preconditions.

## Non-Goals

- Changing what the pipelines produce when every input is present and valid. Output for a healthy run is unchanged.
- Adding retry, backoff, or recovery. The subject is reporting the failure, not surviving it.
- Reworking the three-variant design. Variant handling is uniform and correct.
- Restructuring the precondition framework. Its types and decorator are sound and the work is coverage.
- Partial-progress resumption. A failing run may leave earlier artifacts on disk, and naming that is enough.

## Migration Boundary

Behaviour changes only on inputs that are currently absent, unreadable, ambiguous, or failing. A run whose inputs are all valid produces identical output and identical exit status. Commands that previously exited zero after skipping work will now exit non-zero, which is the intended break.

## What Changes

- **BREAKING** A batch command that loses any unit fails after reporting every failed unit, rather than completing.
- **BREAKING** An image comparison that raises is an error, not an `unchanged` classification.
- **BREAKING** A release version lookup that cannot reach the registry fails instead of restarting revision numbering.
- A missing or malformed Unity dependency manifest stops the rip instead of being replaced from an empty reading.
- Missing map-position input stops wiki generation instead of emitting pages without map links.
- An external program that is absent is named where it is detected, rather than becoming a timeout or a raw interpreter error.
- Several matching CrossOver installations is an error naming the candidates, rather than an absent path.
- Commands that create, publish, deploy, or mutate state gain precondition declarations.

## Capabilities

### New Capabilities

- `command-failure-semantics`: when a command may report success, how a failure is surfaced, and what an error handler may not convert a failure into.

### Modified Capabilities

None. `dependency-management` and `development-environment` are unrelated to runtime failure reporting.

## Impact

- **Application:** `capture/orchestrator.py`, `extract/rip_workflow.py`, `mods/release.py`, `services/image_registry.py`, `wiki/generators/pages/zones.py`, `mods/local_workflow.py`, `code_facts/runner.py`.
- **Infrastructure:** `assetripper/assetripper.py` for the bare `curl` invocation and the swallowed export-log reads.
- **CLI:** `commands/capture.py` success reporting, `preconditions/checks/maps.py` cause preservation, and precondition declarations across `capture`, `eval`, `guide`, `images`, `mod`, `maps`, `extract`, and `wiki`.
- **Exit codes:** commands that silently degraded now fail. Any automation that depended on a zero exit through a partial run must be updated.
- **Unaffected:** the three-variant configuration, the SteamCMD wrapper's existing typed errors, the Lua validation probe, and the golden-capture aggregation, which already behave this way.
