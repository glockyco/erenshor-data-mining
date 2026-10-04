## Why

When the game removes or renames something, its old wiki page remains live even after generation stops writing it. Existing notes use different wording, and the next refresh can silently lose track of an old page.

## What Changes

- Keep pages about removed content and give them one repository-owned notice and a maintenance category. Replace the existing hand-written notes without losing useful explanations.
- Give old titles of renamed content redirects to their current titles.
- Check for live pages created by WoWBot that generation no longer produces. Report each title and its disposition before a full refresh.
- Mark content that remains in the game but cannot be obtained differently from removed content.

## Capabilities

### New Capabilities

- `wiki-content-lifecycle`: How the wiki identifies, keeps, marks, and reports removed, renamed, and unobtainable content.

### Modified Capabilities

None.

## Impact

The implementation affects repository wiki templates and category pages, the article generation and deploy review path, the wiki command group, and focused tests. The first historical pages are `Reckless` and `Stance: Reckless`. The first redirect is `Skill Book: Reckless Stance` to `Skill Book: Reckless Strike`. All nine existing notes are replaced through guarded live edits after a dry run and approval. The wiki's people-owned pages stay on the wiki, not in the repository. No page is deleted, and the bot does not edit `Recommended Gear`.
