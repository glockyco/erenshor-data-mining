# Cargo Storage Architecture — Research & Decisions (2026-06-07)

Triggered by a directive to validate the wiki Cargo architecture against real-world
best practice rather than inherited assumptions, before building the ability
(`Spell`/`Skill`/`Stance`) Cargo tables (Phase 2). This documents what the
authoritative sources actually say and the decisions that follow. **It reverses two
inherited design decisions** (a shared `Abilities` base table; storing Cargo by
hand-building `{{#cargo_store:...}}` wikitext) — see "Decisions" and "Spec impact".

## Sources

Platform (authoritative for our host — **the Erenshor wiki runs on wiki.gg**):
- wiki.gg — Cargo troubleshooting (Lua limits, per-template table caps, type rules):
  https://support.wiki.gg/wiki/Cargo/troubleshooting
- wiki.gg — Attaching tables (the "Cargo attach trick", recreate discovery):
  https://support.wiki.gg/wiki/Cargo/attaching_tables
- wiki.gg — Cargo overview / storing: https://support.wiki.gg/wiki/Cargo

Upstream extension docs:
- Cargo — Storing data (`#cargo_declare`/`#cargo_store`/`#cargo_attach`, "no more than
  one declare/attach per template"): https://www.mediawiki.org/wiki/Extension:Cargo/Storing_data
- Cargo — Other features (Lua `mw.ext.cargo.*`): https://www.mediawiki.org/wiki/Extension:Cargo/Other_features
- Cargo source `cargo.lua` (Lua wrappers are thin shims over PHP): https://github.com/wikimedia/mediawiki-extensions-Cargo/blob/master/cargo.lua

Large production game wikis (real-world patterns):
- River (Leaguepedia data lead) — Representing one-to-many relations (junction tables
  vs list fields; the attach trick): https://river.me/blog/one-to-many/
- River — Optimizing Cargo, query 1 (**Cargo has no `UNION`**; do it in Lua):
  https://river.me/blog/optimizing-cargo-1/
- PoE wiki — `Module:Cargo` (production Lua→Cargo store: `frame:callParserFunction`,
  multi-row loop, bool/list casting): https://www.poewiki.net/wiki/Module:Cargo
- Leaguepedia — `Module:CargoDeclare` (dedicated declare templates):
  https://lol.fandom.com/wiki/Module:CargoDeclare

## Findings

**F1 — A template may declare at most one table and attach at most one table.**
Hard limit, confirmed on our platform: *"Each template can only attach 1 table … a
template can only declare one table. A template CAN, however, both declare and attach —
for a maximum of 2 tables available without any workarounds."* (wiki.gg troubleshooting;
also Cargo Storing data, River one-to-many). `#cargo_declare` has a built-in attach, so
the declaring template is automatically a writer for its own table (wiki.gg attaching
tables). **Consequence:** a single template storing to 3 tables (the planned "Spell
declares Abilities + Spells + AbilityClasses") is impossible without the attach trick.

**F2 — Storing >1 row per page is normal: call `#cargo_store` once per row.** PoE's
`Module:Cargo` loops over data rows and calls the store function per row; River's
one-to-many template stores the parent row plus N child rows in one `<includeonly>`.
There is no "one row per page" restriction on `#cargo_store`.

**F3 — Native Lua store/declare are unavailable on wiki.gg; use the parser function via
`frame:callParserFunction`.** wiki.gg troubleshooting: *"cargo_store (disabled on
wiki.gg due to poor support), cargo_declare (disabled) … but you can still use
`frame:callParserFunction()`."* and lists "Native store and declare Lua functions" under
features unavailable on wiki.gg. PoE's production module does exactly this:
`mw.getCurrentFrame():callParserFunction('#cargo_store:', values)`. `mw.ext.cargo.store`
(suggested in our older design doc) would **fail on the target platform**.

**F4 — `frame:callParserFunction('#cargo_store:', valuesTable)` is the correct, robust
store call.** Passing a `{ _table=…, Field=value, … }` table hands each value to Cargo as
a discrete named argument — no manual escaping of `|`, `=`, newlines, or `{{`/`[[`, and
no re-parse. Contrast the current Erenshor approach (`Item.lua`/`Character.lua`): it
hand-concatenates `{{#cargo_store:|F=v}}` wikitext, escapes only `|`→`&#124;` and
newline→space, then `frame:preprocess`es the result. That misses `=`, `{{`, `[[`, and
re-parses values as wikitext — a latent injection/format bug, not just a style nit.

**F5 — Cargo has no `UNION`.** River had to implement union in Lua application logic
because *"Cargo doesn't support `UNION` at all."* So a single-table query is the only way
to scan multiple entity kinds "for free"; otherwise you run N queries and merge in Lua.

