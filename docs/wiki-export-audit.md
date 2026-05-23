# Wiki Export System Audit

**Date**: 2026-05-23  
**Scope**: `src/erenshor/application/wiki/`, `src/erenshor/infrastructure/wiki/`

---

## Executive Summary

The wiki export system works, but its complexity is wildly disproportionate to the problem it actually solves. The system's ~2700 lines of application code exist primarily to answer one question per page: *did a human edit this field, and if so, should we keep their value or overwrite it?* The answer for a solo-developer project is almost always "there are at most a dozen manually-edited fields across the entire wiki, and they could be maintained in a 30-line config file."

The fundamental problem is architectural: the system tries to be *clever* about preserving manual edits at the wikitext level — fetching existing pages, parsing MediaWiki templates, applying per-field merge rules, handling legacy template variants — when a much simpler alternative (a config-level override file, or HTML section markers) would achieve the same result with a fraction of the surface area.

---

## System Overview

Three CLI stages:

```
wiki fetch → wiki generate → wiki deploy
```

1. **fetch**: Downloads existing pages from MediaWiki API, caches to `variants/{variant}/wiki/fetched/`
2. **generate**: Re-generates pages from DB, merges with fetched content via preservation rules, writes to `variants/{variant}/wiki/generated/`
3. **deploy**: Uploads generated pages to MediaWiki

The core complexity lives in the generate stage, specifically in `generate_service.py` (746 lines), which applies 4–5 separate transformation passes to every existing page before saving it.

---

## Findings

### 1. The Merge System Is Solving a Non-Problem at Great Cost

**What the problem actually is**: When the bot regenerates a wiki page, it might overwrite a field a human manually edited — for example, a custom image caption or a manually-added quest source link.

**How the current system solves it**: Full fetch–parse–merge–deploy cycle. For each page that already exists on the wiki, the system:
1. Fetches the current wikitext
2. Parses it with `mwparserfromhell`
3. Applies `FieldPreservationHandler.merge_templates()` with per-template per-field rules
4. Runs `LegacyTemplateRemover` to handle old template names
5. Runs `_replace_fancy_tables()` for weapon/armor quality tiers (a second wikitext surgery)
6. Runs `_replace_item_type_templates()` for aura/spellscroll/skillbook/consumable/mold tooltips (a third surgery)
7. Runs `_replace_overview_table()` for the Weapons/Armor overview pages (a fourth surgery)
8. Runs `PageNormalizer` to clean up categories and whitespace

**How many "human-edited" fields actually exist across the entire wiki?** Based on `DEFAULT_PRESERVATION_RULES`, the fields that can ever be manually edited are:
- `image`, `imagecaption` on Items and Abilities
- `othersource` on Items
- `type` on Items (merge), `type` on Characters (prefer_manual)
- `questsource`, `relatedquest` on Items (merge)
- `imagecaption`, `level`, `type`, `image` on Zones

That is fewer than 15 field/template combinations across the entire game's content. The entire multi-stage merge pipeline exists to preserve these 15 combinations.

**A simpler alternative**: A 30-line TOML file of explicit field overrides (`page_title.field = value`) — maintained by the developer alongside the code — would achieve the same result without any wikitext parsing, without fetching, and without any merge logic. The bot would apply these overrides as a final pass after generation.

### 2. `generate_service.py` Has Too Many Code Paths

The method `_process_generated_pages` applies different transformations based on page title and content structure:

```
if page_title in ["Weapons", "Armor"]:
    → _replace_overview_table (string-find based splice)
    → PageNormalizer
else:
    → LegacyTemplateRemover (if legacy templates found)
    → FieldPreservationHandler.merge_templates (for Item/Character/Ability)
    → _replace_fancy_tables (for Item/Weapon, Item/Armor, Item/Charm)
    → _replace_item_type_templates (for Item/Aura, Item/SpellScroll, etc.)
    → PageNormalizer
```

There are also output_dir pages (zones) that bypass this entire pipeline. Five distinct code paths, each with its own assumptions about wikitext structure. Adding a new template type currently requires adding a new code path here — there is no general solution.

### 3. Two Independent Merge Systems Doing Related Work

`FieldPreservationHandler.merge_templates()` and `_replace_fancy_tables()` / `_replace_item_type_templates()` both operate on the same wikitext and both attempt to merge old and new content. They are solving the same problem (keep old where appropriate, use new elsewhere) via completely different mechanisms:

- `FieldPreservationHandler`: Works at the field level inside a template. Parses `{{Item|field=value|...}}` and applies per-field rules.
- `_replace_fancy_tables` / `_replace_item_type_templates`: Work at the template/table level. Finds the entire `{{Item/Weapon}}` block or `{| |- || {{Item/Weapon}} |}` table and replaces it wholesale.

