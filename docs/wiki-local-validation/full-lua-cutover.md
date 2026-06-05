# Local Lua/Cargo Cutover Validation

Date: 2026-06-04

## Scope

Validated the local MediaWiki harness for the Lua-data-driven, Cargo-backed wiki cutover. This covers repo-owned interface pages, modules, generated data modules, public templates, Cargo declarations/stores, and representative fixture articles.

## Commands and results

```bash
uv run python wiki-dev/import_pages.py
```

Result: imported repo-owned interface pages, `Module:Erenshor/*`, `Module:Erenshor/Data/*`, templates, `MediaWiki:Gadget-erenshor.css`, and fixture articles into the local wiki.

```bash
uv run python wiki-dev/cargo_check.py --recreate
uv run python wiki-dev/null_edit.py
uv run python wiki-dev/cargo_check.py
```

Result: recreated local Cargo table definitions for `Items` and `Characters`, null-edited fixture pages to repopulate Cargo rows, then observed `PASS Cargo local validation`.

```bash
uv run python wiki-dev/smoke_test.py
```

Result: every rendered fixture page, Lua testcase smoke page, Cargo overview page, and Cargo row check reported `PASS`.

```bash
uv run pytest tests/unit/test_wiki_dev_harness.py -q
uv run ruff check wiki-dev tests/unit/test_wiki_dev_harness.py
```

Result: `25 passed`; Ruff reported `All checks passed!`.

## Coverage

Lua testcase smoke pages execute all current testcase modules:

- `Module:Erenshor/AbilityLink/testcases`
- `Module:Erenshor/Args/testcases`
- `Module:Erenshor/Character/testcases`
- `Module:Erenshor/Format/testcases`
- `Module:Erenshor/Link/testcases`
- `Module:Erenshor/Item/testcases`
- `Module:Erenshor/Quest/testcases`
- `Module:Erenshor/Skill/testcases`
- `Module:Erenshor/Spell/testcases`
- `Module:Erenshor/Stance/testcases`
- `Module:Erenshor/Zone/testcases`

Rendered fixture coverage includes item subtypes, character types, quests, zones, stances, spells, skills, semantic link wrappers, ability links, manual overrides, missing-data tracking pages, and Cargo-backed armor/weapon overview pages.

Cargo validation covers the local `Items` and `Characters` tables, including expected rows for generated pages, manual override pages, semantic class/faction/zone display fields, and absence checks for pages that must not store item rows.

Parser-health checks fail smoke validation on Lua errors, script errors, parser errors, unresolved template links, parser-limit failures, escaped PortableInfobox/table shells, unexpected missing-data tracking categories, and raw semantic link template calls returned from Lua output (`{{ItemLink|...}}`, `{{AbilityLink|...}}`, `{{QuestLink|...}}`, `{{CharacterLink|...}}`, `{{ZoneLink|...}}`, `{{FactionLink|...}}`, or `{{ClassLink|...}}`).

## Local-vs-live notes

The local harness uses Cargo as the installed compatibility layer. Production wiki.gg uses LIBRARIAN/Cargo-compatible query surfaces, so local Cargo row validation is a pre-cutover compatibility gate rather than a byte-for-byte production database clone.

Cargo table recreation resets table definitions locally but does not synchronously repopulate rows in this stack. The validated workflow is to recreate tables, null-edit fixture articles, then validate rows. The null-edit helper purges all fixture pages only after the full fixture set has refreshed so Cargo query pages reparse against the final table state.
