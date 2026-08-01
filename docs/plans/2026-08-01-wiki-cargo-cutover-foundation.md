---
title: Wiki Cargo Cutover Foundation
type: plan
status: draft
created: 2026-08-01
parent: 2026-07-09-erenshor-planning-overview
---

# Wiki Cargo Cutover Foundation

Build and prove the shared Lua/Cargo foundation for all seven entity types without
adding `lua=1` to any production article. This plan ends at verified sandbox and
infrastructure readiness. Per-type production article conversion belongs to
`2026-07-11-wiki-article-cutover`.

## Preconditions and boundaries

The permanent selector and identity contract is defined by
`2026-06-04-wiki-cargo-data-architecture`: exact `lua=1` alone selects the generated
branch, while `stablekey` identifies one entity after selection. The four-case matrix
must exist for Item, Character, Spell, Skill, Stance, Quest, and Zone.

This plan cannot implement or create production infrastructure until the parity,
schema, and deploy/sync specifications receive human approval. It preserves the
architecture's Cargo ownership, replacement-table, refresh, identity, and future
community-row design. It does not convert articles, retire a legacy template branch,
retire a Jinja generator, or implement community-row authoring.

## Tasks

### Task 1: Approve the three cutover contracts

- [ ] Review and approve `2026-08-01-wiki-render-parity-gate`,
  `2026-07-30-wiki-cargo-schema-revision`, and
  `2026-07-30-wiki-deploy-sync-discipline`. Record approval by promoting each
  technical contract from `draft` to `active`. Implementation cannot begin while
  any of the three remains draft.
  - **Owning specs:** the three specifications named above.
  - **Affected paths:** `docs/plans/2026-08-01-wiki-render-parity-gate.md`,
    `docs/plans/2026-07-30-wiki-cargo-schema-revision.md`, and
    `docs/plans/2026-07-30-wiki-deploy-sync-discipline.md`.
  - **Verification:** run `omp-plans index && omp-plans check && omp-plans status
    --active`. Required result: all three specs are active, navigation is current,
    and validation exits zero.
  - **Commit:** `docs(plans): approve wiki cutover contracts`.

### Task 2: Implement deterministic local render parity

- [ ] Implement the local legacy-versus-Lua comparison and deterministic JSON plus
  human-readable reports defined by the parity spec. Cover named values,
  normalization, multi-entity identity, exact allowlisting, all selector cases, and
  `not_exercised`. Add the regression fixture in which a Lua renderer drops a visible
  field and prove the new gate fails it. After task 1, this task may proceed
  independently of Cargo schema implementation.
  - **Owning spec:** `2026-08-01-wiki-render-parity-gate`.
  - **Affected paths:** `wiki-dev/parity_check.py`,
    `wiki-dev/parity-allowlist.toml`, `wiki-dev/fixtures/`, and
    `tests/unit/test_wiki_dev_parity.py`.
  - **Verification:** run `uv run pytest tests/unit/test_wiki_dev_parity.py -q` and
    `uv run erenshor test wiki --clean-parity`. Required result: the suite passes,
    repeated clean reports are byte-identical, and the field-loss regression records
    `failed` rather than `passed`.
  - **Commit:** `feat(wiki): add deterministic render parity gate`.

### Task 3: Apply the exact selector matrix to every entity template

