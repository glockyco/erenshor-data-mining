# Open Questions for User

**Document Status**: Requires User Input
**Date**: 2025-10-16
**Purpose**: Compile all remaining questions that need user decisions before implementation

---

## Priority 1: Blockers (Must Decide Before Implementation)

These questions must be answered before starting implementation, as they affect core architecture.

### Q1.1: Manual Content Preservation - Template List

**Context**: We need to know which templates are auto-generated to implement merge logic.

**Question**: Which MediaWiki templates do we currently auto-generate? Please provide complete list per entity type.

**Example**:
```
Items:
  - {{Item Infobox}}
  - {{Loot Table}} (if item is dropped by mobs)
  - ???

Characters:
  - {{Character Infobox}}
  - {{Spawn Locations}}
  - {{Abilities}}
  - ???

Spells:
  - {{Spell Infobox}}
  - {{Spell Ranks}}
  - ???
```

**Why It Matters**: Determines merge logic implementation.

---

### Q1.2: Manual Content Preservation - Section vs Template

**Context**: Need to understand if updates are only in templates or also in plain sections.

**Question**: Are there any sections (not templates) that we auto-generate and need to update?

**Example**: Do we generate plain text sections like:
```mediawiki
== Description ==
This is an auto-generated description...

== Loot ==
* Item 1 (25%)
* Item 2 (10%)
```

Or is everything always in templates like `{{Character Infobox}}`?

**Why It Matters**: Affects parsing strategy (template-only vs. section-based).

---

### Q1.3: Stable Entity IDs - Database Backups

**Context**: Cannot design entity identification system without analyzing what's stable.

**Question**: Can you provide 2-3 database backups from different game versions?

**Required**:
- One "old" version (e.g., from 3-6 months ago)
- One "recent" version (e.g., from last month)
- One "current" version (latest)

**Format**: SQLite files (e.g., `erenshor-main-v1.0.5.0.sqlite`)

**Why It Matters**: Need to analyze what entity properties remain stable across versions to design reliable identification system.

**User Action**: Please provide paths to backup database files or upload them somewhere.

---

### Q1.4: Name Conflicts - Resolution Strategies

**Context**: Need to define how to resolve name conflicts.

**Question**: What conflict resolution strategies should be available?

**Options**:
1. Suffix disambiguation: `"Sword (item)"`, `"Sword (spell)"`
2. Prefix disambiguation: `"Item: Sword"`, `"Spell: Sword"`
3. Manual mapping: Specify custom title in config
4. Skip: Don't create wiki page for conflicting entity
5. Multi-entity page: Merge multiple entities on one page

**Which should we support?**

**Follow-up**: Should any strategies be prioritized/recommended over others?

**Why It Matters**: Affects conflict resolution UI and configuration schema.

---

### Q1.5: Change Detection - Actionable Level

**Context**: Need to balance useful information vs. noise in change reports.

**Question**: What level of detail is helpful in change reports?

**Too much**: "Modified 45 files, added 234 lines, changed 156 variables..."
**Too little**: "Stuff changed, go look"
**Just right**: ???

**Examples to consider**:
- Should we report every stat change? (e.g., "Goblin health: 100 → 120")
- Should we report new items that just have different names but same stats?
- Should we report script changes that don't affect data export?

**Why It Matters**: Determines what we detect and how we present it.

---

### Q1.6: Resume from Failure - State Timeout

**Context**: Pipeline state becomes stale if left too long.

**Question**: What is acceptable timeout for pipeline state?

**Options**:
1. 24 hours (state cleared if older)
2. 48 hours
3. 1 week
4. Never expire (keep until manually cleared)

**Why It Matters**: Prevents confusion from resuming very old failures.

---

## Priority 2: Important (Should Decide Early)

These affect implementation details but can be decided during development if needed.

### Q2.1: Conflict Detection - Scanning Frequency

**Context**: Conflict detection can run at different times.

**Question**: Should we scan for conflicts on every command, or only specific ones?

**Options**:
1. Only on `extract` and `wiki fetch` (when data changes)
2. On any wiki-related command
3. On demand only (manual `erenshor wiki conflicts` command)
4. Automatic in background (periodic check)

**Trade-off**: More frequent = more overhead, but catch conflicts sooner.

**Why It Matters**: Affects performance and user experience.

---

### Q2.2: Conflict Detection - Auto-Resolution

**Context**: Some conflicts are unambiguous.

**Question**: Should we auto-resolve simple conflicts?

**Example**: If new item "Magic Sword" has no conflicts with any existing pages, auto-create page without prompting.

