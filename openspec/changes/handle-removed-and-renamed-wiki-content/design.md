## Context

See `proposal.md` for the problem and `specs/wiki-content-lifecycle/spec.md` for the behavior. The plan of record is `adopt-data-backed-wiki`, especially D2, D3, D7, D10, D12, and D14. `Reckless` and `Stance: Reckless` remain live, although generation no longer writes them. The old skill-book title belongs to the same item key as its new title.

`WikiStorage.remove_stale_pages` removes local fetched pages and metadata during a full generation. `WikiFetchService` fetches only current generator titles. `plan_article_deploy` reads only generated titles. None of these paths can discover old live pages after their local metadata has gone. A local metadata difference is therefore not a complete live-page check.

No notice or message-box template exists under `wiki/templates/`. `Zone Navbox.wiki` uses a bordered `navbox` with a dark heading. The new notice can use that existing box treatment, without a new wiki interface style. The repository owns templates and category text. People own the prose outside generated article roots.

## Goals / Non-Goals

**Goals:**

- Show the difference between removed content, a renamed page, and content that remains but cannot be obtained.
- Preserve the old article and an editor's useful explanation without copying people-owned pages into the repository.
- Review live retired bot pages even after local stale files have been removed.

**Non-Goals:**

- Delete historical pages or change `Recommended Gear`. Kyrros owns its advice.
- Infer removal merely from a missing generator title. A renamed title or a partial export can produce the same symptom.
- Rebuild an obsolete article from an entity that no longer generates a page. Legacy templates may gain optional fields, but existing fields remain unchanged.

## Decisions

### Notice and page ownership

Add `wiki/templates/Historical Content.wiki` and `wiki/content/Category/Removed Content.wiki` and `wiki/content/Category/Unobtainable Content.wiki`. The notice uses the bordered box and dark heading treatment of `Zone Navbox.wiki`. It needs no new CSS. Parameters are `state`, `thing`, `update`, `date`, and `url`. For `state=removed`, it says: “This <thing> is no longer in the game. It was removed in the <update> update (<date>).” For `state=unobtainable`, it says: “This item can no longer be obtained.” When a verified update exists, it also names the update and date with a link to its patch notes. Without an update, the second sentence is omitted. The notice adds `Category:Removed Content` or `Category:Unobtainable Content` in article namespace only. Each category page explains the state and where to report a wrong classification. No unowned template is called.

The Planar March update went live on 2026-07-13. Its [live patch notes](https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1837955055363541) say “Reckless Stance removed.” The template calls on `Reckless` and `Stance: Reckless` pass `thing=stance` and `thing=skill` respectively, `update=Planar March`, `date=July 13, 2026`, and that link. The template owns the notice markup and category, not the article's whole source. Existing pages keep their infoboxes and other prose.

For a page that generation still produces, read the recorded state and update into optional parameters of its `Item` or `Ability` root. Add `historical_state`, `historical_update`, `historical_date`, and `historical_url` to the legacy infobox templates. They show the status and update and call `Historical Content` after the infobox. Add `aka` to `Item` for a former name when useful. Existing fields and rendering do not change when these parameters are absent. The six generated pages with old notes are `Mana Burst`, `Mana Call`, `Spell Scroll: Mana Charge`, `Charged Soul Gem (Aragath)`, `Pristine Ceremonial Ring`, and `Unusual Copper Sceptre`. A one-time guarded edit removes each old note on these pages and keeps the two crafting explanations as prose. The three other scroll pages (`Spell Scroll: Mana Burst`, `Spell Scroll: Mana Call`, and `Spell Scroll: Mana Flood`) have no current generated or fetched file and receive one-time notices on the live wiki. `Reckless` and `Stance: Reckless` likewise receive one-time notices because generation no longer produces them. The generator never infers a removal from an absent title.

### Rename detection and redirects

