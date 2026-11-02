# Design

## Context

See `proposal.md` for the problem and scope. This is a planning audit of repository code and read-only SQLite, not a runtime appearance review.

### Current paths

- `mapping.json` supplies character image names through `processor/mapping.py`. `processor/characters.py:688-702` then changes some names through `model_image_names`, but only for generated pages. `processor/model_images.py:41-50` skips a page with one display-name kind before checking whether that kind contains several model keys.
- `services/model_image_manifest.py:211-237` groups by subject and selects one capture source. `processor/pictures.py:248-263` assigns that subject's approved pixel hash to every matching character. The later title-to-pixel collision check cannot detect different models already collapsed to one approval.
- The raw `Characters.ModelKey` is a fingerprint of enabled mesh renderer mesh and material asset identifiers, sorted and hashed by `CharacterListener.cs:506-535`. It is an asset fingerprint, not a visual comparison. Different keys can depict one look, so key inequality triggers review rather than proving visible difference.
- Character deduplication in `processor/characters.py:217-227` uses display name, statistics, flags, attack skills, and loot, not portrait identity. Map queries in `src/maps/src/lib/database.base.ts:528-659` select the representative's `image_hash`. `application/maps/catalog_images.py` emits derivatives by pixel hash. The search popups already collect distinct hashes from their character alternatives.
- Generated wiki character sections derive render and screenshot titles from `image_name`. `wiki_lua/characters.py:297-310` emits only the representative's pictures, while `wiki_lua/link_catalog.py` emits character link pictures. The implementation must update both section output and data-backed output rather than relying on the unfinished article-conversion change to do it.
- `cli/commands/images.py` implements manifest, capture, review, approve, and publish. Only capture needs a running game with MapTileCapture. Review reads the wiki and writes local contact sheets. Approval copies local files. Publication can move files and delete orphan files, so old-title preservation needs an explicit migration input rather than a naming change alone.

### Collision audit and method

Both connections used SQLite `file:...?mode=ro` URIs. The clean source was `variants/main/erenshor-main.sqlite`, with `variants/main/erenshor-main-raw.sqlite` attached as `raw`. All 1,254 clean characters had an image hash, every stable key joined a raw character, and none had an empty model key. This is a current audit, not a fixed completeness threshold.

The grouping query was:

```sql
SELECT c.image_name,
       COUNT(*) AS characters,
       COUNT(DISTINCT r.ModelKey) AS model_keys,
       COUNT(DISTINCT c.display_name) AS display_names,
       COUNT(DISTINCT c.npc_name) AS npc_names,
       GROUP_CONCAT(DISTINCT c.display_name) AS names
FROM characters c
JOIN raw.Characters r ON r.StableKey = c.stable_key
WHERE c.image_hash IS NOT NULL
GROUP BY c.image_name
HAVING COUNT(DISTINCT r.ModelKey) > 1
ORDER BY c.image_name;
```

It found 73 image names covering 193 character rows and 173 model keys summed within names. The full list, member stable keys, names, scenes, model labels, and the detail query are in `image-name-audit.json`, not repeated here. The file numbers the model keys instead of quoting them, so equal labels mean equal keys, and the query returns the keys themselves.

The categories are reproducible object-name triage, not claims that the models look alike or that differently named assets are different runtime NPCs. First classify names whose trimmed, case-folded `object_name` values are all equal as `same-object-name`. For the remaining groups, normalize each object name by repeatedly removing the terminal pattern `(?:\s*\(\d+\)|\s*\d+|\s+(?:bkp|broken|combined|new|restored|observer|female|male|f|m))$`, trimming, and removing the prefix `^restored\s*`, until unchanged. One resulting family is `numbered-or-variant-copies`. Several families are `different-object-families`, including mixed groups. Apply case folding before the patterns.

| Kind | Image names | Character rows | Model keys summed within names |
| --- | ---: | ---: | ---: |
| Numbered or variant copies of one object-name family | 40 | 96 | 94 |
| Differently named object families sharing an image name | 28 | 80 | 69 |
| Other: identical object names with different model keys | 5 | 17 | 10 |
| Total | 73 | 193 | 173 |

