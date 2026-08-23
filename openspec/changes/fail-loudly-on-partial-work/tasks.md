## 1. Baseline

- [ ] 1.1 Record a healthy end-to-end run of capture, image processing, wiki generation, and extract rip against valid inputs. Keep checksums of the outputs so later steps compare against a measurement.
- [ ] 1.2 Record the current `uv run erenshor test ci` result and the current count of commands carrying a precondition declaration.

## 2. Capture reports what it did

- [ ] 2.1 Change `application/capture/orchestrator.py` so a failed zone is collected rather than skipped, and the run reports every failure.
- [ ] 2.2 Change `cli/commands/capture.py` so the completion message is emitted only when no zone failed, and a partial run exits non-zero and states that the output is partial.
- [ ] 2.3 Add a regression test proving one failing zone makes the command exit non-zero and name that zone.
- [ ] 2.4 Confirm a run with every zone valid produces output identical to the task 1.1 baseline.

## 3. A failed image comparison is not `unchanged`

- [ ] 3.1 Change `application/services/image_registry.py` so a perceptual-hash failure raises instead of setting `change_type='unchanged'`, `is_changed=False`, and `similarity_score=1.0`.
- [ ] 3.2 Change the hash fallback that substitutes database values so it raises rather than reporting a stored value as a fresh measurement.
- [ ] 3.3 Add a regression test proving an image whose comparison raises is never selected as needing no upload.
- [ ] 3.4 Confirm an image run over valid inputs selects the same set as the task 1.1 baseline.

## 4. Release versioning fails instead of restarting

- [ ] 4.1 Change `application/mods/release.py` so a failed vault version lookup raises a named error instead of returning an empty collection.
- [ ] 4.2 Keep the distinction between a reachable registry that reports nothing published and a lookup that failed.
- [ ] 4.3 Add a regression test proving an unreachable registry does not produce a revision number.

## 5. A manifest that cannot be read is not rewritten

- [ ] 5.1 Change `application/extract/rip_workflow.py` so a missing or malformed dependency manifest raises and names the file, instead of returning an empty mapping.
- [ ] 5.2 Confirm the restore step that writes the manifest cannot run after a failed read.
- [ ] 5.3 Add a regression test for both the absent and the malformed manifest.

## 6. Generation refuses to emit lossy output

- [ ] 6.1 Change `application/wiki/generators/pages/zones.py` so absent or unconfigured zone-position input fails instead of producing an empty key set.
- [ ] 6.2 Add a regression test proving wiki pages are not emitted without map links when that input is missing.

## 7. Name the missing program

- [ ] 7.1 Change `infrastructure/assetripper/assetripper.py` to confirm `curl` is resolvable before probing, and fail naming the program rather than returning `False` and waiting for the startup timeout.
- [ ] 7.2 Change the export-log monitor so a read error is reported with its cause rather than logged at debug and polled past.
- [ ] 7.3 Add a resolvability check with a named error to `application/code_facts/runner.py`, matching the one in `application/export_surface/runner.py`.
- [ ] 7.4 Convert raw subprocess failures in the maps helper into named errors identifying the program.
- [ ] 7.5 Add tests for each named failure.

## 8. Ambiguity is distinct from absence

- [ ] 8.1 Change `application/mods/local_workflow.py` so several matching CrossOver installations raise and name every candidate, instead of warning and returning `None`.
- [ ] 8.2 Change the unreadable-manifest path so it names the record instead of reporting absence.
- [ ] 8.3 Preserve the subprocess cause in `cli/preconditions/checks/maps.py` rather than reporting a generic authentication failure.
- [ ] 8.4 Add tests for two matching bottles, an unreadable manifest, and no installation, asserting three distinct reports.

## 9. Precondition coverage

- [ ] 9.1 Write down the rule that decides which commands declare preconditions, and list the commands that mutate state outside the process.
- [ ] 9.2 Add declarations to the `capture` and `images` command groups. Run the suite.
- [ ] 9.3 Add declarations to the `mod` command group, including build, deploy, activate, release, and launch. Run the suite.
- [ ] 9.4 Add declarations to the remaining `maps`, `wiki`, `guide`, `eval`, and `extract` commands that mutate state. Run the suite.
- [ ] 9.5 Record which commands were deliberately left undeclared because they only read, so the omissions are intentional and reviewable.

## 10. Verification and documentation

- [ ] 10.1 Run each affected pipeline end to end against valid inputs and confirm byte-identical output against the task 1.1 baseline.
- [ ] 10.2 Run `uv run erenshor test ci` and compare against the task 1.2 result.
- [ ] 10.3 Document the failure rule where contributors will meet it, in present tense, describing the current behaviour only.
- [ ] 10.4 Run `openspec validate fail-loudly-on-partial-work --strict`.
- [ ] 10.5 Search the application and infrastructure packages for remaining handlers that convert a failure into a value, and either fix each or record why it is correct.
