# Proposal

## Why

A character's image name currently selects a capture without proving that every character with that name shows the same model. A shared name can therefore give visibly different characters one portrait on the wiki and the map, even when the clean build and the pixel-title collision check succeed.

## What Changes

- Validate every character's final render title against its exported model identity before looking up approved pictures, regardless of page membership, display name, visibility, or existing captures.
- Give each different look its own image name, capture subject, reviewed render, and title. Allow different exported model keys to share a subject only through an explicit, reviewed same-look declaration.
- Bind capture manifests and approvals to the model membership they represent, so a title change or changed model cannot silently reuse another look's approval.
- Carry the resolved portrait identity through character deduplication, generated wiki data and sections, and map portrait hashes without changing character names, article identities, loot, or spawn probabilities.
- Resolve all existing shared-name model collisions in one cutover. Preserve published file histories and old title resolution, and leave editor screenshots and editor-owned files alone.
- Compare new player-visible title options through the `compare-options` skill and Plannotator before accepting titles. Require separate publication approval before any live wiki write.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `game-image-catalog`: validate character title-to-model membership before capture lookup, record reviewed same-look groups, and preserve each member's portrait through catalog and consumer selection.
- `wiki-images`: capture each resolved character look independently, bind reviews and approvals to that look, and migrate split titles without losing published title resolution or editor screenshots.

## Impact

The implementation changes `mapping.json` and its loader, character processing and clean portrait metadata, model-image manifests and approvals, catalog linking, generated character wiki output, and portrait-sensitive deduplication and map queries. Existing capture, review, approval, publication, and rollback workflows remain the entry points. No new rendering preset, item-image policy, gameplay data derivation, or game exporter fingerprint algorithm is introduced.

The migration boundary is all character image names in the selected variant, including unused, hidden, summon, chest, and page-less characters. Item, ability, and stance titles retain their current rules and cross-kind title collision checks. This change is separate from character article conversion and live NPC identity work. Planning authorizes no game launch, capture, code change, file publication, article write, or deployment.
