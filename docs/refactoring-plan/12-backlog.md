# Backlog: Deferred Features

**Document Status**: Reference - Future Work
**Date**: 2025-10-16
**Purpose**: Track features and improvements deferred from initial refactoring

---

## Overview

This document tracks all features, improvements, and enhancements that were explicitly deferred to backlog during the refactoring planning process. These items are NOT part of the initial rewrite but may be implemented in future iterations.

**Priority Levels**:
- **High**: Should implement soon after initial rewrite
- **Medium**: Nice to have, implement when time allows
- **Low**: Optional enhancements, revisit if needed

---

## 1. Diff Command

**Priority**: High

**Description**: Show differences between current wiki content and newly generated content.

**User Request**: Q1.5, Q2.5

**Use Case**: User wants to see what would change before pushing to wiki, especially after fixing bugs in generators.

**Proposed Features**:
- `erenshor wiki diff <page>` - Show diff for specific page
- `erenshor wiki diff --all` - Show diffs for all changed pages
- Colored terminal output (additions in green, deletions in red)
- Optional HTML diff output for browser viewing

**Dependencies**: None

**Effort**: Medium (2-3 days)

**Why Deferred**: Not critical for initial implementation. Dry-run mode provides basic preview functionality.

**Notes**: Consider using Python `difflib` for diff generation.

---

## 2. Maps Performance Optimization

**Priority**: Medium

**Description**: Optimize maps initial load time and add offline support.

**User Request**: Q2.6, Q2.7, Issue 2

**Current Performance**: ~5 seconds initial load (acceptable for now)

**Proposed Improvements**:
1. **Compression** - gzip database for faster download (~70% size reduction)
2. **IndexedDB Caching** - Cache database in browser for subsequent loads (~100ms)
3. **Service Worker** - Enable offline support after first visit
4. **Lazy Loading** - Load map tiles data first, entity details on demand
5. **Streaming** - Stream database decompression for faster perceived load

**Dependencies**: None (all browser-based)

**Effort**: Medium (1-2 weeks)

**Why Deferred**: Current performance acceptable, full SQLite database required for future search functionality.

**Notes**: Revisit if load times become problematic or offline support becomes priority.

---

## 3. Advanced Change Detection

**Priority**: High

**Description**: Comprehensive game update detection with actionable reports.

**User Request**: Q3.7, Issue 6

**Proposed Features**:

### 3.1 C# Script Diffing
- Detect new/modified/deleted C# scripts
- Parse AST to identify specific changes (fields, methods, classes)
- Generate actionable reports: "Added field `craftingTime` to `ItemData.cs`"

### 3.2 ScriptableObject Field Comparison
- Compare exported database schemas across versions
- Detect new fields in existing tables
- Highlight fields with non-null values (indicates active use)

### 3.3 New Entity Type Discovery
- Scan for new ScriptableObject types
- Suggest listener implementation for new types

### 3.4 Actionable Reports
```
Game Update Summary (v1.0.5.0 → v1.0.5.3)

Data Changes (Automatic):
  • 5 new items, 2 new characters

Mechanic Changes (Manual Intervention Required):
  1. New Field: Items.craftingTime
     Actions:
     • Update ItemListener.cs to export craftingTime
     • Update Item wiki template to display crafting time

  2. New ScriptableObject: AchievementData
     Actions:
     • Create AchievementListener.cs
     • Create Achievements table in database
     • Create Achievement wiki template
```

**Dependencies**: Database backups for comparison

**Effort**: High (2-3 weeks)

**Why Deferred**: Basic entity count changes are sufficient initially. Advanced detection requires significant implementation effort.

**Notes**: Consider auto-generating listener boilerplate code for new fields/types.

---

## 4. Docker Support

**Priority**: Low

**Description**: Containerize project for easier setup on new systems.

**User Request**: Q2.11, Q2.12, Q2.13, Issue 9

**Challenges**:
- Unity dependency makes containerization complex
- Large image size (~5 GB with Unity)
- Unity licensing in containers
- Infrequent setup (solo dev, not worth effort now)

**Possible Approaches**:
1. **Full containerization** - Include Unity (complex, slow)
2. **Partial containerization** - Only Python/SteamCMD/AssetRipper (Unity on host)
3. **Dev container** - VS Code dev container for consistent dev environment

**Dependencies**: None

**Effort**: High (1-2 weeks)

