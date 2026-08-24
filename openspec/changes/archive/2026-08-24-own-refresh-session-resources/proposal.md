## Why

The refresh workflow tells agents to run a broad teardown script because the commands that create processes and mutable links do not own their complete lifecycles. The script searches global process state by port, age, and command substring, so it can terminate unrelated CrossOver or development processes.

## What Changes

- Make each long-running command remain attached to, and own, the process tree that it creates.
- Make `maps dev` preserve and restore the database link state on normal exit, interruption, and failure.
- Make CrossOver game launch wait for the game and its children instead of detaching them with `--no-wait`.
- Use graceful process termination first, with bounded forced termination only for processes in the owned tree.
- Remove teardown behavior that searches global process state or quits Unity Hub and its licensing service.
- Remove the teardown script and the routine end-of-session teardown step after lifecycle smoke tests prove that the owners clean up their resources.
- Keep recovery narrow: report an escaped process or stale link with its exact identity instead of searching for and killing possible matches.

## Capabilities

### New Capabilities

- `refresh-session-lifecycle`: Defines ownership, shutdown, state restoration, and recovery behavior for resources created during a local refresh session.

### Modified Capabilities

- None.

## Impact

- **CLI:** `uv run erenshor mod launch` becomes a supervised foreground command on CrossOver. It exits after the game and its child processes exit.
- **Maps:** `uv run erenshor maps dev` restores the link state that existed before startup instead of relying on later teardown.
- **Agent workflow:** `refreshing-game-data` no longer requires routine global cleanup at the end of a session.
- **Removed surface:** `.agent/skills/refreshing-game-data/scripts/teardown_session.py` and its incident-driven kill heuristics are deleted.
- **External applications:** Unity Hub and `UnityLicensingClient` remain under their own lifecycle owners. The refresh workflow does not terminate them.
- **Non-goals:** no game installation changes, bottle migration, export semantic changes, deployment changes, or generic workstation process manager.