For example, the second category contains the fire and ice Guardian of Brax assets and mixed renamed families. The third contains Braxonian Flame Well, Sean Figarello, Sivakayan Cleric, Thella Steepleton, and Vithean Immortal. These categories deliberately do not infer identity from `display_name`: only Lost Treasure has several curated display names in this collision set. Only Reaver of Sivakaya has several distinct non-normalized NPC names. Visual review must decide which keys really need separate portraits.

The two A Lost Sea Giant rows have levels 8 and 11 and different model keys. The male key equals the Lost Sea Giant King's key. This establishes a missed collision without selecting either new title or treating shared model identity as a reason to merge the King's character identity.

## Goals / Non-Goals

Goals: one validated portrait look per final title, complete member coverage, explicit evidence for cross-key sharing, and a complete all-name migration with no successful build that silently assigns one look to another.

Non-goals: changing the exported fingerprint algorithm, item body rendering, the camera preset, gameplay calculations, character display names, article identities, live NPC identity, or publication infrastructure unrelated to portrait splits. Equal models on differently named characters may keep separate subjects and titles, with pixel deduplication preserving one physical picture.

## Decisions

### D1. Resolve and validate globally before catalog lookup

Replace the page-relative inference in `model_images.py` with one portrait resolver applied after mapping to every processed character, because page and display-name boundaries do not define model identity. Explicit character `image_name` mappings become the title choice. Materialize the existing Training Dummy distinctions in mapping or its existing deterministic dummy rule before removing the page-relative inference, so the cutover does not regress its established titles.

The resolver computes the final normalized subject and render title through `wiki_filename.py`, groups all character members by that title, and checks exported model keys. One key needs no exception. More than one key needs exactly one valid same-look declaration covering that title's full current membership. Empty model keys, collisions, stale declarations, and overlapping groups fail with the title, stable keys, model keys, pages, and the correction needed. Run this before any approved render lookup even when no captures exist. Retain the existing cross-kind and unequal-pixel title checks.

Persist `model_key` and resolved `portrait_look_key` in clean characters so manifest and consumers read the same decision without reconstructing it from names. A default look key is derived from the exported model key. An explicit group has a namespaced declaration identifier and its checked membership digest. Keep `image_name` as the resolved render subject. Reject an automatic suffix generator because it could turn an unreviewed asset label into player-visible wording.

### D2. Record cross-key sameness as a reviewed mapping declaration

Add a `character_model_looks` section to `mapping.json`, parsed and validated by its existing loader, because a same-look exception belongs beside the image-name choices it permits. Each declaration has an internal identifier, exact member stable keys with expected model keys, a capture representative stable key, a reason, and a review record. The review record names the game build, camera preset, comparison capture hashes for every distinct model key, and the human decision reference. Evidence files remain in the variant's capture review records. The mapping records their hashes and durable decision reference, not an unbounded image payload.

All declared members must resolve to one render title. A character belongs to at most one declaration, the representative must be a current member, and the declaration covers the title's full membership. Do not accept a broad allow flag, an empty reason, absent review evidence, chained equivalence, or new members by inheritance. A changed member, key, or reviewed membership invalidates the declaration. Identical keys need no declaration. Review several model keys side by side before marking one look, rather than inferring sameness from numbered names or equal levels.

### D3. Bind capture and approval to look membership

Extend character manifest entries, staged capture records, contact sheets, and approved records with sorted member keys, their model keys, the look identity and membership digest, selected capture source, and title, because a subject string alone cannot prove what a render depicts. Normal manifest generation consumes validated clean look metadata and selects only a source within that look. Existing source ranking and unsourced reporting remain.

A split creates separate normal subjects and captures for different looks. Same-look groups use their declared representative and one normal render. If that representative cannot be located, report the group as unsourced rather than capturing another look. Compare approval identity to current manifest identity before catalog linking. A missing or mismatched approval leaves that look without a render and cannot fall back to the old subject's pixels. A byte mismatch remains a hard failure under the existing approval contract.

