## Context

See proposal.md - Why.

The sites are scattered but the shape repeats. An exception handler is asked a question it cannot answer, and it answers anyway with the value that lets execution continue. The audit found eleven instances, and their severity depends entirely on what consumes the fabricated value.

```
handler converts failure to ...        consumer treats it as ...        result
-------------------------------------  ------------------------------  --------------------------
skipped unit                           completed batch                  partial output, exit 0
change_type='unchanged'                nothing to upload                stale published image
{} versions                            nothing published yet            reused release revision
{} dependencies                        manifest to rewrite              manifest replaced from nothing
set() map keys                         zone has no map                  wiki pages without links
False (curl absent)                    server not up yet                30s wait, wrong cause
None (ambiguous install)               no installation                  unactionable report
```

The first four persist or publish. Those are the ones that matter.

The repository already contains the correct pattern in three places, so this change has a model to follow rather than one to invent: the SteamCMD wrapper checks resolvability and raises a typed error carrying remediation, the Lua validation probes each tool and raises a named error when none is present, and golden capture aggregates per-family errors and refuses to replace the baseline.

## Goals / Non-Goals

**Goals**

- One owner for the decision to fail: the operation that detected the condition, not a caller reading a sentinel.
- Failure reports that name the operation, the input, and the cause.
- Precondition coverage that follows a stated rule rather than the order commands were written.

**Non-Goals**

- Retry, backoff, or degraded modes.
- Changing healthy-run output or exit status.
- A new error hierarchy. Existing typed errors extend where they fit.
- Resumable partial runs.
- The question of whether a game path configured as read-only should also be writable by download and deploy. That belongs to `describe-the-supported-setup`.

## Decisions

**Batch commands aggregate, then fail.** Alternative: stop at the first failed unit. Rejected because an operator running a long capture wants every failure in one report, not one per re-run. Continuing to collect is allowed. Reporting success is not. This matches the golden-capture aggregation the repository already has.

**A failed measurement raises rather than returning a sentinel.** Alternative: a third classification such as `unknown` alongside `changed` and `unchanged`. Rejected for the image path because every consumer would need to learn the new value, and a consumer that did not would treat it as falsy and skip the upload, which is the current bug wearing a new name. Raising forces the caller to decide.

**Missing input fails at the reader, not the writer.** The rip workflow currently reads a manifest into `{}` and then writes a manifest built from that reading. Guarding only the write would still lose the distinction between "no dependencies" and "could not tell". The reader raises, so the writer never runs.

**Resolvability is checked before invocation, not inferred from the exception.** Alternative: catch `FileNotFoundError` around each call and re-raise with a better message. Rejected because the same exception type arises from a missing input file, so the improved message could name the wrong cause. An explicit check answers exactly one question.

**Precondition coverage follows a rule, not a list.** The rule is that a command mutating state outside the process declares its preconditions. A list would drift as commands are added. Stating the rule makes an undeclared new command a reviewable omission.

**Ambiguity gets its own outcome.** Discovery currently warns and returns `None`, which the caller reports as a missing installation. The operator's remedy for ambiguity is to remove a bottle, and for absence is to install the game. One report cannot serve both.

## Risks / Trade-offs

**Commands that quietly degraded will now fail, including in automation.** → This is the intended break and it is named in the migration boundary. The failures it surfaces are conditions that were already producing wrong output.

**A long capture that previously produced partial tiles now exits non-zero.** → Output already written is retained and the report states that it is partial. No cleanup is attempted, because deleting an operator's completed work to signal failure is worse than reporting it.

**Widening precondition coverage could reject a workflow that currently works.** → Add declarations per command group with the suite run between groups, so a rejection is attributed to the group that introduced it.

**Raising on a failed image hash could stop a large upload run on one bad file.** → Accepted and consistent with the batch rule: the run reports every failed image and fails. The alternative is the defect being fixed.

## Migration Plan

1. Land the four persisting or publishing sites first, worst first: capture reporting, image classification, release version lookup, manifest reading. Each is one commit with its own regression test.
2. Land the reporting fixes that change no output: named external-program failures, preserved precondition causes, ambiguity as an error.
3. Land precondition declarations per command group, running the suite between groups.
4. Run each affected pipeline end to end against valid inputs and confirm the output is byte-identical to a run recorded before step 1.

Rollback is per commit. The order is chosen so that the highest-severity fixes land first and can be kept if a later group is reverted.
