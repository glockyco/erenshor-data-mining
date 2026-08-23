## Context

See proposal.md - Why.

Each statement was checked against the code rather than against another document.

| Statement | Code | Verdict |
|---|---|---|
| `.env.example` lists four precedence layers led by environment variables | `infrastructure/config/loader.py:125-203` merges `config.toml` then `.erenshor/config.local.toml` | two layers, no environment layer |
| `.env.example` advertises database, cache, output, and report variables | the package reads `ERENSHOR_GAME_PATH`, `ERENSHOR_LUNARIS_DLL`, `ERENSHOR_LUNARIS_LIB_DIR`, `ERENSHOR_MAPS_DATABASE_PATH` | advertised set and read set do not intersect |
| `README.md:82` "CrossOver or another Windows runtime" | `mods/local_workflow.py:692-723` invokes CrossOver `cxstart` | one runtime |
| `docs/architecture-analysis.md` names three paths | none of the three exists | stale |
| bottle root and launcher defined in `mod.py:44-45` | `local_workflow.py:42-43` defines and exports both at `:736-737` | duplicated |

One finding inverted on inspection and is worth recording. The legacy per-zone map page holds `new WebSocket('ws://localhost:18584')` at `src/maps/src/routes/maps/[mapName]/+page.svelte:214`, and the catalog builds only `InteractiveMapCompanion` on `18585`. Nothing in this repository serves `18584`. Players running the previous companion mod do.

The socket is therefore deliberate, and the commit that retired the plural mod says so while deleting 947 lines of it: the legacy consumer is preserved so existing installations continue to provide player positioning. That reason exists in one commit message and nowhere a reader will look. The README states the behaviour without the reason, and the code site carries only tactical comments about message shape.

This is the inverse of the other findings. Elsewhere a document claims something the code does not do. Here the code does something deliberate that the documents do not explain.

The same handler also carries a branch that discards messages holding a `type` field, commented as ignoring messages from the new mod. The dates show why it exists and why it no longer can fire.

| date | event |
|---|---|
| 2026-01-16 | `InteractiveMapCompanion` is created and serves `18584` |
| 2026-01-18 | `5fba5e94` moves it to `18585`, because both mods on one port conflicted |
| 2026-02-14 | `3bf8ba6a` adds the Thunderstore release path |

The new mod held the old port for two days, entirely before it had a release path, so no installed copy of it serves `18584`. The only client that does is the retired mod, whose `CreateMessage` serialises `scene`, `x`, `y`, `z`, `fx`, `fy`, `fz`, and whose runtime contains no occurrence of `type` in any case. The branch guards against a sender that has never existed on that port.

## Goals / Non-Goals

**Goals**

- Statements a contributor reads first are the ones most worth trusting.
- One owner for each environment-specific fact.
- A check that keeps referenced paths honest, rather than a one-time sweep.

**Non-Goals**

- Runtime behaviour, other than the constants collapsing to an import.
- Where game files live, which `single-game-installation` decides. This change describes the result.
- Rewriting planning artifacts. They record decisions with dates and are exempt from the present-tense rule.

## Decisions

**Where a document and the code disagree, the code wins, with two exceptions.** The exceptions are the `game_install` fallback and the tracked game-files default, where the documented intent is defensible and the resolution order may be the thing to correct. Both are recorded as questions rather than resolved by editing the prose to match whatever the code happens to do. Making a document agree with an accident is how the accident becomes a requirement.

**The CLI imports the constants rather than the application layer losing them.** `local_workflow` already exports both names. The alternative, a new shared constants module, adds a module to hold two lines that already have an owner.

**Referenced paths get a check, not just a fix.** Alternative: correct the three stale paths and move on. Rejected because the same rot returns. A check that extracts repository-relative paths from active documents and asserts they exist is cheap and turns a recurring cleanup into a gate.

**Present-tense applies to active documents only.** Planning artifacts under the plans directory record what was decided and when. Stripping their history would destroy their purpose. The rule is scoped to documents that tell a reader how the project works.

**Naming an older client is present tense, not history.** The present-tense rule as first drafted would have licensed deleting the README sentence about port `18584`, because it names a retired mod. That would have removed the only user-facing trace of a live compatibility surface, which is the opposite of the goal. The distinction the specification draws is the subject of the sentence. "We used to listen on this port" is history. "We listen on this port, for these clients" is current behaviour that happens to name something old. The second is required, not merely permitted.

**Keeping the socket and removing the dead branch are separate calls.** The socket serves real installations and stays indefinitely. The `type` branch serves nothing, and keeping it would leave the handler implying that two kinds of client reach this port when one does. Alternative: keep the branch as cheap insurance. Rejected because it is insurance against an event the release history rules out, and because it is the reason the surface reads as accidental. The check is which senders exist, not whether the code costs anything.

**A compatibility surface states its removal condition, even when there is none.** Alternative: document who it serves and stop. Rejected because the next reader inherits the same question this investigation started with, which is whether the thing is deliberate or forgotten. "Kept indefinitely" answers it in three words and is a true statement when nothing is planned. Inventing a removal trigger nobody intends to measure would be worse than admitting there is none.

## Risks / Trade-offs

**A path check produces false positives on prose that contains something path-shaped.** → Scope it to fenced or backticked repository-relative paths and allow an explicit exemption list, kept short.

**Correcting `.env.example` may remove a variable somebody relies on.** → The package does not read them, so nothing that works today stops working. The four variables the package does read gain documentation they lack.

**Deferring the legacy socket leaves a shim in place.** → It is recorded in the proposal with its file and line, and the README continues to describe it correctly, so nothing is hidden while the decision waits.

## Migration Plan

1. Correct the statements whose verdict is unambiguous: `.env.example`, the launch prerequisite, the stale architecture paths, and the duplicated constants.
2. Add the path-reference check and let it find whatever the manual sweep missed.
3. Record the tracked-configuration arrangement in a comment.
4. Take the two deferred decisions to the maintainer, then reconcile the `game_install` documentation with whichever answer wins.

Rollback is per commit, and no step changes behaviour except the constant import, which is verified by the existing tests for launch and discovery.