**Counter-example**: If new item "Sword" conflicts with existing manual page, require user resolution.

**Why It Matters**: Reduces manual intervention for obvious cases.

---

### Q2.3: Resume from Failure - Default Behavior

**Context**: Resume can be automatic or explicit.

**Question**: Should resume be default behavior or require explicit flag?

**Option A**: Auto-resume if state exists
```bash
erenshor update  # Automatically resumes if previous run failed
```

**Option B**: Require explicit flag
```bash
erenshor update           # Always start fresh
erenshor update --resume  # Explicitly resume from failure
```

**Trade-off**: Auto is convenient but might surprise users; explicit is clear but requires more typing.

**Why It Matters**: Affects user experience and CLI design.

---

### Q2.4: Resume from Failure - Stage Granularity

**Context**: Resume can work at different levels.

**Question**: Should we support resuming individual output stages (wiki/sheets/maps) or only full pipeline?

**Option A**: Full pipeline only
```bash
erenshor update --resume  # Resumes entire pipeline
```

**Option B**: Individual stages
```bash
erenshor wiki update --resume   # Resume just wiki portion
erenshor sheets deploy --resume # Resume just sheets portion
```

**Why It Matters**: Affects state tracking complexity.

---

### Q2.5: Change Detection - Auto-Generate Listener Code

**Context**: When new fields detected, we could try to generate boilerplate.

**Question**: Should we attempt to auto-generate listener code for new fields/types?

**Example**: Detect `Items.craftingTime` field added, generate:
```csharp
// Suggested addition to ItemListener.cs
if (item.craftingTime > 0) {
    record.CraftingTime = item.craftingTime;
}
```

**Pro**: Saves boilerplate typing
**Con**: Might generate incorrect code, need to review anyway

**Why It Matters**: Determines scope of change detection system.

---

### Q2.6: Maps Performance - Acceptable Load Time

**Context**: Need to optimize maps load time.

**Question**: What is acceptable load time for maps initial load?

**Options**:
- < 1 second (very fast)
- < 3 seconds (fast)
- < 5 seconds (acceptable)
- < 10 seconds (slow but usable)

**Current estimate**: ~5 seconds first load, ~100ms subsequent (with caching).

**Why It Matters**: Determines if further optimization needed.

---

### Q2.7: Maps Performance - Offline Support Priority

**Context**: Service workers enable offline support.

**Question**: Should we prioritize offline support (service worker)?

**Use case**: View maps without internet after first visit.

**Effort**: Medium (2-4 hours for service worker implementation)

**Why It Matters**: Affects maps implementation priorities.

---

### Q2.8: CLI Docs - Additional Information

**Context**: Auto-generating CLI documentation.

**Question**: What additional information should CLI docs include beyond command/param descriptions?

**Options**:
- Examples of usage
- Related commands (e.g., "See also: erenshor wiki push")
- Common workflows (e.g., "Typical workflow: extract → wiki update → wiki push")
- Troubleshooting tips
- Links to detailed documentation

**Why It Matters**: Determines doc template design.

---

### Q2.9: CLI Docs - Output Formats

**Context**: Can generate docs in multiple formats.

**Question**: Should we generate both HTML and Markdown, or only HTML?

**HTML**: Browser-viewable, rich formatting, searchable
**Markdown**: GitHub-friendly, can be in repo, simpler

**Why It Matters**: Affects doc generation command and templates.

---

### Q2.10: CLI Docs - Styling Preference

**Context**: HTML docs can have different visual styles.

**Question**: Preferred styling for CLI docs?

**Options**:
- Minimal/clean (like man pages)
- Modern/colorful (like modern documentation sites)
- GitHub-like (familiar to developers)
- Custom (specify preferences)

**Why It Matters**: Affects CSS and HTML template design.

---

### Q2.11: Docker - Setup Frequency

**Context**: Determining if Docker is worth the effort.

**Question**: How often do you set up the project on new systems?

**Options**:
- Once a year or less
- A few times a year
- Monthly
- Weekly

**Why It Matters**: If infrequent, Docker overhead not justified.

---

### Q2.12: Docker - Primary Setup Pain Point

**Context**: Docker should solve the biggest pain points.

**Question**: What is the primary pain point in setting up the project?

**Options**:
- Unity installation (large, complex)
- Python dependencies (version conflicts, etc.)
- Configuration (paths, credentials, etc.)
- AssetRipper / SteamCMD installation
- Other (specify)

