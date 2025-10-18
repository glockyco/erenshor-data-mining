# Wiki Service Design Questions

## Context

Implementing WikiService for Task 2.5 (Phase 3) with push-style notifications.

## Questions

### 1. Page Title Resolution

**Question**: Where do wiki page titles come from?

The page generators take `page_title` as a parameter (e.g., `ItemPageGenerator.generate_page(item, page_title="Sword of Truth")`), but how do we determine the correct wiki page title for each entity?

**Options**:
- a) Use entity name directly (e.g., `item.item_name`)
- b) Add a naming registry/service that provides canonical wiki page titles
- c) Use MediaWiki's title convention: `{Namespace}:{Name}` (e.g., `Item:Sword`, `Character:Goblin`)
- d) Defer this for now and use simple entity names

**Decision**: For now, use MediaWiki namespace convention: `Item:{item_name}`, `Character:{character_name}`, `Spell:{spell_name}`. This matches wiki.gg conventions and is simple to implement.

### 2. Batch Size for Wiki API Calls

**Question**: Should we fetch existing wiki pages in batches or one-by-one?

MediaWikiClient supports batch fetching (`get_pages()`), but we also need to update pages individually. Should we:
- a) Fetch all existing pages in batches, then update one-by-one
- b) Fetch and update one-by-one (simpler but slower)
- c) Make it configurable

**Decision**: Fetch in batches, update one-by-one. This balances performance with clarity. Fetching is read-only and safe to batch, while updates should be individual for error handling and progress tracking.

### 3. Error Handling Strategy

**Question**: When a page update fails, should we:
- a) Stop the entire batch (fail-fast)
- b) Continue processing other pages (fail-soft)
- c) Make it configurable

**Decision**: Fail-soft. Continue processing other pages and collect errors for final report. This allows partial success and gives users visibility into all failures at once, not just the first one.

### 4. Dry-Run Implementation

**Question**: What should dry-run mode do?
- a) Generate content but don't call MediaWiki API
- b) Generate content, fetch existing pages, show diffs, but don't update
- c) Skip generation entirely, just show what would be processed

**Decision**: Option (a) - generate content but skip all MediaWiki API calls (both fetch and update). This allows testing the generation pipeline without hitting the wiki. For diff viewing, we can add that as a separate feature later.

### 5. Progress Display

**Question**: Should we use:
- a) Rich progress bar with live updates
- b) Simple line-by-line output with warnings/errors inline
- c) Both (progress bar + inline notifications)

**Decision**: Option (c) - progress bar for overview, inline warnings/errors as they occur. This provides both high-level progress tracking and detailed issue visibility.

### 6. Warning Categories

**Question**: What warnings should be shown?
- Manual edits detected
- Legacy templates found
- Large content changes (e.g., >50% diff)
- Missing database fields
- Other?

**Decision**: Start with:
- Manual edits detected (preserved fields have content)
- Legacy templates found and removed
- API errors (rate limits, network issues)

Keep it simple initially, can expand based on user feedback.

### 7. Service Initialization

**Question**: Should WikiService:
- a) Take all dependencies as constructor parameters (DI)
- b) Create its own instances internally
- c) Mix of both (client injected, generators created internally)

**Decision**: Option (a) - full dependency injection. This keeps the service testable and follows clean architecture principles. Create a factory or builder if initialization becomes complex.

### 8. UpdateResult Structure

**Question**: Should UpdateResult include:
- Detailed per-page results (list of successes, failures)?
- Just summary counts?
- Warnings and errors as separate lists?

**Decision**: Summary counts + separate warning/error lists. Detailed per-page results would be too verbose for console output. Users can check logs for full details.

## Decisions Made

1. Page titles: Use MediaWiki namespace convention (`Item:{name}`, etc.)
2. Batching: Fetch in batches, update individually
3. Error handling: Fail-soft, continue processing on errors
4. Dry-run: Generate content, skip all wiki API calls
5. Progress: Progress bar + inline warnings/errors
6. Warnings: Manual edits, legacy templates, API errors
7. DI: Full dependency injection
8. UpdateResult: Summary counts + warning/error lists
