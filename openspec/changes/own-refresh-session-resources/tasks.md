## 1. Supervise game processes

- [x] 1.1 Add a process-session owner that starts a dedicated process group, records exact process identities atomically, validates identities before signaling, and removes its record after complete shutdown.
- [x] 1.2 Change CrossOver launch planning from `--no-wait` to `--wait-children` and keep `mod launch` active for the owned session.
- [x] 1.3 On interruption, terminate the owned process group gracefully, wait for the bounded grace period, and force only validated survivors.
- [x] 1.4 Add focused tests for normal completion, interruption, a stubborn owned child, PID identity mismatch, atomic record cleanup, and refusal to terminate an unowned process.
- [x] 1.5 Commit game supervision and its tests as one verified change.

## 2. Make maps state transactional

- [x] 2.1 Replace direct link mutation with a transaction that records absent or symlink state and refuses a regular file or directory.
- [x] 2.2 Put Vite process shutdown and link restoration in one `try`/`finally` path used for normal exit, signals, startup failure, and runtime failure.
- [x] 2.3 Detect concurrent link replacement and fail closed without overwriting the newer state.
- [x] 2.4 Add focused tests for prior-target restoration, initially absent state, regular-file refusal, runtime failure, interruption, and concurrent replacement.
- [x] 2.5 Commit maps lifecycle ownership and its tests as one verified change.

## 3. Prove real process ownership

- [x] 3.1 Launch the selected CrossOver game through `uv run erenshor mod launch` and confirm that the command remains active while the game runs.
- [x] 3.2 Stop the supervised launch and confirm the game, its session `conhost.exe`, and its Unity crash handler exit while unrelated bottle processes remain.
- [ ] 3.3 Run `uv run erenshor maps dev` with a non-main variant, interrupt it, confirm its port is released, and confirm the exact prior database-link state is restored.
- [ ] 3.4 Simulate an identity mismatch in the recovery path and confirm that the candidate process is reported but not signaled.

## 4. Remove compensating teardown

- [ ] 4.1 Delete `.agent/skills/refreshing-game-data/scripts/teardown_session.py` after the real ownership gates pass.
- [ ] 4.2 Remove the routine end-of-session teardown section and replace relevant recovery text with exact-identity inspection guidance.
- [ ] 4.3 Remove current instructions to quit Unity Hub or kill `UnityLicensingClient`; retain incident evidence only where it explains an observed historical failure.
- [ ] 4.4 Search the repository for the removed script, broad port/process-age cleanup, and global process-name kill instructions; remove every current route.
- [ ] 4.5 Commit the teardown removal, skill update, and related documentation cleanup as one verified change.

## 5. Validate the change

- [ ] 5.1 Run the focused Python tests for mod launch, process sessions, and maps development.
- [ ] 5.2 Run `nix develop --command uv run ruff check` and the repository type checker for the changed Python paths.
- [ ] 5.3 Run the repository's agent-instruction and skill-reference checks.
- [ ] 5.4 Run `openspec validate own-refresh-session-resources --strict`.
- [ ] 5.5 Run the applicable repository pre-push gate before archive.
