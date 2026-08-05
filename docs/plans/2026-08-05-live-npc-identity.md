---
title: Live NPC Identity from the Companion Mod
type: plan
status: draft
created: 2026-08-05
parent: 2026-07-09-erenshor-planning-overview
superseded_by:
archived:
---

# Live NPC Identity from the Companion Mod

**Goal:** Make the live map overlay resolve the exact character behind an in-game
NPC, so its popup shows that character's own loot with plain percentages instead
of a merged list of every same-named candidate.

**Scope:** The InteractiveMapCompanion entity payload, the website's live NPC
popup and its character lookups, the protocol version on both sides, and the two
release channels. The merged-candidate view is kept as the fallback for mods that
send no identity and for creatures absent from the exported data.

## Why the current behaviour is wrong

The mod sends only a display name. 39 map-visible display names belong to more
than one deduplicated character, and for 22 of those the characters drop
different things, covering 52 characters in total. The overlay narrows by scene
and merges the survivors into probability ranges with a "N characters share this
name" note, which reads as hedging rather than an answer.

Two facts make an exact fix possible. A character's `stable_key` is built from
the editor asset name through `StableKeyGenerator.ForCharacter`, and
`stable_key = 'character:' || lower(trim(object_name))` holds for all 878
prefab-style rows, so no duplicate-suffix handling is needed. `SpawnPoint` keeps
the chosen prefab in its private `NextSpawn` field, and that prefab's `.name` is
exactly the `object_name` the key derives from. Of the 52 ambiguous characters,
43 are prefab-style and resolve through that path, and the remaining 9 are
scene-placed and resolve through `NPC.HomePos`.

The runtime object name is not usable: `NPC.cs:467` runs
`base.transform.name = NPCName` at startup, overwriting the prefab name.

## Tasks

Task 1 and Task 2 are independent and may be done in either order. The website
change is inert until a mod sends the new fields, and the new fields are ignored
by an older website.

### Task 1: Website resolves an exact character when identity is supplied

- [ ] Add two optional fields to `EntityData` in
      `src/maps/src/lib/map/live/types.ts`, documented as absent for mods older
      than protocol 0.3.0:
      `characterKey?: string` (an exact `characters.stable_key`) and
      `homePosition?: [number, number, number]` (the authored spawn position).
- [ ] Add `getCharacterByKey(stableKey: string): Promise<{ stableKey: string } | null>`
      to `src/maps/src/lib/database.base.ts` as
      `SELECT stable_key FROM characters WHERE stable_key = ? LIMIT 1`. It exists
      so an unrecognised key falls through to the next tier instead of rendering
      as "no drops", which calling the drops query directly could not distinguish.
- [ ] Add `getCharactersByHomePosition(scene: string, position: [number, number, number]): Promise<{ stableKey: string; npcName: string }[]>`
      to the same file, selecting `stable_key` and `npc_name` from `characters`
      where `scene = ?` and each of `ABS(x - ?)`, `ABS(y - ?)`, `ABS(z - ?)` is
      below `0.01`, ordered by `stable_key`. It returns a list because 376
      scene-placed characters occupy only 357 distinct positions. The tolerance
      sits below the two-decimal granularity the key format already assumes and
      absorbs float drift through JSON. Follow the `stmt.step()` and
      `stmt.free()` shape used by the neighbouring `getCharactersByName`.
- [ ] Change the predicate in the existing `getCharactersByName` from
      `WHERE c.display_name = ?` to `WHERE c.npc_name = ?`, and update its doc
      comment to say it matches the unmapped in-game name. This is a bug fix. The
      mod sends `Stats.MyName`, which `NPC.cs:518` assigns from `NPCName`, while
      `display_name` is the curated value `mapping.json` may override. The two
      differ for 34 characters, and for each of those the current query matches
      nothing and the popup shows an empty drop list. `character:reaver of sivakaya`
      is the worked example: the game sends `Assassin of Sivakaya` while the query
      looks for `Reaver of Sivakaya`. `LiveNpcPopupContent.svelte` is the only
      production caller, which `grep -rn getCharactersByName src/maps/src`
      confirms alongside the test file.
- [ ] Replace the single lookup in `loadData()` of
      `src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte` with an
      ordered cascade that stops at the first tier yielding candidates.
      One: `entity.characterKey` present and `getCharacterByKey` returns a row.
      Two: `entity.homePosition` present and `liveState.zone` non-null, through
      `getCharactersByHomePosition`, preferring rows whose `npcName` equals
      `entity.name` when more than one returns and keeping all rows when that
      subset is empty. Three: the existing
      `getCharactersByName(entity.name, liveState.zone)` with its in-scene
      preference. Mirror the existing `placed.length > 0 ? placed : matches`
      idiom rather than introducing a second one.
- [ ] Keep `variantCount` as the count of resolved characters and leave the
      markup untouched. A single character makes `aggregateDropVariants` yield
      `minProbability === maxProbability`, so `formatDropChance` already prints a
      plain percentage, and the shared-name note is already gated on
      `variantCount > 1`. Do not delete `aggregateDropVariants` or that note,
      because tier three still serves older mods and summoned creatures.