These two systems need to be applied in the correct order, and each assumes the other has already done its job. When the template system changes (next template rename), both need to be updated in sync.

### 4. Brittle Wikitext Parsing — Silent Corruption Risks

Several methods use manual string manipulation on wikitext rather than a proper parser:

**`_replace_wiki_table` (generate_service.py ~l. 460–485)**:
```python
table_end = new_wikitext.find("|}", table_start) + 2
```
MediaWiki tables can be nested. A template inside a table cell that renders its own wikitable will have a `|}` inside the outer table. This `find` will stop at the *first* `|}` after `{|`, which may be the inner table's closing tag, not the outer one. Result: silently truncated table content. Example that breaks it:
```
{| class="wikitable"
|-
|| {{SomeTemplate|content=
{| another table
|}
}}
|}
```
The find for `|}` returns the position of the inner `|}`, not the outer one.

**`_extract_template_at_position` (generate_service.py ~l. 722–745)**:
```python
if wikitext[i : i + 2] == "{{":
    brace_count += 1
```
Triple-brace syntax `{{{parameter}}}` (used in wikitext for template parameters) contains `{{` at position 0, followed by another `{`. The counter will count it as opening `{{` + orphan `{`, and then `}}}` as `}}` + orphan `}`. In practice this works because the brace counts still balance (3 opens, 3 closes), but it means the function cannot distinguish between `{{template}}` and `{{{parameter}}}` at position boundaries, which can cause incorrect extraction when a template argument value itself starts with `{`.

**`_replace_overview_table` (generate_service.py ~l. 352–378)**:
```python
old_table_start = old_wikitext.find("{|")
intro_text = old_wikitext[:old_table_start].rstrip()
```
Assumes the first `{|` in the page is the overview table. If a human editor adds even a small wikitable to the intro section of the Weapons or Armor page, this will split the page at the wrong boundary, merging intro fragments with the generated table.

**`PageNormalizer._extract_categories`**:
```python
category_pattern = r"\[\[Category:[^\]]+\]\]"
```
This regex matches anywhere in the text, including inside `<nowiki>` blocks and HTML comments. A comment like `<!-- See [[Category:Weapons]] for more -->` would have its category extracted and moved to the bottom, removing the comment's content.

### 5. `metadata.json` Performance Problem

`WikiStorage._load_metadata()` and `_save_metadata()` are called on **every single page operation** — every fetch save, every generate save, every deploy update. Each call reads the entire `metadata.json` file, deserializes it, modifies it, reserializes it, and writes it back.

For a full generation run of ~2000 pages:
- 2000 calls to `_load_metadata()` → reads a file that grows from 0 to ~500KB over the run
- 2000 calls to `_save_metadata()` → writes the file 2000 times

Total I/O: approximately 500MB of read + 500MB of write for a single generation pass, all to track timestamps. This also has no file locking, so running two wiki operations concurrently (e.g., `generate` in one terminal while `fetch` completes in another) can corrupt `metadata.json`.

### 6. No Edit Conflict Detection

`MediaWikiClient.edit_page()` does not pass `basetimestamp` or `baserevid` to the MediaWiki API. This means there is no edit conflict detection: if a human edits a wiki page between the `fetch` step and the `deploy` step, the bot will silently overwrite the manual edit with no warning.

The MediaWiki API supports this via the `basetimestamp` parameter (set to the revision timestamp captured during fetch). The current code has the timestamp available in `PageMetadata.fetched_at` but does not use it.

### 7. Rate Limiting Is Inconsistent

The rate limit appears in two places with different values:
- `MediaWikiClient.__init__`: `rate_limit_delay: float = 1.0` (default)
- `WikiDeployService.deploy_all` and `deploy_from_dir`: `time.sleep(2.0)` hardcoded after every edit

The service-level hardcoded sleep overrides the client-level configurable delay. If the client's delay is changed to 0.5 (e.g., for a faster network), the deploy service's 2-second sleep still applies. The actual upload rate is the *sum* of both delays, not the configured rate.

### 8. `LegacyTemplateRemover` Is a Museum of Template Renames

The class maps 8 old template names to current ones. Its presence reveals the system has been through at least 3 major template renames:
- `{{Enemy}}` / `{{Pet}}` → `{{Character}}`
- `{{Consumable}}` / `{{Weapon}}` / `{{Armor}}` / `{{Auras}}` / `{{Mold}}` / `{{Ability Books}}` → `{{Item}}`
- `{{Fancy-weapon}}` / `{{Fancy-armor}}` / `{{Fancy-charm}}` → `{{Item/Weapon}}` / `{{Item/Armor}}` / `{{Item/Charm}}` (handled separately in `generate_service.py`)