Existing approval records lack this membership proof. Migrate them by explicit review against their retained manifest, source and bytes where that evidence exists, or recapture. Never clone the shared approval to all split titles. Preserve genuinely unchanged approvals after this one-time provenance review. Remove the legacy approval read path after migration instead of maintaining a permissive fallback.

### D4. Provide a bounded path for the review that resolves collisions

Add `images manifest --model-review` as a local comparison mode, because the new clean build must reject unresolved collisions before their same-look and title decisions can be made. It reads the last clean snapshot for capture locations and the selected raw export for current model keys, checks stable-key coverage and build alignment, and emits one review-only entry per colliding model key. Each entry uses an internal stable-key-based subject, no publishable wiki title, and its exact members and source. It must not guess sources for new or unmatched raw members.

Use the existing capture and review commands for this manifest, with contact sheets that show every colliding source and model key. Review-only entries are rejected by approve and catalog ingestion. The mode does not relax the clean build guard, write clean data, or create final titles. Once visual decisions and title comparisons are accepted, write final mappings and declarations, rebuild, run normal manifest generation, and capture the final subjects. This is an explicit review mode, not a compatibility alias or alternate publisher.

### D5. Carry portrait identity through wiki and map consumers

Include resolved portrait look and subject in portrait-sensitive character deduplication, because the map's representative must not erase a distinct portrait. Keep gameplay aggregation and total spawn probability invariant across the split. Map spawn alternatives retain their own hash and the existing search popups can show the distinct hashes. Verify located, unlocated, search, and NPC paths, not only the A Lost Sea Giant example. Do not replace pixel-hash image URLs with wiki titles or character names.

Wiki section generation emits the render associated with each displayed look without renaming the article or character. Data-backed character records retain render associations on member variants instead of only a representative-level render. Update the corresponding Lua consumer and link catalog callers so a multi-look article does not silently choose one portrait for all members. Keep a deterministic representative render only where a single thumbnail is required, and do not present it as depicting every variant. Compare any new visible arrangement or explanatory text through `compare-options` before it ships.

Preserve screenshot subject independently of render subject when a title splits, because existing screenshots belong to editors. Add an optional character `screenshot_name` mapping and clean field, defaulting to the unsplit image subject when migrating a split. Wiki section and data generation use this field for screenshot titles, while renders use the resolved image name. Keep existing screenshot files and captions. Do not move, delete, duplicate, or automatically reassign a screenshot to claim it depicts one new look.

### D6. Make old-title disposition an explicit publication input

Record a reviewed migration table with each old render title, old pixel hash, the look it depicts, its retained or new canonical title, and dependent pages and data modules, because the publisher's orphan cleanup otherwise has no reason to preserve an obsolete title. Keep the old title on that same look when its wording is accepted. If it changes, move a project-owned file with its history and leave a direct old-title redirect. Retarget existing redirects to the file, never through another redirect.

Protect these retired-but-preserved titles from orphan deletion as explicit migration redirects. If the old pixels also change, complete the reviewed move first and then update that look's file under existing ownership guards. Do not point the old title at the other look merely because it sorts first or shares a page. An old file of uncertain identity blocks that split pending review. An editor-owned file remains in place, and any required operation on it is a conflict rather than permission to overwrite it.

The dry run lists every mapping, preserved title, move, redirect, create, conflict, and dependent article or module change, with the old and new pictures. Visual capture approval and title wording approval do not authorize live writes. Obtain explicit approval of the complete publication plan before file, redirect, description, article, or module mutations.

### D7. Artifact ownership and write boundaries