**Why It Matters**: Focus on solving the actual pain points.

---

### Q2.13: Docker - Dev Container Interest

**Context**: VS Code dev containers are lighter weight than full Docker.

**Question**: Would VS Code dev container help your workflow?

**Use case**: Consistent Python/tooling environment without Dockerizing Unity.

**Effort**: Low (1-2 hours)

**Why It Matters**: Determines if we should create .devcontainer config.

---

### Q2.14: Test Database - Git Tracking

**Context**: Test database is ~20 MB.

**Question**: Should we commit test database to git or gitignore it?

**Option A**: Commit to git
- Pro: Easy for anyone to run tests
- Con: 20 MB in repo (not huge but noticeable)

**Option B**: Gitignore
- Pro: Smaller repo
- Con: Need to generate test DB before running tests

**Why It Matters**: Affects .gitignore and test setup instructions.

---

### Q2.15: Test Database - Update Frequency

**Context**: Test database needs to stay in sync with production.

**Question**: How often should we update test database?

**Options**:
1. Manually on demand (when tests start failing)
2. Weekly (automated reminder)
3. Monthly
4. After every game update
5. Never (use same test DB forever)

**Why It Matters**: Determines automation and update workflow.

---

### Q2.16: Test Database - Edge Case Collection

**Context**: Building library of problematic cases.

**Question**: Are there specific known edge cases we should add to minimal test database?

**Examples**:
- Items with unusual characters in names
- Characters with extremely high stats
- Spells with no mana cost
- Multi-entity pages with 10+ entities

**Why It Matters**: Helps create focused regression tests.

---

## Priority 3: Nice to Know (Can Defer)

These can be decided later during implementation or deferred to future work.

### Q3.1: Wiki Manual Fixes - Frequency

**Context**: Understanding how often manual wiki fixes happen.

**Question**: How often do you manually fix bugs in wiki pages (as opposed to fixing the generator)?

**Why It Matters**: Determines priority of manual override support.

---

### Q3.2: Image Upload - Current Pain Points

**Context**: Image upload needs automation.

**Question**: What are the current pain points with image uploads?

**Examples**:
- Finding which images need upload
- Detecting changed images
- Bulk uploading
- Naming/organizing images

**Why It Matters**: Focus automation on biggest pain points.

---

### Q3.3: Image Upload - Automation Strategy

**Context**: Image upload can be fully or semi-automated.

**Question**: Should image uploads be fully automatic or semi-automatic?

**Fully automatic**: Upload all images after extraction (might upload unwanted images)
**Semi-automatic**: Detect new/changed, show preview, let user approve batch

**Why It Matters**: Determines upload workflow design.

---

### Q3.4: Logging - Verbosity Levels

**Context**: Configuring logging detail.

**Question**: What logging verbosity do you typically want?

**Options**:
- DEBUG: Everything (very noisy)
- INFO: Important operations (default)
- WARNING: Only warnings and errors
- ERROR: Only errors

**Why It Matters**: Sets default log level.

---

### Q3.5: Logging - Quick Access Commands

**Context**: Designing log access commands.

**Question**: What should `erenshor logs show` display?

**Options**:
- Last 50 lines
- Last 5 minutes
- Full log
- Just errors
- Configurable

**Why It Matters**: Determines log viewer implementation.

---

### Q3.6: Backup Info - Metadata Display

**Context**: Showing backup information to user.

**Question**: What backup metadata would be useful to display?

**Examples**:
- Number of backups
- Total disk space used
- Oldest/newest backup
- Backup for each variant
- Backup sizes

**Why It Matters**: Determines `erenshor backup info` output.

---

### Q3.7: Change Detection - Script Diff Granularity

**Context**: Detecting C# script changes.

**Question**: How detailed should script change detection be?

**Options**:
1. File-level: "CraftingSystem.cs modified"
2. Method-level: "Added method: CanCraft()"
3. Field-level: "Added field: float craftingTime"
4. Line-level: "Added 45 lines, modified 12"

**Trade-off**: More detail = more useful, but also more complex to parse.

**Why It Matters**: Determines C# parsing complexity.

---

### Q3.8: Progress Reporting - Time Estimates

**Context**: Showing estimated time remaining.

**Question**: Should progress bars show ETA (estimated time remaining)?

**Example**: "Uploading pages... 25/100 (ETA: 2m 30s)"

**Pro**: Useful for long operations
**Con**: Estimates can be inaccurate, might annoy users

**Why It Matters**: Determines progress display implementation.

---

### Q3.9: Dry-Run - Preview Detail Level