- [ ] Implement exact `lua=1` selection for Item, Character, Spell, Skill, Stance,
  Quest, and Zone. No flag stays on the verbatim legacy path with no Cargo write.
  Exact flag plus a valid key enters Lua and Cargo. Exact flag plus a missing or
  invalid key emits the existing diagnostic and stores nothing. A key without the
  flag stays legacy and stores nothing. Adopt the live legacy Ability body as
  specified in task 6 before exercising Spell and Skill in a live canary.
  - **Owning specs:** `2026-06-04-wiki-cargo-data-architecture` §5 and
    `2026-08-01-wiki-render-parity-gate`.
  - **Affected paths:** `wiki/templates/Item.wiki`,
    `wiki/templates/Character.wiki`, `wiki/templates/Spell.wiki`,
    `wiki/templates/Skill.wiki`, `wiki/templates/Stance.wiki`,
    `wiki/templates/Quest.wiki`, `wiki/templates/Zone.wiki`, and
    `wiki-dev/fixtures/`.
  - **Verification:** run `uv run erenshor test wiki --clean-parity`. Required
    result: all seven templates pass the four-case selector matrix, and every legacy
    case has zero Cargo rows.
  - **Commit:** `feat(wiki): standardize Lua cutover selectors`.

### Task 4: Correct generated payloads and Cargo schemas

- [ ] Implement `2026-07-30-wiki-cargo-schema-revision`. Strip dead Character
  payload before measuring. Enforce at least 25 percent module-size headroom below
  4,194,304 bytes and shard only if payload reduction cannot meet that gate.
  Implement the `ItemEffects` junction and every declared schema correction. Move
  all Cargo declarations into declare-only templates. Do not run a production
  create or recreate in this task.
  - **Owning spec:** `2026-07-30-wiki-cargo-schema-revision`.
  - **Affected paths:** `wiki/templates/`,
    `variants/{variant}/wiki/lua/Erenshor/Data/`,
    `src/erenshor/application/wiki_lua/`, and `wiki-dev/cargo_check.py`.
  - **Verification:** run `uv run erenshor test wiki --clean-parity`. Required
    result: every generated module has at least 25 percent size headroom, all
    declarations agree with the spec, and local recreation produces the specified
    `ItemEffects` and other junction row counts.
  - **Commit:** `feat(wiki): revise Cargo schema before creation`.

### Task 5: Implement reusable deploy and synchronization gates

- [ ] Implement live-size and rights/protection preflight, SHA drift detection,
  TemplateSandbox candidate rendering, guarded writes, per-mutation checkpoints,
  maxlag and HTTP 429 backoff, rollback sidecars, purge and job polling, and the
  verified manual-browser handoff. Delete every unguarded write path. Add the wiki
  leaf to CI as a required check.
  - **Owning spec:** `2026-07-30-wiki-deploy-sync-discipline`.
  - **Affected paths:** `src/erenshor/application/wiki_deploy/`,
    `src/erenshor/cli/commands/wiki.py`, `wiki-dev/`,
    `tests/system/wiki/`, and `.github/workflows/ci.yml`.
  - **Verification:** run `uv run pytest tests/system/wiki -q` and
    `uv run erenshor test wiki --clean-parity`. Required result: drift,
    `cascadeprotected`, oversized modules, unapproved sandbox diffs, and stale
    revisions all fail before mutation. A verified handoff resumes only after raw
    live SHA equality, and the CI configuration invokes the wiki leaf.
  - **Commit:** `feat(wiki): enforce guarded deploy synchronization`.

### Task 6: Deploy missing modules without converting articles

- [ ] Deploy `Module:Erenshor/Data/Characters`, `Data/Quests`, `Data/Stances`, and
  `Data/Zones` through the guarded deploy path while every production article stays
  on the legacy branch. Adopt live `Template:Ability` byte for byte into repository
  ownership before Spell or Skill canaries. Verify every deployed module against the
  25 percent size-headroom gate and record source and live SHAs in the manifest.
  - **Owning specs:** `2026-07-30-wiki-cargo-schema-revision`,
    `2026-07-30-wiki-deploy-sync-discipline`, and
    `2026-08-01-wiki-render-parity-gate`.
  - **Affected paths:** `variants/main/wiki/lua/Erenshor/Data/`,
    `wiki/templates/Ability.wiki`, `wiki_inventory/templates.py`, and
    `src/erenshor/application/wiki_deploy/`.
  - **Verification:** run `uv run erenshor wiki verify` and the deploy manifest's
    module-size verification command. Required result: all four data modules and the
    adopted Ability template have exact intended live SHAs, every module retains the
    required headroom, and a main-namespace source scan still reports zero
    production article uses of `lua=1`.
  - **Commit:** `feat(wiki): deploy cutover data modules safely`.