Each rename added code — the remapper, the separate `_replace_fancy_tables` path, hardcoded template name lists in `_replace_item_type_templates`. The next template rename will add more code. There is no mechanism to ever remove this code, because pages on the live wiki might still have the old templates (requires knowing whether all pages have been through the pipeline since the rename).

`PageNormalizer.LEGACY_CATEGORIES` has the same pattern: 17 hardcoded old category names accumulated over time.

### 9. Jinja2 Environment Instantiated Per Template Render

In `PageGenerator._render_template()` (base.py):
```python
def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
    from jinja2 import Environment, FileSystemLoader
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), ...)
    return str(env.get_template(template_name).render(**context))
```

A new `Environment` and `FileSystemLoader` is created for every single template render. With ~2000 pages × ~2 renders per page, this instantiates ~4000 Jinja2 environments. The `FileSystemLoader` scans the template directory on each creation. This is solved by making the environment a class-level singleton.

### 10. `FetchService` Has Excess Repository Dependencies

`WikiFetchService.__init__` takes all 13 repository dependencies (items, characters, spells, skills, stances, factions, spawn_points, loot_tables, quests, zones, class_display) — the same list as `WikiGenerateService`. The fetch service's only use of these repositories is in `_build_page_title_index()`, which iterates entities to build a `page_title → [stable_keys]` map for saving to metadata.

This coupling means adding a new entity type requires updating both the generate service and the fetch service's constructor signature. The page title index is also only needed to populate `stable_keys` in `PageMetadata`, which is tracking metadata that `should_deploy()` doesn't even use.

### 11. `Jinja2 autoescape=False` Is Correct but Risky

`autoescape=False` is the right choice for wikitext output. However, if any template variable contains `{{`, `}}`, `{%`, or `%}` (as game content legitimately might), it will be misinterpreted as Jinja2 markup and cause a `TemplateSyntaxError` or silent mis-render. For example, a game item whose lore text contains `{{...}}` would break template rendering. The templates themselves use `{{ "{{" }}` to escape literal double braces, but template *variables* are not escaped. This has probably never triggered because game data doesn't contain those characters — but it's an untested assumption.

### 12. Timezone-Naive Timestamp Comparisons

`PageMetadata.should_deploy()` compares ISO timestamp strings:
```python
if self.deployed_at is not None and self.generated_at <= self.deployed_at:
    return False, "not regenerated since deployment"
```

`datetime.now().isoformat()` produces a local-time string without timezone offset. The wiki's `fetched_at` timestamps come from `datetime.now().isoformat()` too, so they are all in local time — consistent within one machine. But if the developer runs the pipeline on a different machine, or if DST flips between fetch and generate, the comparison can flip incorrectly and either skip deploying changed pages or re-deploy unchanged ones.

---

## What Mature Systems Do (Research Findings)

### Section-Based Bot Content

The best-practice pattern for automated + manual wiki content is physical separation via HTML comment markers:

```
<!-- BOT-GENERATED-START -->
{{Item|...auto-generated...}}
<!-- BOT-GENERATED-END -->

== Notes ==
Human-written content here, never touched by the bot.
```

The bot only replaces content between its markers on each deploy. No fetch step needed, no merge needed, no field-preservation system needed. This is used by bots on Wikipedia and Wikimedia projects.

For this project, the "bot section" would be the infobox template. Manual content (images, notes, lore) lives outside the markers. The current field-preservation system would collapse to ~20 lines.

### Structured Data (Cargo / SMW)

Large game wikis (RuneScape wiki, Minecraft wiki, Path of Exile wiki) have moved to the Cargo extension. Game data lives in dedicated data pages queried via `#cargo_query:` syntax. Display pages consume the data dynamically via templates. The bot updates data pages; human editors work on display pages. The bot never overwrites human content because their content lives in different pages.

This is a larger architectural investment, but it eliminates the merge problem entirely and enables wiki-side querying (sorting items by damage, filtering characters by zone, etc.) that the current system cannot provide.

### Edit Conflict Detection

The MediaWiki API's `action=edit` accepts `basetimestamp` (the timestamp of the revision the bot read when it fetched the page). If the page has been edited since then, the API returns `editconflict` instead of silently overwriting. Every production MediaWiki bot should use this.

### Bot Account Best Practices

- Use `baserevid` or `basetimestamp` on every edit to detect conflicts
- Include bot code version and data source version in the edit summary
- Respect `{{nobots}}` templates (not relevant for a private wiki, but worth noting)
- Log all edits with timestamps to a local file for audit

