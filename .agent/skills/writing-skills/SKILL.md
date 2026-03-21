---
name: writing-skills
description: Create new agent skills for this project. Use when adding reusable guidance for recurring tasks or capturing project-specific knowledge.
---

# Writing Skills

Skills provide reusable instructions that agents can load on-demand. They help
maintain consistency and capture non-obvious knowledge.

## When to Create a Skill

Create a skill when:
- A task recurs and benefits from a consistent approach
- Patterns are non-obvious or easy to forget
- A process has multiple steps that should be followed in order
- Project-specific conventions need enforcement

Avoid creating skills for:
- One-off tasks
- Information that belongs in regular documentation
- Simple facts that don't require guidance

## File Structure

```
.claude/skills/<skill-name>/SKILL.md
```

The directory name must exactly match the `name` in frontmatter.

## Frontmatter

Required fields only:

```yaml
---
name: my-skill-name
description: Brief description. Use when [specific trigger conditions].
---
```

**Name rules**:
- 1-64 characters
- Lowercase alphanumeric with single hyphens
- No leading/trailing hyphens, no consecutive hyphens
- Must match containing directory name

**Description rules**:
- 1-1024 characters
- Include "Use when..." to help the agent know when to load it
- Be specific enough to distinguish from other skills

## Content Structure

```markdown
# Title

Brief intro explaining what this skill covers (1-2 sentences).

## Section 1
Actionable guidance with examples.

## Section 2
More guidance, patterns, or rules.

## Common Pitfalls (optional)
Things to avoid or watch out for.
```

## Content Principles

Skills should contain **project-specific, non-obvious, arbitrary decisions** -
things an agent can't derive from first principles or by reading existing code.

**Include**:
- Architectural decisions ("Harmony patches get services via static properties")
- Arbitrary conventions ("JSON enums use snake_case")
- Project-specific constraints ("PolySharp needed for Unity compatibility")
- Multi-step processes with non-obvious order
- Checklists for tasks that are easy to partially complete

**Exclude**:
- General programming knowledge ("here's how C# records work")
- Patterns the agent can learn by reading existing code
- Reference material that belongs in external documentation
- Syntax examples for standard language features

**Test**: Before adding content, ask "Could an experienced developer figure
this out by reading the codebase?" If yes, don't include it.

A 100-line skill with only project-specific content is more useful than a
300-line skill padded with general knowledge.

## Content Guidelines

**Do**:
- Focus on actionable guidance (what to do, how to do it)
- Include code examples only where they show project-specific patterns
- Use good/bad examples for conventions
- Keep it concise (50-100 lines is ideal, 150 max)
- Use imperative mood ("Add the hook" not "You should add the hook")

**Don't**:
- Duplicate information from regular docs or CLAUDE.md
- Include general language/framework tutorials
- Write exhaustive references (link to docs instead)
- Add content that rarely applies

## Skill Categories

**Process skills**: Step-by-step guides for multi-step tasks.
Example: `adding-export-types` walks through adding a new data exporter.

**Convention skills**: Rules and patterns to follow consistently.
Example: `commit-guidelines` defines commit message format.

**Debugging skills**: Troubleshooting approaches for specific problems.
Example: `debugging` helps investigate export or deployment failures.

## Checklist

Before committing a new skill:

- [ ] Directory name matches frontmatter `name` exactly
- [ ] Description includes "Use when..." trigger
- [ ] Content is actionable, not just informational
- [ ] Examples included where they add clarity
- [ ] Length is appropriate (not too short, not exhaustive)
- [ ] No duplicate information from existing docs or skills

## Keeping Skills Fresh

- **Reference patterns, not instance counts.** "All listeners implement `IAssetScanListener`" stays true. "There are 25 listeners" goes stale the next day. Reference directories and types, not enumerations.
- **Update in the same commit.** If you change a workflow documented in a skill, update the skill in the same commit. Don't create a separate "docs" commit later — it will be forgotten.
- **When renaming a skill**, grep for its old path in source files. Key entry points have skill pointers in comments (e.g., `// See .agent/skills/<name>/SKILL.md`).
- **Skills document non-obvious knowledge.** Common programming knowledge and things derivable from reading code do not belong. The test: would an agent get this wrong without the skill? If no, don't add it.
- **Cross-reference, don't duplicate.** If knowledge exists in another skill, point to it by name. If it exists in code comments, reference the file. Never maintain the same fact in two places.