- [ ] Add `scene TEXT, x REAL, y REAL, z REAL` to the `characters` table in
      `src/maps/tests/fixtures/map-database.sql`, which currently lacks the
      placement columns the new query reads. The clean schema already has them,
      as the `coordinates` view in
      `src/erenshor/application/processor/writer.py` shows. Give
      `character:fixture enemy twin` the placement `('StowawayPortal', 40, 0, 60)`
      matching its existing spawn row and leave the other characters NULL.
- [ ] Give `character:runtime enemy` in that fixture
      `npc_name = 'Runtime Enemy Internal'` while keeping
      `display_name = 'Runtime Enemy'`. Every fixture character currently has the
      two columns equal, so nothing would otherwise catch a regression of the
      `npc_name` predicate. Existing assertions read `display_name` and are
      unaffected.

### Task 2: Mod sends the identity

- [ ] Add `public string? CharacterKey { get; }` and
      `public float[]? HomePosition { get; }` to
      `src/mods/InteractiveMapCompanion/src/Entities/EntityData.cs` as trailing
      optional constructor parameters so existing call sites keep compiling. The
      serializer uses `CamelCaseNamingStrategy` and omits nulls, so these reach
      the wire as `characterKey` and `homePosition` and vanish when unset, with
      no serializer change.
- [ ] Add `src/mods/InteractiveMapCompanion/src/Entities/CharacterIdentity.cs`
      exposing `public static string? TryGetCharacterKey(Character character)`
      and `public static float[]? TryGetHomePosition(Character character)`.
      `TryGetCharacterKey` reads the `NPC` component, its private `MySpawnPoint`,
      then that spawn point's private `NextSpawn`, returning
      `"character:" + prefab.name.Trim().ToLowerInvariant()` and null at any
      missing link. Reproduce that normalisation exactly, because it is what makes
      the string equal a `stable_key`. `TryGetHomePosition` returns the `NPC`
      component's private `HomePos` as `new[] { x, y, z }`.
- [ ] Resolve the three private fields with `AccessTools.FieldRefAccess` into
      static readonly accessors created once. HarmonyLib is referenced for both
      loaders through `lib/bepinex/0Harmony.dll` and `lib/lunaris/0Harmony.dll`,
      and only `src/Plugin.*.cs` is loader-conditional, so this file compiles into
      both artifacts with no extra wiring.
- [ ] Make a reflection failure return null and log a warning exactly once rather
      than throwing or logging per entity per frame. These fields are optional
      enrichment and a null degrades to the name-based tier, which discloses its
      own ambiguity, so nothing false reaches the reader. A game update that
      renames a private field must still surface in the log instead of silently
      reverting every player.
- [ ] Populate both fields in `EntityExtractor.Extract`, computing them only for
      `EntityType.NpcEnemy` and `EntityType.NpcFriendly`. Players, SimPlayers, and
      pets have no database character, so pass null and skip the reflection.
      Follow the private-static-helper style of `GetLevel`, `GetRarity`,
      `GetCharacterClass`, and `GetOwner` in that file.

### Task 3: Declare the protocol change

- [ ] Set `public const string Current = "0.3.0";` in
      `src/mods/InteractiveMapCompanion/src/Protocol/ProtocolVersion.cs`.
- [ ] Set `const EXPECTED_PROTOCOL_VERSION = '0.3.0';` in
      `src/maps/src/lib/map/live/connection.ts`. Leave the mismatch non-fatal, as
      the warn-and-continue branch is what lets an older mod keep working on tier
      three.
- [ ] Add no capability string. `ModConfigBase.GetCapabilities()` returns
      `["entities"]` and no website code branches on capabilities, so an entry
      would be dead weight when the website already detects support through the
      presence of the optional fields.

### Task 4: Release through both channels

The mod ships through two channels carrying different artifacts, and a release
that updates only one leaves half the users behind. Thunderstore packages the
BepInEx build and the command performs the upload. The Erenshor Vault takes the
Lunaris build and the upload is manual through the Vault website.

- [ ] Verify both loaders compile with
      `uv run erenshor mod build --mod interactive-map-companion --loader all`,
      since `CharacterIdentity.cs` reaches both artifacts while only the BepInEx
      one is exercised in game.
- [ ] Add a top entry to `src/mods/InteractiveMapCompanion/thunderstore/CHANGELOG.md`
      using its `## 2026.718.0` heading shape, with no `v` prefix.
- [ ] Add a matching top entry to `src/mods/InteractiveMapCompanion/vault/CHANGELOG.md`
      using its `## v2026.718.0` heading shape, with the `v` prefix. The version
      is CalVer computed by the release commands rather than chosen by hand, so
      run the command for a channel first, read the version it reports, then write
      the heading and re-run. The Thunderstore pipeline re-hashes the changelog
      immediately before upload, so an entry added after packaging will not ship.
- [ ] Package and validate with
      `uv run erenshor mod thunderstore --mod interactive-map-companion --dry-run`,
      which requires `dotnet tool install -g tcli` once. Report its output rather
      than publishing unprompted.
