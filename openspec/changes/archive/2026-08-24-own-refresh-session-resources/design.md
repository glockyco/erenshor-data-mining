## Context

See `proposal.md` for motivation. The current owners stop too early:

- `mod launch` invokes `cxstart --no-wait`, so the command exits before the game and CrossOver child processes.
- `maps dev` owns the Vite process, but it replaces a shared database link and removes the link instead of restoring its prior target.
- `teardown_session.py` compensates later by searching all workstation processes. Its predicates include port `5173`, recent `conhost.exe` processes, and command substrings. These predicates show correlation, not ownership.
- Unity Hub and `UnityLicensingClient` are external applications. The refresh workflow has no reliable proof that it created them.

CrossOver provides `cxstart --wait-children`. The repository supports macOS as the local game workstation. The actual CrossOver process topology must be verified against a real launch before the global teardown is removed.

## Goals / Non-Goals

**Goals:**

- Keep an owner alive for the complete lifetime of every game or maps process that the command creates.
- Restrict termination to an owned process group or to exact persisted identities captured by that owner.
- Restore the exact database-link state that `maps dev` observed before mutation.
- Make normal command exit sufficient cleanup.
- Preserve narrow, fail-closed diagnostics for abnormal owner failure.

**Non-Goals:**

- Manage all processes in the shared CrossOver bottle.
- Terminate Unity Hub, licensing services, or unrelated development servers.
- Infer process ownership from a port, process age, executable name, or command substring.
- Add a generic daemon or workstation process manager.

## Decisions

### Make game launch a supervised foreground operation

Replace `cxstart --no-wait` with `cxstart --wait-children`. Run the launcher in a dedicated process group and keep `mod launch` active until CrossOver reports that the game and its children have exited.

`cxstart` is a Perl launcher that replaces itself with `winewrapper`. Capture the launcher identity only after this expected `exec` transition stabilizes. Validate its PID, process group, start time, and executable before each signal.

On interruption, send graceful termination to the validated launcher group. `--wait-children` remains the authoritative CrossOver owner for Wine children that reparent to PID 1 or enter other process groups; do not rediscover those children by name. Wait for a bounded grace period. Send forced termination only while the validated launcher identity still matches. The real smoke must confirm that ending the launcher group also ends the session game, console, and crash-handler processes while unrelated bottle processes remain.

This changes the CLI from fire-and-forget to foreground supervision. That is intentional: a command cannot own cleanup after it has exited.

Do not use `wineserver -k` or terminate a complete bottle. The bottle contains applications outside the current game session.

### Persist exact identities for crash recovery

The supervisor records the stabilized `winewrapper` PID, process group, start time, and command identity. An atomic session record can survive an abrupt supervisor exit. CrossOver remains responsible for its reparented Wine children through `--wait-children`; the repository does not infer ownership of those processes after reparenting.

Recovery validates all recorded identity fields before signaling the launcher group. A PID match alone is insufficient because the operating system can reuse PIDs. If the real-launch smoke shows that a Wine child survives a validated launcher-group shutdown, this ownership mechanism fails and the teardown script must remain until CrossOver provides a stronger owned handle.

Do not add broad fallback discovery. An unowned possible process is a diagnostic result for manual inspection, not a kill target.

### Make maps link replacement transactional

Before `maps dev` creates its temporary link, classify the path as absent or as a symlink and record the prior target without resolving away the link. Refuse to replace a regular file or directory.

Use one `try`/`finally` lifecycle around link mutation and the Vite child process. The `finally` block terminates the owned child when necessary and atomically restores the previous symlink, or removes the temporary link if the path was initially absent. Signal handlers request shutdown; they do not call `sys.exit` before the shared `finally` block runs.

The command checks that the path still contains the temporary link before restoration. If another actor changed it during the session, restoration fails closed and reports the conflict instead of overwriting new state.

### Remove external-application cleanup

Delete automatic Unity Hub and `UnityLicensingClient` termination. Their continued presence is not a repository resource leak. If a future repository command starts an external application, that command must retain and validate its own handle before it gains cleanup authority.

### Delete the compensating teardown after behavioral proof

Delete `teardown_session.py`, the end-of-session section, and incident-log instructions that prescribe broad cleanup only after:

1. unit tests cover normal exit, interruption, stubborn owned children, identity mismatch, link restoration, and link conflict;
2. a real CrossOver launch shows that the supervised command observes the game, `conhost.exe`, and Unity crash-handler lifetime correctly;
3. a real maps session restores its prior link and releases only its own listening port.

Keep incident history as evidence when it explains the old failure mode. Remove obsolete commands and prescriptions from current guidance.

## Risks / Trade-offs

- `mod launch` now occupies its terminal or managed process slot for the game session. This is the cost of deterministic ownership.
- CrossOver can reparent Wine processes. `--wait-children` reduces this risk, but the real smoke is the acceptance gate. If a child escapes before its identity is captured, do not delete the old script until exact-identity supervision is fixed.
- A supervisor crash can leave an owned process alive. The identity record permits narrow recovery, but it intentionally refuses cleanup when ownership cannot be proved.
- Link restoration can report a conflict when another command mutates the shared path concurrently. Failing closed protects the newer state and exposes the unsupported overlap.
