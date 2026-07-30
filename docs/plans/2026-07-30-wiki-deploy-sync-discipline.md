---
title: Wiki Deploy and Sync Discipline
type: spec
status: draft
created: 2026-07-30
parent: 2026-07-09-erenshor-planning-overview
---

# Wiki Deploy and Sync Discipline

**Goal:** Replace ad-hoc wiki deploys with a discipline that cannot silently break
production. The motivating incident is real: `WoWBot` deployed Lua-only `Quest`,
`Zone`, and `Stance` template bodies on 2026-07-14 and again on 2026-07-22, an admin
reverted both rounds within a minute, and nothing in the tooling detected either the
breakage or the reverted state afterwards. A separate incident, the 5,099,976-byte
character data module against a 4,194,304-byte page limit, could only ever have failed
at the API because nothing checks size before writing.

**Constraint that shapes everything:** MediaWiki's Action API has **no multi-page
transaction**. Each `action=edit` commits independently. Atomicity is therefore
impossible and must be replaced by preflight, ordering, checkpointing, verification,
and rollback.

## What the repo already gets right

- `client.safe_edit_page` sends `baserevid` plus `starttimestamp` plus an md5 and an
  `assert`, so the server rejects the write if the page moved since the snapshot.
  `safe_create` sends `createonly`. This is the correct use of the documented
  conflict guards.
- `deploy-repo-pages` and `deploy-interface` use those guarded paths, take one batched
  live snapshot, checkpoint a manifest before and after each mutation, and abort on
  the first guarded failure.
- Manifests record title, source path, source SHA, stage, content model, ownership,
  old and new revision ids and timestamps, and a rollback sidecar.
- Deploy stages are ordered: generated data, then Lua modules, then Cargo
  declarations, then templates, then content pages.
- Accounts are correctly separated: the bot for content, `WoWMuch@InterfaceDeploy`
  for the `MediaWiki` namespace, anonymous reads for inventory.

## Gaps

### 1. No drift detection, which is the gap that caused the incident

No command answers "does live currently match what we last deployed". `wiki
inventory-templates` writes a local `ownership.yml` from an API inventory.
`wiki sync-interface` mirrors fixed live interface pages into a gitignored directory.
Neither compares repo to live, and neither produces a drift verdict.

Consequence: after the admin reverted three templates, the repo had no way to know,
and the next deploy would have re-pushed the same broken bodies.

### 2. No preflight against production limits

Nothing checks page size against `maxarticlesize`, and nothing checks Lua memory or
parser limits. A 5 MB module is "deployable" as far as the tooling is concerned.

### 3. Two unguarded write paths

- Legacy `WikiDeployService.edit_page` sends no `baserevid`, `basetimestamp`, or
  `starttimestamp`, so it silently clobbers a concurrent human edit. It also catches
  per-page errors and **continues**, so it can partially deploy with no durable
  manifest.
- `refresh.refresh_item_owners_for_source_changes` null-edits through the same
  unguarded `edit_page`, so a human edit racing a refresh is lost.

### 4. No pre-deploy template gate

MediaWiki ships exactly the right mechanism and it is installed. `TemplateSandbox`
1.1.0 plus `action=parse` accepts `templatesandboxtitle`, `templatesandboxtext`,
`templatesandboxprefix`, and `templatesandboxcontentmodel`, and it supports Scribunto.
Rendering a set of canary pages with the candidate template body and diffing the HTML
against production would have caught both revert incidents before any write.

### 5. No job-queue awareness

`refresh.py` purges dependents and null-edits owners but never polls for completion.
Cargo recreate runs one job per contributing page. On shared hosting `$wgJobRunRate`
governs progress, so completion must be observed rather than assumed.

### 6. Cargo recreate is not automatable by the bot

`WoWBot` lacks `recreatecargodata`. The tooling prints an instruction to use
`Special:CargoTables` and stops, which is correct today but leaves the most dangerous
step entirely manual and unrecorded.

### 7. CI runs no wiki checks

`erenshor test wiki` does run `import_pages.py`, `smoke_test.py`, `cargo_check.py`,
and `tests/system/wiki`, and `--clean-parity` adds the clean-parity harness. But
`.github/workflows/ci.yml` never invokes the wiki leaf: `test-unit` runs `tests/unit`
and `test-contract` runs `tests/contract`. Every wiki safety check depends on a human
remembering a manual command.

### 8. The harness is not a production proxy

`wiki-dev/README.md` states this itself. It runs stock upstream Cargo, not the
LIBRARIAN fork. It uses local credentials with local rights. `import_pages.py`
discovers `wiki/modules` and fixtures, **not** the generated
`variants/main/wiki/lua` data, so it cannot exercise the oversized character module or
real module limits, and it writes with only `createonly`/`nocreate` and a client-side
comparison, so it does not model race-safe production writes. It structurally cannot
catch LIBRARIAN quirks, production rights, `maxarticlesize`, live concurrency, or
queue lag.

## Design

Five gates, in order. A deploy that skips a gate is not a deploy.

### Gate 1 — Preflight, before any write

- Reject any page whose serialized size exceeds `maxarticlesize`, read live from
  `action=query&meta=siteinfo&siprop=general`, with a configurable headroom margin.
- For Lua modules, parse a representative consumer page with `action=parse` and
  `prop=limitreportdata`, and reject if Lua memory or time exceeds a fraction of the
  reported ceiling. Current live ceilings are 52,428,800 bytes and 15.000 seconds, and
  the heaviest page today sits at 19 percent of memory.
- Assert the deploying account holds every right the plan needs, extending the
  existing `editinterface` dry-run check to `recreatecargodata` when the plan touches
  Cargo declarations.

