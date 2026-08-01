---
title: Wiki Render Parity Gate
type: spec
status: draft
created: 2026-08-01
parent: 2026-07-09-erenshor-planning-overview
---

# Wiki Render Parity Gate

Define the deterministic evidence required to prove that the legacy and generated
Lua/Cargo paths preserve the approved wiki presentation and content contract before
an article crosses to exact `lua=1`.

## Scope and execution surfaces

Compare the same entity through the verbatim legacy branch and the exact `lua=1`
branch without changing production state:

1. Local fixtures exercise both branches first.
2. TemplateSandbox parses candidate template and module text against live canary
   titles next.
3. A guarded live canary is allowed only after its generated data module and every
   Cargo table it reads or stores exist and have passed deployment verification.

The local instrument lives in `wiki-dev/` and produces the same report shape for
local, TemplateSandbox, and guarded live comparisons. The executable order is owned
by `2026-08-01-wiki-cargo-cutover-foundation`. Deployment preflight, drift,
protection, guarded-write, and rollback behavior remain owned by
`2026-07-30-wiki-deploy-sync-discipline`.

## Comparison identity

Each entity comparison is identified by the tuple
`(page_title, entity_type, stable_key)`. A page containing multiple entities is an
ordered set of those entity identities. It is never represented or compared as one
page-level content blob.

The required corpus includes a page containing one Spell stanza and one Skill
stanza. The report preserves their source order and proves that each resolves and
stores under its own `(entity_type, stable_key)` identity.

Duplicate identities and duplicate stable keys within the same entity type are
errors. A missing or extra entity instance is a failed comparison.

## Extracted contract

For each entity instance, extract and compare these named surfaces:

- infobox fields by stable field name
- link target and rendered label as separate values
- icon and image identity
- presence or absence of every optional field
- category membership
- relationship-section rows
- parser warnings and parser errors
- declared presentation-contract nodes

A presentation-contract node is a named structural element whose presence, order,
role, class, or parent-child relationship is part of the approved display contract.
The fixture declaration names each node and the properties that matter. Unnamed DOM
structure is not compared. Whole-page byte equality and unrestricted HTML equality
are forbidden because parser wrappers, attribute order, and unrelated page chrome are
not semantic parity.

## Normalization

Normalization is surface-specific and deterministic:

- Strip outer whitespace and normalize non-breaking spaces.
- Collapse internal whitespace only for values declared as plain text.
- Compare numeric values after the documented unit or percentage conversion for that
  field. The report retains both source values and the normalized value.
- Preserve link targets and labels as separate values. Never normalize one into the
  other.
- Preserve icon and image title identity after canonical MediaWiki filename
  normalization.
- Sort relationship rows by their declared stable semantic tuple only when the
  section is declared unordered.
- Never sort ordered stages, dialogue or progression rows, or the entity order on a
  multi-stanza page.
- Compare category membership as a set while retaining unexpected and missing
  categories separately in the diff.

Every field and relationship section must declare its normalization rule. An unknown
rule fails closed rather than falling back to string comparison.

## Cargo-backed sections

Before a required production Cargo table exists, its relationship comparison receives
verdict `not_exercised`. It can never receive `passed` from an empty result or from a
local substitute.

After table creation, compare normalized relationship row sets and require generated
and community provenance to remain distinct. A generated row cannot satisfy an
expected community row, and a community row cannot mask a missing generated row.
Production readiness requires every required Cargo-backed section to move from
`not_exercised` to `passed`.

## Failure rules

A comparison fails on any of these conditions:

- missing or extra entity instances
- missing or extra fields
- unequal normalized values
- an unexpected parser warning
- `Script error` or another parser error node
- duplicate entity identities or stable keys
- an unapproved relationship difference
- an unapproved structural difference in a declared presentation-contract node
- an allowlist entry that no longer matches either expected side
- a required comparison surface with no declared normalization rule

The gate never converts a failure into `not_exercised`. That verdict is reserved for
a declared Cargo-backed surface whose production table does not yet exist.

## Approved-difference allowlist

Approved differences live in checked-in `wiki-dev/parity-allowlist.toml`. Every entry
must name all of these fields:

- entity type
- stable key or exact fixture selector
- field or section
- comparison surface
- expected legacy value
- expected Lua value
- reason

Wildcards, broad selectors, omitted expected values, and rules such as `ignore HTML`
are forbidden. An entry matches exactly one declared difference. A report fails when
an observed difference lacks an entry, when an entry's legacy or Lua value differs,
or when an entry is unused because the expected difference disappeared. Removing an
obsolete allowance is part of accepting the new contract.

## Required corpus and selector matrix

The corpus covers Item, Character, Spell, Skill, Stance, Quest, and Zone. Every type
must exercise both selector branches. Across the corpus, and per type where the
fixture shape permits, it must prove the full selector contract:

| Case | Expected result |
|---|---|
| no `lua=1` and no key | verbatim legacy rendering, no Cargo store |
| exact `lua=1` and valid key | generated Lua rendering and expected Cargo rows |
| exact `lua=1` and invalid key | existing missing-data diagnostic, no Cargo row, no legacy fallback |
| valid key without `lua=1` | verbatim legacy rendering, no Cargo store |

At minimum, the full suite includes all seven entity types, both branches for each
type, one invalid stable key under exact `lua=1`, stablekey-without-flag legacy
behavior, and one ordered multi-entity page containing both a Spell and a Skill.
Quest participates in template parity but remains excluded from production article
conversion until `2026-07-31-wiki-quest-article-strategy` is approved.

## Outputs

Every run emits:

1. A deterministic JSON report with stable key ordering, explicit source metadata,
   extracted values, normalization rules, matched allowlist entries, and per-case
   verdicts.
2. A human-readable diff grouped by page, entity identity, field or section, and
   comparison surface.

The JSON verdict vocabulary is exactly `passed`, `failed`, and `not_exercised`.
Repeated runs over the same inputs must produce byte-identical JSON. Timestamps and
other run-specific values belong outside the deterministic report or are omitted.
Production readiness requires zero `failed` cases and zero required
`not_exercised` cases.

## Acceptance criteria

- Local fixtures compare the legacy and exact `lua=1` branches for all seven entity
  types without mutating production.
- TemplateSandbox parses candidate template and module text against live canary
  titles before any guarded live canary.
- The report keys each entity by `(page_title, entity_type, stable_key)` and preserves
  ordered multi-entity stanza order.
- Named fields, link targets and labels, image identity, optional-field presence,
  categories, relationships, parser diagnostics, and declared presentation nodes are
  extracted and normalized under the rules above.
- Missing production Cargo tables yield `not_exercised`, never `passed`. After table
  creation, required relationship cases pass with generated and community provenance
  distinct.
- `wiki-dev/parity-allowlist.toml` accepts only exact, bidirectionally checked
  differences with no wildcard or broad HTML ignore.
- The deterministic JSON report and human-readable diff expose every failed and
  `not_exercised` surface.
- A regression fixture intentionally drops one visible field from a Lua renderer.
  The gate must fail that fixture, proving it detects a defect that the current
  CSS-property and DOM-presence check misses.
- Production readiness is impossible with any failed case or any required
  `not_exercised` case.