| Artifact or file kind | Owner | Write boundary |
| --- | --- | --- |
| Image names, screenshot subjects, same-look declarations | `mapping.json` and `processor/mapping.py` | Reviewed repository edits only. No game asset or raw database edits. |
| Clean portrait metadata and deduplications | Character processor and clean schema writer | Existing clean build transaction and replacement boundary. Fail before publishing a replacement clean database on unresolved membership. |
| Normal and comparison manifests, staging and approvals | Existing `images` commands and model capture services | Selected variant's image directories only. Comparison mode is nonpublishable and root dry run prevents local writes. |
| Catalog pictures, links and titles | `processor/pictures.py` | Only approved matching look identities enter the catalog. Keep pixel hashes and immutable approved-byte checks. |
| Wiki sections, character data and Lua consumers | Existing character generators and checked-in wiki module files | Generate locally, then existing article or repository-page publication gates. No direct unreviewed wiki edits. |
| File migration table, redirects and upload journal | Existing image publication planner and run executor | Approved plan, account ownership, immediate live rechecks, and native journal before writes. |
| Map portrait derivatives and page data | Existing catalog derivative builder and map repository | Read the selected clean database, emit the complete matching site build. No title-based image lookup. |
| Workflow instructions | Existing image workflow section of `README.md` | Explain how to resolve a failed model-title check, review a same-look declaration, preserve screenshots, and run the gated cutover. Do not copy this audit or internal field inventory into the README. |

## Risks / Trade-offs

- Model-key inequality can overstate differences. Compare every distinct key before deciding between a separate look and a same-look declaration.
- Model keys are not a full appearance fingerprint. Keep their exporter limitation separate from this title-resolution change and report a confirmed runtime mismatch instead of overriding evidence with the key.
- Splitting deduplication can change row counts and representative keys. Assert unchanged gameplay totals and article identity, and test consumers with equal-stat different-look members.
- A broad image publication run can include unrelated queued changes. Review its complete dry-run plan and block publication unless the approved payload matches the intended cutover.
- Comparison mode needs an aligned prior clean snapshot. Reject stale build or unmatched-source input and obtain an aligned snapshot rather than bypassing validation.
- Same-look evidence can become unavailable. Keep evidence with the capture records and require new review when the proof cannot be inspected.

## Migration Plan

Implement sequential atomic units for resolution and review, identity-bound capture approval, consumer propagation, and publication migration. The first resolver unit includes the complete reviewed mapping migration rather than landing a default build that knowingly fails on existing collisions. Prepare comparison captures and decisions before activating that default guard. Final renders and consumer checks may remain local until the cutover is publication-ready.

Capture comparisons with the running game, decide same-look groups, compare new title options in Plannotator, and then write every required mapping. Run the clean build, normal manifest, final captures, review, and approval. Rebuild the catalog and map derivatives, generate wiki outputs, and verify the all-name audit has no unmarked multi-key titles. Include new collisions introduced since this audit rather than treating 73 as a fixed work list.

Publish files and preserved redirects first after approval, verify title resolution, and only then publish dependent article or data changes. Deploy the complete matching map build only with separate deployment authorization. Treat each old-title split and all its new looks as an indivisible dependency set for readiness. A failed capture, unresolved ownership conflict, stale approval, or missing title blocks that set's dependent publication. No article is allowed to name a render that has not been made available.

Use the existing publication journals and page deployment manifests for retry and rollback. An uncertain live result stops the run and is reconciled before retry. Roll back dependent wiki pages or data before reverting their files and moves, restore redirects from the run record, and restore the prior complete map build and clean/catalog set together. Preserve approved captures and both complete local output sets until acceptance. Do not prune old catalog hashes while a deployed site still references them.

## Open Questions

- Which of the colliding model keys actually look the same in the running game? The required visual review resolves this without changing the one-look-per-title contract.
- Which new title wording and any multi-look article presentation should ship? The implementation must compare options with the real data through the `compare-options` skill in Plannotator. No new player-visible title is selected here.
- Which look does each currently published shared file depict, and are its latest uploader and redirect targets project-owned? The migration review and live dry run resolve this before publication.
- When is the reviewed file and dependent wiki plan authorized, and when is map deployment authorized? Neither capture approval nor this proposal grants publication permission.

## Outside-scope finding

The exported model fingerprint omits renderer transforms and scale, skinned-mesh blend-shape weights, and runtime material property blocks from the data it hashes at `CharacterListener.cs:506-535`. Equal model keys therefore do not prove equal appearance in those dimensions. No runtime case was tested in this planning work. Changing that fingerprint is a separate exporter change and is not included here.