Compare the stable keys from the old live article's template calls with the current `build_article_identity_map` output. If a key points to a different generated title, propose a rename. For `item:skillbook - stance - reckless`, replace the old `Skill Book: Reckless Stance` article with `#REDIRECT [[Skill Book: Reckless Strike]]` in one guarded bot edit after verifying that the target exists. The generated item infobox can show `aka=Skill Book: Reckless Stance`. The redirect is not removed content. Record the old title and current title in the reviewed rename entries. On ambiguous or multiple-entity pages, report an unresolved finding instead of choosing a target automatically.

### Live retirement audit

Add `uv run erenshor wiki audit-retired-pages` and run its same check during a full `uv run erenshor --dry-run wiki deploy`. Query WoWBot's new-page contributions with continuation, restricted to article namespace. Verify that candidates still exist in batches of at most 50. Compare live titles with the complete generated title set, not `metadata.json`. Read stable keys from the live article when possible and match them to current generated titles. Show a sorted table with old title, key if known, current title if one exists, expected disposition, and observed state (`pending notice`, `pending redirect`, `marked`, `redirect`, or `unexplained`). Show checked, pending, and unexplained counts. A recognized pending change is not unexplained. An unexplained page or an incomplete API result makes the audit fail, but it writes nothing. A selected-page generation run never claims a full audit.

Before migration the audit reports pending notices for `Reckless` and `Stance: Reckless` and a pending redirect for `Skill Book: Reckless Stance`. After migration it reports the same titles as resolved. The three scroll pages have no local generated files. Include each in the WoWBot-created-page report only if its live creation revision names WoWBot. Their reviewed records and notices need verification either way. A full deploy needs a successful dry run and approval under D10. The normal article deploy does not silently delete old pages. If an old identity reappears as a generated page, fail the classification check for review before editing the article.

### Source of removal facts

Keep the hand-written `content-lifecycle.json` at the repository root beside `mapping.json`. A `pages` mapping keyed by wiki page title gives `stable_key` where one still exists, `state` (`removed` or `unobtainable`), and optional `update`, `date`, and `patch_notes_url`. Record a reason or source with each classification, including the Planar March patch notes for Reckless. A separate `renames` mapping records old title, stable key, current title, and optional update evidence. It lets `Skill Book: Reckless Strike` display its former name without claiming that the item was removed. The reader validates dates, links, status, unique titles, and consistency with generated identities before a refresh. The file is not placed under `wiki/`: D2 permits only deployable page sources there. A known removed entity can remain in clean data, as `stance:reckless` does, without obtaining a generated wiki page. An unobtainable item stays generated and never gets the removal status.

### Failure handling and rollback

Test the notice and changed infoboxes in the local MediaWiki stack. Use TemplateSandbox on the live wiki before a repository-page deploy. Dry-run and review exact changes to all affected articles. Use fetched revision IDs, parse guards, and article rollback manifests for the one-time bot edits. Deploy the template, categories, and revised infoboxes before editing articles. A newer editor revision stops that edit and requires a new fetch and review. Rollback restores edited pages from the manifest. It does not delete pages created by a deploy.

## Risks / Trade-offs

- [An old article has no stable key] → Report the title without a key, and require a reviewed disposition rather than guessing from its name.
- [A missing generated page reflects a bad export] → The audit only proposes a classification. It does not mark pages automatically.
- [Old notes can be edited by people] → Review each diff and guard the revision. Preserve the crafting explanation as prose.
- [A renamed old title remains a useful link] → Keep its redirect. Never treat it as a deleted page.

## Migration Plan

1. Add the template, both category pages, the reviewed facts, the optional infobox fields, and focused checks. Verify the local render and the retirement audit.
2. Dry-run and deploy the repository pages after approval and the render check. Verify the notice and both categories render correctly.
3. Fetch and regenerate the six current articles from `content-lifecycle.json`. Review their fields and notices. Remove their old handwritten notes with revision guards while preserving both crafting explanations. Add notices to the three ungenerated scroll pages and the two old Reckless pages, then turn the old skill-book page into a redirect. Use guarded bot edits and retain a rollback manifest.
4. Run the retirement audit again. It must report the three known retired WoWBot titles with resolved dispositions, classify any other WoWBot-created old pages, and show no unexplained title. Check the six generated notices, five one-time notices, redirect, and both categories on the live wiki.