**Context**: Dry-run mode shows what would happen.

**Question**: How much detail should dry-run output show?

**Options**:
- Summary: "Would update 25 pages"
- List: "Would update: Page 1, Page 2, ..."
- Full: "Would update Page 1: [shows full diff]"
- Configurable: `--dry-run=summary|list|full`

**Why It Matters**: Determines dry-run output format.

---

### Q3.10: Interactive Mode - Confirmation Prompts

**Context**: Dangerous operations can have confirmation prompts.

**Question**: Which operations should require confirmation prompts?

**Examples**:
- Wiki push (upload pages)
- Sheets deploy (overwrite data)
- Backup cleanup (delete files)
- Config reset (restore defaults)

**Why It Matters**: Balance safety vs. convenience.

---

### Q3.11: Validation Commands - Naming Consistency

**Context**: Health check commands might have inconsistent names.

**Question**: Should validation commands all use "doctor" naming?

**Current proposal**:
- `erenshor doctor` (general health)
- `erenshor wiki validate` (wiki-specific)

**Alternative**:
- `erenshor doctor` (general health)
- `erenshor doctor wiki` (wiki-specific)
- `erenshor doctor sheets` (sheets-specific)

**Pros**: More consistent, discoverable
**Cons**: Might feel odd for some commands

**Why It Matters**: CLI consistency and user experience.

---

### Q3.12: Type Sharing - JSON Schema Approach

**Context**: Sharing types between Python and TypeScript.

**Question**: How should we implement type sharing via JSON Schema?

**Approach**:
1. Define types in JSON Schema
2. Generate Python types from schema (dataclasses or Pydantic)
3. Generate TypeScript types from schema
4. Use schema for validation

**Alternative**: Manually maintain types in both languages (simpler but error-prone).

**Why It Matters**: Determines tooling and build process.

---

### Q3.13: Documentation - MkDocs for Future

**Context**: Documentation strategy for the future.

**Question**: If we outgrow Markdown in docs/, should we use MkDocs for documentation site?

**MkDocs**: Static site generator for documentation (like Read the Docs).

**Why It Matters**: Determines future documentation infrastructure.

---

### Q3.14: Performance Metrics - Tracking

**Context**: Tracking pipeline performance over time.

**Question**: Should we log performance metrics?

**Metrics**:
- Extraction time
- Database size
- Wiki update time
- Number of entities
- Upload speeds

**Storage**: SQLite table or JSON files

**Why It Matters**: Useful for detecting performance regressions.

---

### Q3.15: Notification - CLI Output Verbosity

**Context**: Command outputs can provide varying levels of information.

**Question**: How verbose should "next steps" hints be?

**Example after extraction**:
```
Minimal:
✓ Extraction complete!

Medium:
✓ Extraction complete!
Next: erenshor wiki update

Verbose:
✓ Extraction complete!

Next steps:
  • Update wiki pages:     erenshor wiki update
  • Deploy to sheets:      erenshor sheets deploy
  • Export maps data:      erenshor maps export
```

**Why It Matters**: Balance helpful vs. overwhelming.

---

## Summary by Priority

### Priority 1 (Blockers): 6 questions
- Q1.1: Template list for auto-generation
- Q1.2: Section vs template updates
- Q1.3: Database backups for analysis
- Q1.4: Conflict resolution strategies
- Q1.5: Change detection detail level
- Q1.6: Pipeline state timeout

### Priority 2 (Important): 16 questions
- Q2.1 - Q2.16: Various implementation details

### Priority 3 (Nice to Know): 15 questions
- Q3.1 - Q3.15: Polish and UX details

---

## How to Respond

For each question, provide:

1. **Answer** (choose option or provide custom answer)
2. **Rationale** (why this choice makes sense)
3. **Additional context** (if needed)

**Example Response Format**:

```markdown
### Q1.1: Manual Content Preservation - Template List

**Answer**:
Items:
  - {{Item Infobox}}
  - {{Loot Table}}

Characters:
  - {{Character Infobox}}
  - {{Spawn Locations}}
  - {{Abilities}}

...

**Rationale**: These are all the templates we currently auto-generate.

**Additional Context**: We might add {{Crafting Recipe}} in the future.
```

---

## Remaining Decisions Needed

Once these questions are answered, we'll have everything needed to proceed with implementation. Any questions that remain open can be decided during implementation or deferred to later phases.

**Recommended approach**: Focus on Priority 1 (blockers) first, then tackle Priority 2 during implementation, defer Priority 3 until needed.