**F6 — One-to-many → a separate junction table, not list fields or numbered columns.**
River's entire one-to-many article. List fields can't associate companion data (e.g. a
class with its required level); numbered columns hit column limits and make queries
fragile. The junction holds one row per relationship and is queried directly (reverse) or
joined + `GROUP_CONCAT` (forward).

**F7 — wiki.gg type/format rules that constrain storage.** Integer columns must be real
integers (no decimal point, no `+`, no markup); Float columns must be plain numbers;
`unique` is broken; implicit store / omitting the table name is disabled (must name the
table and every field); for `format=template`, field names with underscores get mangled,
so **CamelCase field names** are preferred (we already use these). (wiki.gg troubleshooting.)

**F7a — wiki.gg's Cargo fork rejects SQL-keyword field names (verified empirically).**
Declaring a `Range` column makes table creation fail silently: `#cargo_declare`
renders `Error: "Range" cannot be used as a Cargo Field name, because it is an SQL
keyword`, the table is never created, and `cargorecreatetables` still returns
`success:true`, so `#cargo_store` to it is a no-op (the row vanishes with no error —
cf. F7 "Cargo has almost no error state logging"). The blocklist is selective (`End`
is accepted, as the `Items` table proves), so the only safe rule is to avoid SQL
keywords in column names. The spell/skill range column is therefore stored as
`CastRange`. (Found while debugging an empty `Spells` table on the local harness.)

## Decisions

**D1 — Drop the shared `Abilities` base table.** Use three independent per-type tables —
`Spells`, `Skills`, `Stances` — plus the `AbilityClasses` junction. Rationale:
- The base table's only unique benefit is a single-query "all abilities regardless of
  type" scan (F5: no `UNION`). That need is rare and fully served by per-type queries
  merged in Lua, and ability *name/link* resolution is already done from the Lua data
  modules (`Module:Erenshor/AbilityLink`), not Cargo.
- Keeping it forces every `Spell`/`Skill`/`Stance` page to write 3 tables, exceeding the
  declare-1/attach-1 cap (F1) and requiring the attach-trick sub-templates — pure
  complexity for marginal value, plus duplicated Name/Image across base and detail.
- Dropping it lands every storing template within the no-workaround 2-table budget.

**D2 — Per-template Cargo association (within F1, no attach trick):**
- `Template:Spell` — declares `Spells` (auto-attached) **+** attaches `AbilityClasses`.
- `Template:Skill` — declares `Skills` (auto-attached) **+** attaches `AbilityClasses`.
- `Template:Stance` — declares `Stances` only.
- `Template:AbilityClasses` — declare-only template for the junction (Leaguepedia's
  dedicated-declare convention, F1/attach docs); `Spell` and `Skill` attach it.

**D3 — Centralize storage in `Module:Erenshor/Cargo` using
`frame:callParserFunction('#cargo_store:', values)`** (F3/F4), casting booleans to
`yes`/`no` (Cargo Boolean accepts these) and dropping nil fields; one call per row, looped
for junction rows. **Refactor `Item.lua` and `Character.lua` onto this helper** so there
is a single store mechanism (removing the fragile hand-built-wikitext path) rather than
two parallel conventions.

**D4 — Cargo stores the queryable subset only; descriptions/long text stay Lua-only.**
Detail tables carry filter/sort/join columns + `Name`/`Image` for query-result display.
The infobox renders rich text from the data modules, so e.g. spell `Description` is not a
Cargo column.

**D5 — `AbilityClasses` junction = `(StableKey, Class, RequiredLevel)`**, one row per
(ability, class). Spells broadcast their single `requiredLevel` to each class; skills use
per-class `classLevels`; stances have no classes (F6). `Class` stores the canonical class
name to join consistently with item `Classes`.

## Spec impact

- Umbrella spec (`2026-06-04-wiki-cargo-data-architecture.md`) §5.2/§7/§8: remove the
  `Abilities` base table; abilities = `Spells`/`Skills`/`Stances` + `AbilityClasses`.
- Phase 2 plan (`2026-06-06-wiki-cargo-phase2-abilities.md`): supersede the "base +
  detail, Spell declares Abilities/Spells/AbilityClasses" model with D1–D5.
- The older `Module:Erenshor/Cargo` `mw.ext.cargo.store` sketch in
  `docs/wiki-lua-architecture-design.md` is wrong for wiki.gg (F3) and is replaced by D3.

## Verification plan

Multi-row storage (F2) and the no-base join model (D1/D5) are proven empirically on the
local harness during implementation: `Minor Lightning` (two classes) must yield two
`AbilityClasses` rows; the Phase 2d two-spell page must yield two `Spells` rows; and the
existing `Items`/`Characters` Cargo fixtures must stay green across the D3 refactor.