- [ ] Publish with
      `uv run erenshor mod thunderstore --mod interactive-map-companion` once the
      dry run is clean. The token comes from the environment or the repository's
      local `.env` and is never passed inline.
- [ ] Build the Vault artifact with
      `uv run erenshor mod vault --mod interactive-map-companion`, then upload the
      printed DLL by hand through the Erenshor Vault website, pasting the matching
      top entry from `vault/CHANGELOG.md` as the release notes. The Vault write
      API is not automated and this stays manual.
- [ ] Deploy the website half with `uv run erenshor maps build` followed by
      `uv run erenshor maps deploy`, which is what changes the popup for every
      user regardless of the channel their mod came from.

## Verification

`uv run erenshor test ci` runs the static gates and all five leaves. Add these
behaviour tests first, so it proves the new paths rather than only the old ones.

- `src/maps/src/lib/database.test.ts`: `getCharacterByKey('character:fixture enemy twin')`
  returns that key and `getCharacterByKey('character:nope')` returns null.
  `getCharactersByHomePosition('StowawayPortal', [40, 0, 60])` returns
  `character:fixture enemy twin` with its `npcName`, and a position five units
  away returns `[]`. `getCharactersByName('Runtime Enemy Internal')` finds
  `character:runtime enemy` while `getCharactersByName('Runtime Enemy')`, the
  curated name the game never sends, finds nothing. Without that last assertion
  nothing distinguishes the two columns.
- `src/mods/InteractiveMapCompanion/tests/InteractiveMapCompanion.Tests/Protocol/MessageSerializerTests.cs`:
  an `EntityData` carrying both new values serialises them as `characterKey` and
  `homePosition`, and one carrying neither emits neither key. This is the only
  mod-side unit coverage available, because `CharacterIdentity` reads live Unity
  components and the test project has no Unity host.

**End to end, in game.** Braxonian Desert carries both manual checks.

1. `uv run erenshor mod deploy --mod interactive-map-companion --loader bepinex`
2. Travel to Braxonian Desert. Two characters named `Molorai Archaeologist` spawn
   there, `character:molorai archaelogist` with 11 drops and
   `character:molorai archaelogist 1` with 12, so today's popup shows a merged
   list. Four exist game-wide across Braxonian and Duskenlight, which is why the
   note reads "2" here rather than "4".
3. Click one and expect a single list of 11 or 12 items with plain percentages
   and no shared-name note, where the same click previously showed ranges.
4. Confirm identity is flowing rather than tier three coincidentally producing one
   candidate: inspect a `stateUpdate` frame in devtools and check the entity
   carries `"characterKey": "character:molorai archaelogist"` or
   `"character:molorai archaelogist 1"`. The asset misspells "archaelogist", and
   the key mirroring that misspelling is a useful signal the value came from the
   prefab rather than the display name.
5. Click `Assassin of Sivakaya`, which the site calls `Reaver of Sivakaya`, and
   confirm a drop list appears where it was previously empty. Find the other
   curated-name candidates with
   `sqlite3 variants/main/erenshor-main.sqlite "SELECT stable_key, display_name, npc_name FROM characters WHERE display_name <> npc_name"`.

**Old-mod regression.** With a mod build predating this change installed, the
popup must keep working through tier three with its merged list, ranges, note,
and a protocol-mismatch warning. Nothing may throw and the drop list may not be
empty.

**Lunaris artifact.** The in-game check runs under BepInEx. Confirm the Vault
build at least compiles, and repeat the Braxonian check under Lunaris with
`uv run erenshor mod deploy --mod interactive-map-companion --loader lunaris` if
an install is available. If it is not, say so when reporting rather than implying
both loaders were exercised.

## Assumptions and contingencies

- `NextSpawn` holds the prefab of the currently live NPC. It is assigned
  immediately before instantiation in `SpawnPoint.SpawnNPC` and not cleared. If
  in-game testing shows a wrong key on spawn points with both `CommonSpawns` and
  `RareSpawns` populated, switch to a Harmony postfix on `SpawnPoint.SpawnNPC`
  recording instance ID to prefab name in a static dictionary and read that
  instead. Do not infer the prefab from the NPC's stats.
- Not every character the overlay shows exists in the clean database. Summoned
  creatures and event spawns may not, which is why tier one verifies existence
  before committing to a key and why tier three stays.
- Bumping the protocol version makes every current 0.2.0 mod log a warning on
  connect. That is accurate and non-fatal. If it proves noisy, soften the message
  rather than reverting the bump, because the payload genuinely changed.
- Home-position resolution serves 9 characters. If it proves unreliable in game,
  for example because `HomePos` is recorded after a character has moved, drop
  that tier and let those 9 fall to tier three. The prefab path covers the other
  43 and is the load-bearing half.
- Matching on `npc_name` assumes the mod keeps sending `Stats.MyName`, assigned
  from `NPCName` at `NPC.cs:518`. If a future build stops populating it and names
  arrive empty, read `NPC.NPCName` directly in the extractor rather than
  reverting to `display_name`, which is a curated value the game never sends.
