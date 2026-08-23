## 1. Baseline

- [ ] 1.1 Record the current `uv run erenshor test ci` result, so the documentation work can prove it changed nothing.
- [ ] 1.2 List every repository-relative path referenced by active documents and record which of them do not exist.

## 2. Configuration precedence

- [ ] 2.1 Rewrite the precedence section of `.env.example` to the layers `infrastructure/config/loader.py` applies, in the order it applies them.
- [ ] 2.2 Remove the advertised variables the package does not read.
- [ ] 2.3 Document the environment variables the package does read, with the effect of each.
- [ ] 2.4 Confirm no other document repeats the removed precedence claim.

## 3. Launch prerequisite

- [ ] 3.1 Change the macOS launch prerequisite in `README.md` to name CrossOver, matching `mods/local_workflow.py`.
- [ ] 3.2 Remove the SteamCMD prerequisite from `README.md`. `single-game-installation` removes the tool, so the prerequisite describes something the project no longer uses.
- [ ] 3.3 State that game files come from the Steam client inside the bottle, matching what the tooling reports when an installation is missing.

## 4. Stale references

- [ ] 4.1 Correct or remove the three nonexistent paths named in `docs/architecture-analysis.md`.
- [ ] 4.2 Remove the historical narrative from that document, leaving a description of the current architecture.
- [ ] 4.3 Resolve every other missing path found in task 1.2.

## 5. One definition per constant

- [ ] 5.1 Import the bottle root and launcher path in `cli/commands/mod.py` from `application/mods/local_workflow`, which already exports both.
- [ ] 5.2 Confirm the existing launch and discovery tests still pass, including the tests that patch these constants.
- [ ] 5.3 Search for other environment-specific values defined more than once and record what is found.

## 6. A check that keeps references honest

- [ ] 6.1 Add a check that extracts repository-relative paths from active documents and fails when one does not exist.
- [ ] 6.2 Give it a short, explicit exemption list for intentional examples.
- [ ] 6.3 Wire it into the repository checks and confirm it fails when a path is removed.

## 7. Document the compatibility surface

- [ ] 7.1 Record at `src/maps/src/routes/maps/[mapName]/+page.svelte:214` why the socket connects to port `18584`: nothing in this repository serves it, and players running the previous companion mod do.
- [ ] 7.2 State that the surface is kept indefinitely. This is decided, so record it as a fact rather than leaving the question open.
- [ ] 7.3 Extend the README paragraph so it gives the reason alongside the behaviour it already describes.
- [ ] 7.4 Remove the `message.type` branch and the "Ignore new mod messages" comment from the same handler. The only client that serves this port emits `scene, x, y, z, fx, fy, fz` and no `type` field, so the branch cannot be taken. Keep the socket and the old-format destructuring.
- [ ] 7.5 Verify the removal against the retired mod's payload rather than against the comment, then confirm the legacy page still tracks position with an old-format message.
- [ ] 7.6 Search for other interfaces kept for clients the project no longer builds, and document each or record that none exist.

## 8. Present tense

- [ ] 8.1 Read the active documents and remove statements describing previous behaviour, removals, or deprecations.
- [ ] 8.2 Keep statements that name an older client in order to say what the code accepts today. Those are current behaviour and the compatibility requirement demands them.
- [ ] 8.3 Leave planning artifacts unchanged, because they record decisions with dates.

## 9. Verification

- [ ] 9.1 Run `uv run erenshor test ci` and compare against task 1.1.
- [ ] 9.2 Run the new path check over the whole documentation set and confirm it passes.
- [ ] 9.3 Run `openspec validate describe-the-supported-setup --strict`.
- [ ] 9.4 Confirm no active document lost a statement that the compatibility requirement demands.
- [ ] 9.5 Confirm no document still describes a configured game-files path, a non-CrossOver install, or SteamCMD, all of which `single-game-installation` removes.