---

## Prioritized Recommendations

### High Priority (safety and correctness)

1. **Add `basetimestamp` to `edit_page`**. Store the fetched revision timestamp in `PageMetadata` and pass it to the API call. This prevents silent overwrites of concurrent edits and takes ~10 lines.

2. **Replace string-find wikitext surgery with proper parser calls throughout**. `_replace_wiki_table`, `_replace_overview_table`, and `_replace_fancy_charm_template` should use `mwparserfromhell` node traversal consistently, not `str.find("{|")` / `str.find("|}".

3. **Fix `metadata.json` O(N²) pattern**. Load metadata once per command invocation (in the service constructor or a lazy cache on first access), not once per page save.

### Medium Priority (architecture simplification)

4. **Replace the fetch→merge cycle with an override config file**. Introduce `wiki/overrides.toml` mapping `page_title.field = value`. During generation, apply these overrides as a final pass after Jinja2 rendering. This eliminates `FieldPreservationHandler` (~600 lines), removes the need to fetch pages before generating, and makes manual overrides explicit and version-controlled rather than implicit and scattered across the live wiki.

5. **Consolidate `_replace_fancy_tables`, `_replace_item_type_templates`, and `FieldPreservationHandler.merge_templates` into a single templated merge pass**. All three are doing the same thing (merge old node → new node) via different mechanisms. A unified approach would be: parse both old and new wikitext, for each top-level template node in new content, either replace the corresponding node in old content (if present) or insert it (if new). The field-level preservation rules apply during this pass.

6. **Make `LegacyTemplateRemover` a migration artifact, not permanent infrastructure**. Run it once against the live wiki via a one-off script to migrate all remaining old-format pages, then delete the class. Track migration completion per page in metadata.

7. **Eliminate `FetchService`'s repository dependencies**. The page title list should come from the generator registry (generators know their pages), not from loading all entities again. Pass the generator list to the fetch service instead of all 13 repositories.

### Low Priority (cleanup)

8. **Cache the Jinja2 Environment as a class-level singleton** in `SectionGeneratorBase`. One environment per process, not one per render call.

9. **Unify rate limiting**: Remove the `time.sleep(2.0)` from `WikiDeployService` and rely solely on `MediaWikiClient.rate_limit_delay`. Make the delay configurable via the wiki config section.

10. **Move `LEGACY_CATEGORIES` in `PageNormalizer` out of the class** into a one-off migration script. Once all old-format pages have been regenerated, this list serves no purpose and is dead code.

11. **Use timezone-aware timestamps** (`datetime.now(UTC).isoformat()`) for all `metadata.json` timestamps.

---

## Unknown Unknowns (Untested Failure Modes)

These failure modes have almost certainly never been hit, because the game data happens to avoid the edge cases. But they are latent bugs:

- **Nested wikitables corrupting `_replace_wiki_table`**: Any `|}` inside a template in a table cell will cause premature table extraction.
- **`{{{parameter}}}` syntax in wikitext**: Triple-brace template parameters in human-written content will confuse `_extract_template_at_position`'s brace counter.
- **Jinja2 meta-characters in game data**: An item lore string containing `{{`, `}}`, or `{%` would cause a Jinja2 render error or silent mis-render.
- **Category in `<nowiki>` or comment**: The category regex extracts categories from anywhere in the page, including commented-out or escaped content.
- **`merge_handler` comma detection**: The `{{!}}` heuristic for QuestLink comma avoidance is not exhaustive. Any other template with commas in its arguments would be incorrectly split.
- **Concurrent `generate` + `fetch` run**: No file locking on `metadata.json` write.
- **Unicode edge cases from Unity export**: The pipeline assumes all game strings are clean UTF-8. A single malformed character in a game asset would raise `UnicodeEncodeError` when writing the page file.

---

## Code Metrics

| File | Lines | Primary responsibility |
|---|---|---|
| `generate_service.py` | 746 | Page merge orchestration — too broad |
| `field_preservation.py` | 595 | Per-field merge rules |
| `client.py` | 827 | MediaWiki HTTP API |
| `storage.py` | 449 | File + metadata I/O |
| `fetch_service.py` | 333 | Fetch orchestration |
| `deploy_service.py` | 321 | Deploy orchestration |
| `legacy_template_remover.py` | 276 | Historical cruft |
| `template_parser.py` | ~404 | mwparserfromhell wrapper |
| **Total** | **~3950** | |

For comparison: the actual content being generated is 14 Jinja2 templates averaging ~500 bytes each. The infrastructure to merge those templates back into existing pages is ~10× larger than the templates themselves.
