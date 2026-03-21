---
name: commit-guidelines
description: Generate commit messages following project conventions. Use when creating git commits, reviewing staged changes, or writing commit messages.
---

# Commit Message Guidelines

Follow Conventional Commits format with prose descriptions.

## Format

```
type(scope): short summary in imperative mood

Prose description explaining what changed and why. Focus on reasoning
and context, not lists of files or bullet points. Write in complete
sentences. Wrap at 80 characters.
```

## Types

- **feat**: New feature or capability
- **fix**: Bug fix
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **style**: Formatting, whitespace, no code change
- **docs**: Documentation only
- **test**: Adding or updating tests
- **chore**: Maintenance tasks, dependencies, CI config

## Scopes

Common scopes: `mod`, `map`, `maps`, `wiki`, `sheets`, `cli`, `export`,
`protocol`, `domain`, `infra`

## Rules

- Imperative mood: "Add feature" not "Added feature"
- No period at end of summary line
- Summary line under 72 characters
- Body wrapped at 80 characters
- Prose over bullet points - write flowing sentences
- Explain why, not what (the diff shows what)
- No Claude attribution or co-author lines
- One concept per commit (atomic commits)

## Issue References

Reference GitHub issues in commit bodies:
- `Part of #N` - Contributes to but doesn't complete the issue
- `Closes #N` - Completes the issue (GitHub auto-closes on merge)

Place at end of commit body as a separate line.

## Good Example

```
feat(map): add enemy level filter with dual-thumb slider

Players can now filter spawn points by enemy level range. The slider
uses a dual-thumb design allowing min/max selection. Filter state
persists in the URL for shareable links.

Part of #42.
```

## Bad Example

```
feat(map): add enemy level filter

- Added LevelFilter component
- Updated MapControls to include filter
- Added URL state persistence
- Updated types

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

The bad example uses bullet points instead of prose, lists what changed
instead of why, and includes attribution lines that should not be added.