**Why Deferred**: User rarely sets up on new systems, Unity blocker, YAGNI for solo hobby project.

**Notes**: Revisit if project needs to be handed over to another developer.

---

## 5. Full Documentation Site

**Priority**: Low

**Description**: Comprehensive documentation site beyond CLI docs.

**User Request**: Q3.13

**Proposed Tool**: MkDocs (static site generator)

**Content**:
- Architecture overview
- Developer guide
- API reference
- Troubleshooting
- FAQ

**Dependencies**: None

**Effort**: Medium (1 week for initial setup, ongoing maintenance)

**Why Deferred**: CLI docs + CLAUDE.md + planning docs are sufficient for now.

**Notes**: Revisit if documentation grows beyond manageable size in Markdown files.

---

## 6. Pre-Defined Section Structures

**Priority**: Medium

**Description**: Standard section templates for different wiki page types.

**User Request**: Issue 1 follow-up

**Concept**: Each entity type has predefined sections that are auto-generated:

**Example - Character Page**:
```
== Overview ==
[Auto-generated description]

== Statistics ==
[Auto-generated stats table]

== Spawn Locations ==
[Auto-generated spawn table]

== Loot ==
[Auto-generated drop table]

== Abilities ==
[Auto-generated ability list]

== Strategy ==
[Manual content - preserved]

== Trivia ==
[Manual content - preserved]
```

**Implementation**:
- Define section structure per entity type in config
- Mark sections as "managed" (auto-generated) or "manual" (preserved)
- Update managed sections, preserve manual sections

**Dependencies**: Template-based content merging (Phase 4)

**Effort**: Medium (1-2 weeks)

**Why Deferred**: Need to establish basic template update system first. Pre-work in Phase 4 can make this easier in future.

**Notes**: Consider allowing custom section structures via config overrides.

---

## 7. Auto-Generated Listener Code

**Priority**: Low

**Description**: Generate C# listener boilerplate for new fields/types.

**User Request**: Q2.5

**Concept**: When change detection finds new field, offer to generate listener code:

```csharp
// Detected: Items.craftingTime (float)
// Generated boilerplate:

if (item.craftingTime > 0) {
    record.CraftingTime = item.craftingTime;
}
```

**Challenges**:
- Need to infer correct C# code from field type
- May generate incorrect code (requires manual review anyway)
- C# code generation from Python is complex