### Task 7: Create production Cargo tables through the privileged procedure

- [ ] Create every designed production Cargo table only after tasks 1 through 6
  pass. Use declare-only templates and the privileged replacement-table procedure.
  Poll the queue, stop for the manual `Special:CargoTables` switch-in where required,
  record every privileged operation and checkpoint in the deployment manifest, then
  verify the active schemas and expected row counts. Do not add `lua=1` to an article
  in this task.
  - **Owning specs:** `2026-06-04-wiki-cargo-data-architecture`,
    `2026-07-30-wiki-cargo-schema-revision`, and
    `2026-07-30-wiki-deploy-sync-discipline` Gate 5.
  - **Affected paths:** `wiki/templates/`, `wiki-dev/cargo_check.py`, and
    `src/erenshor/application/wiki_deploy/`.
  - **Verification:** run `uv run erenshor wiki verify` and the production Cargo
    schema and row-count verification command defined by the deploy spec. Required
    result: no `__NEXT` table or queue operation remains pending, every active schema
    matches its declaration, row counts match the approved projections, and the
    article scan still reports zero `lua=1` uses.
  - **Commit:** `feat(wiki): create production Cargo foundation`.

### Task 8: Run all-seven local and TemplateSandbox canaries

- [ ] Run local and TemplateSandbox canaries for Item, Character, Spell, Skill,
  Stance, Quest, and Zone. Exercise both selector branches, invalid identity, key
  without flag, and ordered multi-entity Spell/Skill identity. Re-run every
  Cargo-backed relationship section after table creation so required verdicts move
  from `not_exercised` to `passed` with generated and community provenance distinct.
  - **Owning spec:** `2026-08-01-wiki-render-parity-gate`.
  - **Affected paths:** `wiki-dev/parity_check.py`,
    `wiki-dev/parity-allowlist.toml`, `wiki-dev/fixtures/`, and
    `src/erenshor/application/wiki_deploy/`.
  - **Verification:** run `uv run erenshor test wiki --clean-parity` and the guarded
    TemplateSandbox parity command defined by the parity spec. Required result: zero
    failed cases, zero required `not_exercised` cases, no parser warnings or error
    nodes, and exact ordered Spell/Skill identities.
  - **Commit:** `test(wiki): prove all entity cutover canaries`.

### Task 9: Publish the zero-conversion foundation report

- [ ] Produce a foundation-completion report from the deterministic manifests and
  parity outputs. Prove that every required parity case passes, every required Cargo
  table and generated module exists with 25 percent size headroom, drift is zero,
  rollback artifacts exist, privileged operations are recorded, and zero production
  articles were converted. Only an approved passing report permits
  `2026-07-11-wiki-article-cutover` to become active.
  - **Owning specs:** all four cutover authorities and this plan.
  - **Affected paths:** `wiki-dev/`,
    `src/erenshor/application/wiki_deploy/`, and `docs/plans/`.
  - **Verification:** run `uv run erenshor wiki verify`,
    `uv run erenshor test wiki --clean-parity`, `omp-plans index`, and
    `omp-plans check`. Required result: the report has zero failed and zero required
    `not_exercised` cases, all live SHAs match, all rollback sidecars exist, the
    article inventory contains zero `lua=1` uses, and plan validation exits zero.
  - **Commit:** `docs(wiki): certify Cargo cutover foundation`.

## Completion gate

The plan is complete only when task 9's report is approved. Completion proves shared
infrastructure readiness with zero converted production articles. The next operation
is activation of `2026-07-11-wiki-article-cutover` and its Stance canary. No task in
this plan performs that edit.
