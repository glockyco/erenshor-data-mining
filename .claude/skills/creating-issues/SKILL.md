---
name: creating-issues
description: Create GitHub issues for development tasks. Use when adding new issues or updating existing ones.
---

# Creating Issues

Development issues follow a consistent structure to ensure clarity and
trackability.

## Structure

### Summary
One sentence describing what this issue accomplishes. Be specific and concise.

### Context
Why this work is needed:
- Problem being solved or goal being achieved
- Dependencies on other issues (link them with #number)
- Relevant background information

### Tasks
Checklist of concrete work items:

```markdown
- [ ] First task
- [ ] Second task
- [ ] Third task
```

Use checkboxes for trackability. Break down into small, verifiable steps.
Mark completed items with `[x]` as work progresses.

### Acceptance Criteria
Observable outcomes that indicate completion:
- Specific behavior that should work
- Commands that should succeed
- States that should be true

Focus on "what" not "how". These should be verifiable by someone other than
the implementer.

### Planned Commits
Document the atomic commits that will implement this issue:

```markdown
## Planned Commits

1. `type(scope): short description`
   - What this commit includes
   - Key changes or files affected

2. `type(scope): another description`
   - Details about this commit
```

This provides:
- Implementation roadmap for the developer
- Context for reviewers about the intended structure
- Reference point for tracking progress on complex changes
- Forces upfront thinking about how to break down the work

Even single-commit issues should document the planned commit - it clarifies
intent and ensures the commit message is thought through before implementation.

### Notes (optional)
Additional context that doesn't fit above:
- Constraints or limitations
- Related issues or alternatives considered
- Technical details for implementers

## Labels

Use existing labels consistently:

**Component labels**:
- **mod**: BepInEx plugin code
- **map**: Interactive map website (Svelte/deck.gl)
- **cli**: Python CLI tooling
- **protocol**: WebSocket protocol design
- **export**: Unity export system
- **wiki**: Wiki deployment
- **sheets**: Google Sheets deployment
- **infrastructure**: Build, CI/CD, tooling
- **documentation**: Docs and skills

**Priority labels**:
- **P0-critical**: Blocking, must do first
- **P1-high**: Important for milestone
- **P2-medium**: Should do
- **P3-low**: Nice to have

## GitHub CLI Commands

### Creating Issues

Use `gh issue create` with all metadata in one command:

```bash
gh issue create \
  --title "Issue title" \
  --label "mod" --label "P1-high" \
  --milestone "Interactive Map: Foundation" \
  --project "Erenshor Data Mining" \
  --body "$(cat <<'EOF'
## Summary
...
EOF
)"
```

Always use `--project "Erenshor Data Mining"` to assign to the correct project.

### Verifying Project Assignment

```bash
gh issue view <number> --json projectItems
```

### Listing Available Labels and Milestones

```bash
gh label list
gh milestone list
```

## Example

```markdown
## Summary

Add WebSocket server for live entity broadcasting.

## Context

The interactive map needs real-time entity positions from the game. This
enables the "live mode" feature where users see player and NPC positions
update in real-time.

## Tasks

- [ ] Add Fleck WebSocket server initialization in Plugin.cs
- [ ] Create message serialization for entity state
- [ ] Handle client connections and disconnections
- [ ] Broadcast state to all connected clients at configurable interval
- [ ] Add BepInEx configuration options for port and interval

## Acceptance Criteria

- WebSocket server starts on plugin load
- Clients can connect to ws://localhost:18584
- Entity state is received by connected clients
- Server handles disconnections gracefully without errors

## Planned Commits

1. `feat(mod): add Fleck WebSocket server initialization`
   - Add Fleck NuGet dependency
   - Initialize server in Plugin.cs OnEnable()
   - Add basic connection handling

2. `feat(mod): add entity state message serialization`
   - Create EntityStateMessage class
   - Implement JSON serialization

3. `feat(mod): add client broadcast loop`
   - Implement timed broadcast to all connected clients
   - Add BepInEx config for port and interval

## Notes

- Default port 18584 (configurable via BepInEx config)
- Binds to 0.0.0.0 for LAN access (phone as second screen)
```

## Updating Existing Issues

When updating an issue:
- Mark completed tasks with `[x]`
- Add new tasks discovered during implementation
- Update acceptance criteria if scope changed
- Add notes explaining any deviations from original plan