**Dependencies**: Advanced change detection (Backlog Item #3)

**Effort**: High (2-3 weeks)

**Why Deferred**: Limited value (still need manual review), high complexity.

**Notes**: May not be worth implementing. Manual implementation is straightforward.

---

## 8. Image Upload Automation

**Priority**: High

**Description**: Full automation of image uploads to wiki.

**User Request**: Q3.2, Q3.3

**Current State**: Semi-automatic (bulk upload works, finding changed images manual)

**Proposed Features**:
1. **Change Detection** - Use recentchanges API to find images modified in game
2. **Batch Upload** - Upload all changed/new images automatically
3. **Comparison** - Compare game images to wiki images (detect visual changes)
4. **Dry-Run** - Preview which images would be uploaded

**Dependencies**: MediaWiki file upload API

**Effort**: Medium (1-2 weeks)

**Why Deferred**: Current semi-automatic approach works. Full automation is goal but not critical initially.

**Notes**: User mentioned "see the current implementation" - need to review existing image handling.

---

## 9. Advanced Logging Features

**Priority**: Low

**Description**: Enhanced log viewing and management commands.

**User Request**: Q3.5, Q3.6

**Proposed Commands**:
```bash
erenshor logs show              # Show recent logs (last 50 lines or 5 minutes)
erenshor logs show --all        # Show full log
erenshor logs show --errors     # Show only errors
erenshor logs tail              # Live tail of log file
erenshor logs tail --filter <pattern>  # Tail with regex filter
```

**Use Cases**:
- Quickly check recent errors after command failure
- Monitor long-running operations
- Debug issues without opening log file manually

**Dependencies**: None

**Effort**: Low (1-2 days)

**Why Deferred**: Direct file access is sufficient for now. See Research Tasks for UX recommendations.

**Notes**: Consider if these commands provide enough value over `tail -f variants/main/logs/latest.log`.

---

## 10. Performance Metrics Dashboard

**Priority**: Low

**Description**: Visualize performance metrics over time.

**User Request**: Q3.14

**Current Plan**: Store metrics in SQL (sufficient for queries)

**Dashboard Features**:
- Extraction time trends
- Database size growth
- Upload speeds
- Entity count changes
- Wiki page update counts

**Proposed Tool**: Simple web dashboard (Flask + Chart.js)

**Dependencies**: Performance metrics tracking (in SQL)

**Effort**: Medium (1 week)

**Why Deferred**: SQL queries provide actionable data. Dashboard is nice-to-have visualization.

**Notes**: May not be worth effort for solo dev. SQL queries + terminal output likely sufficient.

---

## 11. Resume for Individual Stages

**Priority**: Low

**Description**: Resume specific stages (wiki, sheets, maps) independently.

**User Request**: Q2.4

**Example**:
```bash
erenshor wiki update --resume   # Resume just wiki portion
erenshor sheets deploy --resume # Resume just sheets portion
```

**Complexity**: State tracking per stage, more complex than full pipeline resume.

**Dependencies**: Full pipeline resume (Phase 2)

**Effort**: Medium (1 week)

**Why Deferred**: Full pipeline resume is sufficient. Can manually run remaining stages if needed.

**Notes**: Consider if this adds enough value over running stages manually.

---

## 12. CLI Auto-Completion

**Priority**: Low

**Description**: Shell auto-completion for CLI commands.

**Tools**: Typer has built-in completion support

**Shells**: Bash, Zsh, Fish

**Implementation**:
```bash
# Generate completion script
erenshor --install-completion

# Or manually
eval "$(_ERENSHOR_COMPLETE=source_bash erenshor)"
```

**Dependencies**: Typer (already in use)

**Effort**: Low (1 day - mostly documentation)

**Why Deferred**: Nice quality-of-life feature but not critical.

**Notes**: Very easy to add if user wants it. Typer handles most of the work.

---

## 13. Progress ETAs

**Priority**: Low

**Description**: Show estimated time remaining in progress bars.

**User Request**: Q3.8

**Example**: "Uploading pages... 25/100 (ETA: 2m 30s)"

**User Preference**: "Nah, those estimates are bound to be inaccurate. No need to have them."

**Dependencies**: None

**Effort**: Low (1-2 days)

**Why Deferred**: User explicitly doesn't want inaccurate estimates.

**Notes**: May still implement basic ETA for very predictable operations (e.g., file downloads).

---

## 14. Cargo Integration (Wiki Extension)

**Priority**: High (if wiki team wants it)

**Description**: Integrate MediaWiki Cargo extension for structured data storage.

**User Question**: "the wiki team has long wanted to introduce Cargo to the wiki (the extension is available already), but we've only done some very small-scale manual testing. How to properly integrate cargo? Should that be considered in some way in our new architecture as well?"

**What is Cargo**: MediaWiki extension that stores template data in database tables for querying.

**Potential Benefits**:
- Query wiki data via SQL (e.g., "find all items with level > 10")
- Generate dynamic lists/tables from wiki content
- Reduce duplicate data entry

**Architectural Considerations**:
- Would our auto-generated templates work with Cargo?
- Do we need to change template structure?
- Can we auto-populate Cargo tables during wiki updates?

**Dependencies**: Understanding of Cargo extension, wiki team requirements

**Effort**: Unknown (need research)

**Why Deferred**: Needs investigation and answer from AI (see Research Tasks).

**Notes**: **This is a priority item** if wiki team actively wants Cargo integration.

---

## Summary by Priority

### High Priority (implement soon after initial rewrite)
1. Diff Command
2. Advanced Change Detection
3. Image Upload Automation
4. Cargo Integration (if wiki team wants it)

### Medium Priority (nice to have)
5. Maps Performance Optimization
6. Pre-Defined Section Structures

### Low Priority (revisit if needed)
7. Docker Support
8. Full Documentation Site
9. Auto-Generated Listener Code
10. Advanced Logging Features
11. Performance Metrics Dashboard
12. Resume for Individual Stages
13. CLI Auto-Completion
14. Progress ETAs (user doesn't want)

---

## Revisiting Backlog Items

**When to Revisit**:
- After initial rewrite is stable and validated
- When pain points emerge during regular use
- When user requests specific feature
- When dependencies become available

**Process**:
1. Review backlog item
2. Assess current priority
3. Estimate effort
4. Get user approval
5. Implement in focused iteration

**Don't Implement**:
- Features that solve theoretical problems
- Features that add complexity without clear value
- Features that duplicate existing functionality

---

**End of Backlog**