### Gate 2 — Drift verification

- For every managed title, fetch `action=query&prop=revisions&rvprop=sha1|ids|timestamp`
  in batches of up to 50. The server-side SHA1 makes this cheap and needs no content
  transfer.
- Compare against the last deployment manifest. Classify each page as unchanged,
  drifted, or missing.
- **On drift, stop and report. Never overwrite without an explicit force flag.** Offer
  two resolutions: adopt live into the repo, or confirm the overwrite.
- Do not rely on `list=recentchanges` for this. Bot-flagged edits are hidden from
  recent changes by default, so the revision SHA1 comparison is the reliable signal.

### Gate 3 — Canary render, for templates and modules only

For each candidate template body, and for a set of canary pages chosen to cover both
rendering branches:

```
action=parse&title=<canary>&templatesandboxtitle=Template:<X>
  &templatesandboxtext=<candidate>&templatesandboxcontentmodel=wikitext
  &prop=text|parsewarnings
```

Diff the returned HTML against a plain `action=parse` of the same page and require no
new `parsewarnings`, no `Script error`, and no `class="error"`. Gate the deploy on the
diff being inside an approved allowlist.

The canary set must include, per entity type, at least one page that exercises the
legacy branch and one that exercises the new branch. That is precisely the check both
revert incidents lacked.

### Gate 4 — Ordered, checkpointed, guarded write

- Keep the existing stage order and extend it: declarations before stores, stores
  before dependents.
- Every write uses `baserevid` plus `starttimestamp`. Delete the unguarded
  `edit_page` path, including for null-edits and legacy article deploys.
- Send `maxlag=3` and back off exponentially on maxlag and on HTTP 429. Keep the bot
  flag. Use a descriptive User-Agent.
- Checkpoint after every mutation so an interrupted run is resumable rather than
  ambiguous.
- On any guarded failure, stop. Never continue past a failure the way the legacy
  article deploy does.

### Gate 5 — Post-deploy verification and Cargo migration

- Re-verify each written page's SHA1 against what was intended.
- Purge dependents with `forcelinkupdate`, then **poll** rather than assume.
- For a schema change, follow wiki.gg's documented procedure exactly:
  1. Edit the declare-only template.
  2. Recreate **with a replacement table**, so the existing table stays queryable
     read-only while `__NEXT` populates. Replacement is the default, not the
     exception.
  3. Wait for the job queue. The `Special:CargoTables` banner disappearing is the
     completion signal.
  4. Switch in at `Special:CargoTables`. This is a manual admin action with no API.
  5. Only then edit the storing templates. **New fields are invisible to queries
     until the switch, so a storing template saved earlier will error.**
- Run every recreate as `WoWMuch` or another sysop-equivalent account, and record the
  operation in the manifest even though a human performs the switch-in.

### Ownership convention

Make collision structurally impossible rather than a matter of care.

- Bot-owned: `Module:Erenshor/*`, `Template:*` for repo-owned templates, and the
  `MediaWiki` namespace gadget pages.
- Human-owned: article prose, community sections, and the future `{{ItemSource}}` and
  `{{SpawnPoint}}` rows.
- Every bot-owned page carries a documentation notice stating that it is generated and
  that edits will be overwritten, plus a pointer to the repo path.
- Drift on a bot-owned page is an error. Drift on a human-owned page is expected and
  must never be touched by a deploy.

## Acceptance criteria

- A `wiki verify` command reports, for every managed page, whether live matches the
  last manifest, using server-side SHA1, and exits non-zero on unexpected drift.
- `deploy-repo-pages` refuses to run when drift is detected, unless forced, and the
  refusal names every drifted page.
- No write path in the repo omits `baserevid` and `starttimestamp`. The unguarded
  `edit_page` is deleted, not merely avoided.
- A deploy that would exceed `maxarticlesize` fails in preflight, naming the page and
  the overage, and a regression test covers the oversized character module case.
- A template or module deploy renders the canary set through `templatesandboxtext` and
  fails on new parse warnings, script errors, or unapproved HTML diffs.
- Reverting the three template incidents is reproducible as a test: deploying a
  Lua-only `Quest` body against a legacy canary page fails the canary gate.
- `refresh` polls for purge and job completion instead of assuming it.
- CI invokes the wiki leaf, so harness import, smoke, Cargo check, and the module size
  gate all run automatically.
- The Cargo migration runbook exists as an executable command sequence that stops at
  the manual switch-in and records it.

## Explicitly out of scope

- Multi-page atomicity. It does not exist in MediaWiki and no amount of tooling
  provides it. The compensating controls above are the answer.
- Automating the `Special:CargoTables` switch-in. There is no API.
- Making the harness a faithful production proxy. It runs a different Cargo
  implementation. Treat its green result as necessary and never sufficient, and
  reserve LIBRARIAN-specific verification for a live canary.

## References

- API:Edit conflict guards — https://www.mediawiki.org/wiki/API:Edit
- API:Revisions, `rvprop=sha1` — https://www.mediawiki.org/wiki/API:Revisions
- API:Parsing wikitext, sandbox parameters — https://www.mediawiki.org/wiki/API:Parsing_wikitext
- Extension:TemplateSandbox — https://www.mediawiki.org/wiki/Extension:TemplateSandbox
- Extension:Cargo, storing data and recreation — https://www.mediawiki.org/wiki/Extension:Cargo/Storing_data
- wiki.gg, recreating Cargo tables — https://support.wiki.gg/wiki/Cargo/recreating_tables
- Manual:Maxlag parameter — https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
- API:Etiquette — https://www.mediawiki.org/wiki/API:Etiquette
- Manual:Bots — https://www.mediawiki.org/wiki/Manual:Bots
