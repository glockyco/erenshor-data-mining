# Erenshor 0.8 data changes

Compared main 0.7 (build 24405256) with playtest 0.8 (build 26769622). The row diff is at `output/0.8/main-vs-playtest.md`. It reports changes in 87 of 136 tables. This review uses the clean SQLite databases for consumer-facing values, the raw databases to check export evidence, and [the script review](script-changes.md) for runtime bindings that the clean data does not represent. Item comparisons use the persistent game item `id` when resource-derived keys differ. Character comparisons account for the seven known replacements listed below. Picture tables are out of scope because the playtest does not have the publication picture catalog. The playtest's 103 `skill_classes` rows replace main's per-class skill columns and are not 103 new skills.

## 1. New content

### Zone and class

- `zone:glowmere`, Glowmere Grotto, is the only new zone. The clean graph has zone lines from Soluna's Landing and Malaroth's Nesting Grounds to the dungeon and return lines to both zones. It does not model the spoken wall passage separately.
- `Bard`, Bard, is the seventh playable class. Nine starter items are recorded: bread, water, tattered leggings, a rusty dagger, Worn Lute, Simple Song's skill book, the Sonic Assault and Unsetting Sustain scrolls, and A Guide To Songwriting. Bard class eligibility was also added to 546 items that already existed.
- `zone:ripper`, Ripper's Keep, is rebuilt, not a new zone. The guard's entry quest, indoor NPCs and vendor copies are new. The key-operated gate, ritual portal and portal spell are distinct routes. The portal spell's landing changed from `(572, 54.4, 293)` to `(561.04, 55, 407)`. The ritual route to `zone:ripperportal` still requires The Ripper Ritual and is tier 12 in both builds.

### Quests and givers

| Zone | Quest | Stable key | Giver or turn-in | Reward |
| --- | --- | --- | --- | --- |
| Fernalla's Revival Plains | Find The Watcher | `quest:meetwillowwatcher` | Vaeia Sevust (`character:vaeia sevust`) starts it on `protects`. Watcher (`character:watcher`) completes it in Willowwatch Ridge. | 300 XP |
| Hidden Hills | Old Bonepits Songbook | `quest:oldsongbook` | Brandon Uree (`character:brandon uree`) starts it and takes one Old Song Book. | 5 XP and Merosavillan Lute |
| Ripper's Keep | A Key to Ripper's Keep | `quest:ripperkey` (`RIPPERKEY`) | Ripper Gate Guard (`character:ripper gate guard`) starts it on `killed` and takes one Sivakayan Ore. | 35 XP and Ripper's Gate Key |
| Ripper's Keep, then Port Azure | The Captive Artisan | `quest:captiveartisan` | No assignment dialog. Captive Artisan drops Artisinal Bag and Elysia Thistlewick (`character:shady merchant`) takes it. | 250 XP and Statue: The Living Bard |
| Ripper's Keep | The Captive Artisan (Ripper) | `quest:captiveartisan1` | No assignment dialog. Captive Artisan drops Artisinal Bag and Phoebe Thistlewick (`character:shady merchant:1`) takes it. | 250 XP and Artisinal Bag back |

Find The Watcher is the only new quest with a giver in Fernalla's Revival Plains in this build. Watcher and Willow Seeds (`quest:willowseed`) already existed.

### Characters and vendors by zone

The clean data adds 53 character keys. Seven replace existing keys (listed in section 2). Four of the remaining 46 have no recorded placement. New placements under existing titles, such as Baking Oven, do not imply new wiki pages.

| Zone or placement | Display name | Stable key | Vendor role |
| --- | --- | --- | --- |
| Braxonian Desert | Minstrel of Sivakaya | `character:bard of sivakaya` |  |
| Faerie's Brake | Azure Guard | `character:azure brake guard 1` |  |
| Faerie's Brake | Faerie Guard | `character:faerie guard` |  |
| Fernalla's Revival Plains | Vaeia Sevust | `character:vaeia sevust` |  |
| Glowmere Grotto | Bilgerat's Remains | `character:bilgerat` |  |
| Glowmere Grotto | Ghostly Buccaneer | `character:buccaneer ghost 1` |  |
| Glowmere Grotto | Ghostly Cannoneer | `character:ghostly cannoneer` |  |
| Glowmere Grotto | Ghostly Captain | `character:ghostly captain` |  |
| Glowmere Grotto | Ghostly Oracle | `character:ghostly oracle` |  |
| Glowmere Grotto | Martin the Shipwright | `character:martin` |  |
| Glowmere Grotto | Skeletal Buccaneer | `character:buccaneer skeleton` |  |
| Glowmere Grotto | Skeletal Cutthroat | `character:skeletal cutthroat` |  |
| Glowmere Grotto, Malaroth's Nesting Grounds | Skeletal Pirate | `character:pirate skeleton` |  |
| Port Azure | Spark Hatchling | `character:spark beetle hatchling` |  |
| Ripper's Keep | Alexandra Jules | `character:alexandra jules` | Windblade |
| Ripper's Keep | Baking Oven | `character:baking oven (1):ripper:670.86:62.09:431.81` |  |
| Ripper's Keep | Baking Oven | `character:baking oven (2):ripper:669.68:62.09:433.11` |  |
| Ripper's Keep | Baking Oven | `character:baking oven:ripper:668.49:62.09:434.40` |  |
| Ripper's Keep | Captive Artisan | `character:captive artisan` |  |
| Ripper's Keep | Cara L'roft | `character:cara lroft` | Stormcaller |
| Ripper's Keep | Daniel Cappo | `character:citizen:ripper:535.23:52.19:337.25` |  |
| Ripper's Keep | Elise Cappo | `character:citizen (1):ripper:537.45:52.19:338.88` |  |
| Ripper's Keep | Evrett Ilsha | `character:dockhand nelson 1:ripper:570.01:52.19:409.88` |  |
| Ripper's Keep | Gravlo Posser | `character:gravlo posser 1` | Paladin |
| Ripper's Keep | Lasterio Frostwave | `character:lasterio frostwave` | Arcanist |
| Ripper's Keep | Phoebe Thistlewick | `character:shady merchant:1` | Oddities |
| Ripper's Keep | Rasterle Raris | `character:rasterle raris:ripper:646.35:52.25:337.51` | Reaver |
| Ripper's Keep | Ripparian Priest | `character:ripparian priest:ripper:627.30:62.09:383.16` |  |
| Ripper's Keep | Ripper Gate Guard | `character:ripper gate guard` |  |
| Ripper's Keep | Robert Fischer | `character:robert fischler:ripper:648.70:52.19:340.59` | Reaver |
| Ripper's Keep | Soot | `character:soot` |  |
| Ripper's Keep | Training Dummy | `character:dpsdummy:ripper:671.81:61.54:451.97` |  |
| Ripper's Keep | Vermic Vineweaver | `character:vermic vineweaver:1` | Druid |
| Vitheo's Plane of Valor | Angry Accompanist | `character:accompanist dissonant` |  |
| Vitheo's Plane of Valor | Hypnotic Accompanist | `character:accompanist hypnotic` |  |
| Vitheo's Plane of Valor | Melancholy Accompanist | `character:accompanist melancholy` |  |
| Vitheo's Plane of Valor | Revitalizing Accompanist | `character:accompanist revitalizing` |  |
| Vitheo's Plane of Valor | The Skald | `character:skald` |  |
| No recorded placement | Ghostly Cannoneer | `character:ghostly swashbuckler` |  |
| No recorded placement | Gravlo Posser | `character:gravlo posser` |  |
| No recorded placement | Training Dummy | `character:dpsdummy` |  |
| No recorded placement | Vermic Vineweaver | `character:vermic vineweaver` |  |

The level 42 raid boss in Vitheo's Plane of Valor (`zone:planeofvitheo`) is The Skald, not Minstrel of Sivakaya. `RaidSkaldEvent` ties the four accompanist spawn points to The Skald being alive. The plane's entry route still has progression tier 37. The clean graph shows The Skald and his accompanists at that tier without their encounter dependency, and the clean encounter tier labels The Skald an enemy.

The six Bard vendors are:

| Zone | Vendor | Stable key | Distinct stock items |
| --- | --- | --- | --- |
| Hidden Hills | Brandon Uree | `character:brandon uree` | 15 |
| Loomingwood Forest | Emjae Keenan | `character:mj keenan` | 21 |
| Port Azure | Joan Jetty | `character:joan jetty` | 31 |
| Ripper's Keep | Halzee Frange | `character:halzee` | 30 |
| Stowaway's Step | Davidson Malarky | `character:davidson malarky` | 20 |
| Willowwatch Ridge | Spiro Calsatto | `character:spiro calsatto` | 21 |

Davidson and Spiro are existing characters who became vendors. The other four are new characters. The table counts distinct items, not repeated slots. Oscar VanEllis is a re-keyed existing General vendor in Ripper's Keep, not a seventh Bard vendor.

### Items by kind

There are 117 new item identities. The 84 resource re-keys are separate. Astra, Rogue of the Stars drops the new level 40 Bard weapon Melisma, The First Muse. The new furniture turns up in all eight room slots and all four statue positions in `planning_table_furnishings`.

#### Bard armor

| Item | Stable key |
| --- | --- |
| Cadenced Silk Boots | `item:foot - 42 - cadenced silk boots` |
| Cadenced Silk Gloves | `item:glove - 42 - cadenced silk gloves` |
| Cadenced Silk Hat | `item:head - 42 - cadenced silk hat` |
| Cadenced Silk Sleeves | `item:arm - 42 - cadenced silk sleeves` |
| Cadenced Silk Tunic | `item:chest - 42 - cadenced silk tunic` |
| Cadenced Silk Wrap | `item:leg - 42 - cadenced silk wrap` |
| Cadenced Silk Wristlet | `item:wrist - 42 - cadenced silk wristlet` |

#### Bard weapons

| Item | Stable key |
| --- | --- |
| Derision | `item:weap - 44 - derision` |
| Melisma, The First Muse | `item:weap - 40 - muse` |
| Ovation | `item:weap - 44 - ovation` |

#### Instruments

| Item | Stable key |
| --- | --- |
| Azynthian Lute | `item:music - 33 - azynthian lute` |
| Braxonian Lute | `item:music - 28 - braxonian lute` |
| Campfire Lute | `item:music - 3 - campfire lute` |
| Fernallan Lute | `item:music - 24 - fernallan lute` |
| Madman's Lute | `item:music - 18 - madman's lute` |
| Merosavillan Lute | `item:music - 10 - merosavillan lute` |
| Molorai Lute | `item:music - 12 - molorai lute` |
| Painted Lute | `item:music - 44 - painted lute` |
| Prisoner's Lute | `item:music - 16 - prisoner's lute` |
| Screeching Lute | `item:music - 43 - screeching lute` |
| Shivering Lute | `item:music - 24 - shivering lute` |
| Sivakayan Lute | `item:music - 24 - sivakayan lute` |
| Waking Lute | `item:music - 33 - waking lute` |
| Worn Lute | `item:music - 1 - basic lute` |

#### Bard aura items

| Item | Stable key |
| --- | --- |
| Charismatic Presence | `item:aura - bard 2` |
| Inspiring Presence | `item:aura - bard 1` |
| Magnificent Presence | `item:aura - bard 3` |
| Radiant Presence | `item:aura - bard 4` |
| Transcendent Presence | `item:aura - bard 5` |

#### Skill books

| Item | Stable key |
| --- | --- |
| Skill Book: Caesura | `item:skillbook - caesura` |
| Skill Book: Chant of Battle | `item:skillbook - dissonant song` |
| Skill Book: Cheap Shot | `item:skillbook - cheap shot` |
| Skill Book: Comfort Song | `item:skillbook - comfortsong` |
| Skill Book: Elrehon's Cacophony | `item:skillbook - elrehon's cacophony` |
| Skill Book: Entrainment | `item:skillbook - entrainment` |
| Skill Book: Hum | `item:skillbook - hum` |
| Skill Book: Interlude of Faith | `item:skillbook - harmonic song` |
| Skill Book: Medley | `item:skillbook - medely` |
| Skill Book: Simple Song | `item:skillbook - simple song` |
| Skill Book: Tavern Song | `item:skillbook - tavern song` |

#### Furniture and book

| Item | Stable key |
| --- | --- |
| A Guide To Songwriting | `item:book - songwriting` |
| Statue: The Living Bard | `item:furniture - living bard statue` |

#### Quest and access items

| Item | Stable key |
| --- | --- |
| Artisinal Bag | `item:gen - artisinal bag` |
| Old Song Book | `item:gen - old song book` |
| Pirate Musings | `item:gen - bellwain note` |
| Pirate's Ledger | `item:gen - pirate's ledger` |
| Ripper's Gate Key | `item:key - ripper's gate key` |
| Thistlewick Key | `item:key - thistlewick key` |

#### Other equipment

| Item | Stable key |
| --- | --- |
| Bearskin Boots | `item:foot - 36 - bearpaw boots` |
| Bearskin Cape | `item:back - 30 - bearskin cloak` |
| Bilgerat's Stranglers | `item:glove - 28 - bilgerat's stranglers` |
| Captain's Dinner Jacket | `item:chest - 32 - captain's dinnercoat` |
| Deckworn Shoes | `item:foot - 30 - deckworn shoes` |
| Immaculate Ursine Tunic | `item:chest - 35 - immaculate ursine coat` |
| Oracle Wand | `item:wand - 29 - oracle's wand` |
| Patinated Bangle | `item:arm - 28 - patinated bangle` |
| Shipwright's Sledge | `item:weap - 30 - shipwright's sledge` |
| Skallywag's Hanger | `item:weap - 31 - scallywag's hanger` |
| Swordstruck Ring | `item:ring - 28 - swordstruck ring` |

#### Song scrolls, chords and notes

These 58 item rows teach the listed spells. When the scroll display-name column is empty, it shares the spell's display name. The paired stable keys are authoritative even when the labels disagree. There are 49 identical display-name pairs, but none shares a clean `wiki_page_name` with its taught spell. For example, `item:song scroll - chord channeling major` has the wiki title "Chord: Channeling Major (Item)".

| Spell display name | Spell stable key | Scroll stable key | Scroll display name if different |
| --- | --- | --- | --- |
| Chord Healing Phrygian | `spell:bard - note healing phrygian` | `item:song scroll - note healing phrygian` | Chord: Healing Phrygian |
| Chord: Channeling Major | `spell:bard - chord channeling major` | `item:song scroll - chord channeling major` |  |
| Chord: Channeling Minor | `spell:bard - chord channeling minor` | `item:song scroll - chord channeling minor` |  |
| Chord: Clarifying Pizzicato | `spell:bard - chord clarifying pizzicato` | `item:song scroll - chord clarifying pizzicato` |  |
| Chord: Decrescendo | `spell:bard - chord decrescendo` | `item:song scroll - chord decrescendo` | Note: Decrescendo |
| Chord: Elemental Harmony | `spell:bard - chord elemental harmony` | `item:song scroll - chord harmony elemental` |  |
| Chord: Enthusiasm | `spell:bard - chord enthusiasm` | `item:song scroll - chord enthusiasm` |  |
| Chord: Flowing Apreggio | `spell:bard - chord flowing appregio` | `item:song scroll - chord flowing appregio` | Note: Flowing Apreggio |
| Chord: Healing Aeolian | `spell:bard - note healing aeolian` | `item:song scroll - note healing aeolian` |  |
| Chord: Healing Dorian | `spell:bard - note healing dorian` | `item:song scroll - note healing dorian` |  |
| Chord: Healing Ionian | `spell:bard - note healing ionian` | `item:song scroll - note healing ionian` |  |
| Chord: Healing Lydian | `spell:bard - note healing lydian` | `item:song scroll - note healing lydian` |  |
| Chord: Healing Mixolydian | `spell:bard - note healing mixolydian` | `item:song scroll - note healing mixolydian` | Chord: Healing Mixloydian |
| Chord: Insisting Legato | `spell:bard - chord insisting legato` | `item:song scroll - chord insisting legato` |  |
| Chord: Inspiring Melody | `spell:bard - chord inspiring melody` | `item:song scroll - chord inspiring melody` |  |
| Chord: Invigorate | `spell:bard - chord invigorate` | `item:song scroll - chord invigorate` | Chord: Invigorating Minor |
| Chord: Magical Harmony | `spell:bard - chord magical harmony` | `item:song scroll - chord harmony magical` |  |
| Chord: Meditative Minor | `spell:bard - chord meditative` | `item:song scroll - chord meditative` |  |
| Chord: Narcoleptic | `spell:bard - chord narcoleptic` | `item:song scroll - chord narcoleptic` |  |
| Chord: Percussive Eighth | `spell:bard - chord percussive eighth` | `item:song scroll - chord percussive eighth` |  |
| Chord: Percussive Half | `spell:bard - chord percussive half` | `item:song scroll - chord percussive half` |  |
| Chord: Percussive Three Quarter | `spell:bard - chord percussive third` | `item:song scroll - chord percussive three-quarter 1` |  |
| Chord: Percussive Whole | `spell:bard - chord percussive whole` | `item:song scroll - chord percussive whole` |  |
| Chord: Power Chord | `spell:bard - chord power chord` | `item:song scroll - chord power chord` |  |
| Chord: Rapid Thoughts | `spell:bard - chord rapid thoughts` | `item:song scroll - chord rapid thoughts` |  |
| Chord: Refreshing Finale | `spell:bard - chord refreshing finale` | `item:song scroll - chord refreshing finale` |  |
| Chord: Resonating Minor | `spell:bard - chord resonating minor` | `item:song scroll - note resonating minor` | Note: Resonating Minor |
| Chord: Restful | `spell:bard - chord restful chord` | `item:song scroll - chord restful` |  |
| Chord: Slumber | `spell:bard - chord slumber chord` | `item:song scroll - chord slumber` |  |
| Chord: Sonic Coda | `spell:bard - chord sonic coda` | `item:song scroll - chord sonic coda` |  |
| Chord: Sonic Dirge | `spell:bard - chord sonic dirge` | `item:song scroll - chord sonic dirge` |  |
| Chord: Sonic Overature | `spell:bard - chord sonic overature` | `item:song scroll - chord sonic overature` |  |
| Chord: Sonic Rhapsody | `spell:bard - chord sonic rhapsody` | `item:song scroll - chord sonic rhapsody` |  |
| Chord: Sonic Wave | `spell:bard - chord sonic wave` | `item:song scroll - chord sonic assault` | Chord: Sonic Assault |
| Chord: Surging Legato | `spell:bard - chord surging legato` | `item:song scroll - chord surging legato` |  |
| Chord: Swinging Legato | `spell:bard - chord swinging legato` | `item:song scroll - chord swinging legato` |  |
| Chord: Trance | `spell:bard - chord trance` | `item:song scroll - chord trance` |  |
| Chord: Venomous Harmony | `spell:bard - chord venomous harmony` | `item:song scroll - chord harmony poison` |  |
| Chord: Void Harmony | `spell:bard - chord void harmony` | `item:song scroll - chord harmony void` |  |
| Note: Assaulting Pitch | `spell:bard - note assaulting pitch` | `item:song scroll - note assaulting pitch` |  |
| Note: Binding Second | `spell:bard - note binding second` | `item:song scroll - note binding second` |  |
| Note: Crippling Second | `spell:bard - note crippling second` | `item:song scroll - note crippling second` |  |
| Note: Dissonant Major | `spell:bard - note dissonant major` | `item:song scroll - note dissonant major` |  |
| Note: Dissonant Minor | `spell:bard - note dissonant minor` | `item:song scroll - note dissonant minor` |  |
| Note: Ethereal Bend | `spell:bard - note ethereal bend` | `item:song scroll - note ethereal bend` |  |
| Note: Ethereal Sharp | `spell:bard - note ethereal sharp` | `item:song scroll - note ethereal sharp` |  |
| Note: Fatal Pitch | `spell:bard - note fatal pitch` | `item:song scroll - note fatal pitch` |  |
| Note: Harmonic Major | `spell:bard - note harmonic major` | `item:song scroll - note harmonic major` |  |
| Note: Harmonic Minor | `spell:bard - note harmonic minor` | `item:song scroll - note harmonic minor` |  |
| Note: Hypnotic Beat | `spell:bard - note hypnotic beat` | `item:song scroll - note hypnotic beat` |  |
| Note: Lullaby Fourth | `spell:bard - note lullaby fourth` | `item:song scroll - note lullaby fourth` |  |
| Note: Penetrating Hammer-On | `spell:bard - note penetrating hammer-on` | `item:song scroll - note penetrating hammer-on` | Note: Penetrating Hammer-on |
| Note: Penetrating Pull-Off | `spell:bard - note penetrating pull-off` | `item:song scroll - note penetrating pull-off` | Note: Penetrating Pull-off |
| Note: Piercing Sustain | `spell:bard - note piercing sustain` | `item:song scroll - note piercing sustain` |  |
| Note: Torturous Sustain | `spell:bard - note torturous sustain` | `item:song scroll - note torturous sustain` |  |
| Note: Unbearable Pitch | `spell:bard - note unbearable pitch` | `item:song scroll - note unbearable pitch` |  |
| Note: Undesirable Pitch | `spell:bard - note undesirable pitch` | `item:song scroll - note undesirable pitch` |  |
| Note: Unsetting Sustain | `spell:bard - note unsetting sustain` | `item:song scroll - note unsetting sustain` |  |

### Other spells and Bard skills

There are 67 new spell rows in total. The five aura spells and Note: Amplified Pain are Bard-themed but have no teaching scroll. Note: Amplified Pain is a level 33 song effect with no `spell_classes` row and no item that teaches it. Collision, Injury and Access Auction are not assigned to Bard or any other class.

| Spell | Stable key |
| --- | --- |
| Aura: Inspiring Presence | `spell:aura - bard 1` |
| Aura: Charismatic Presence | `spell:aura - bard 2` |
| Aura: Magnificent Presence | `spell:aura - bard 3` |
| Aura: Radiant Presence | `spell:aura - bard 4` |
| Aura: Transcendent Presence | `spell:aura - bard 5` |
| Note: Amplified Pain | `spell:bard - note amplified pain` |
| Collision | `spell:none - collision` |
| Injury | `spell:none - injury` |
| Access Auction | `spell:none - summon ledger` |

All 11 new skills have a Bard level, including seven active songs and Hum. The existing Backstab, Dodge through Dodge IV, Double Attack, Kick and Melee Proficiency also gain Bard class rows. Task 3.1 names Elrehon's Crescendo, but there is no skill or spell with that display name in this build. The level 35 song in the data is Elrehon's Cacophony.

| Skill | Stable key | Bard level |
| --- | --- | --- |
| Simple Song | `skill:song - simple song` | 1 |
| Comfort Song | `skill:song - comfort song` | 3 |
| Caesura | `skill:caesura` | 4 |
| Cheap Shot | `skill:cheap shot` | 4 |
| Tavern Song | `skill:song - tavern song` | 6 |
| Hum | `skill:song - hum` | 9 |
| Interlude of Faith | `skill:song - harmonicsong` | 12 |
| Entrainment | `skill:entrainment` | 14 |
| Chant of Battle | `skill:song - dissonantsong` | 16 |
| Medley | `skill:song - medely` | 25 |
| Elrehon's Cacophony | `skill:song - elrehonsong` | 35 |

The chessboard change is an encounter, not a new skill. No new skill or item is bound to `FacelessBard`. The existing piece The Faceless (`item:quest - game piece the faceless sivakayan`) now selects one of seven NPC outcomes, including the new Minstrel of Sivakaya. Clean `character_spawns` contains the seventh binding and `progression show` ties the Minstrel to the piece in Braxonian Desert.

### Ascensions and book

All five new ascensions are for Bard.

| Ascension | Stable key |
| --- | --- |
| Frisson | `ascension:brd - frisson` |
| Improved Entrainment | `ascension:brd - entrainment` |
| Resonance Power | `ascension:brd - resonance` |
| Shredding | `ascension:brd - shredding` |
| Volume Increase | `ascension:brd - dissonant volume` |

The new book is `Songwriting`, with page keys `0` through `12` under that title. Its book heading is "A Guide to Songwriting". The starter item is `item:book - songwriting`, with display name "A Guide To Songwriting".

## 2. Re-keyed, renamed and removed pages

### Same display name under a replacement key

Seven character keys disappeared, with the same titles still present. Five Ripper's Keep characters changed from coordinate-bearing keys to prefab keys. Peony Shalmo moved within Faerie's Brake. The Port Azure Training Dummy changed object name at the same coordinates. None of these changes needs a page move or a Historical Content notice.

| Display name | Main key | Playtest key |
| --- | --- | --- |
| Comstock Retalio | `character:comstock retalio:ripper:743.17:43.64:203.05` | `character:comstock retalio` |
| Dusty McPhenn | `character:dusty mcphen:ripper:731.98:43.64:169.43` | `character:dusty mcphen` |
| Goldie Retalio | `character:goldie retalio:ripper:752.67:43.64:203.27` | `character:goldie retalio` |
| Oscar VanEllis | `character:oscar vanellis:ripper:755.35:43.64:193.63` | `character:oscar vanellis` |
| Peony Shalmo | `character:peony shalmo:brake:112.58:16.21:183.08` | `character:peony shalmo:brake:294.85:26.41:552.27` |
| Training Dummy | `character:sm_prop_dummy_archery_01:azure:168.89:41.79:309.30` | `character:dpsdummy:azure:168.89:41.79:309.30` |
| Teodor Smart | `character:teodor smart:ripper:691.18:43.64:182.00` | `character:teodor smart` |

All 1,537 main item IDs still exist. The variant diff's 84 removed item keys are resource renames, not item removals. Of those, 83 keep their display name and 75 move from required level 42 to levels 43 through 46. Orbital Loop's resource key changes from 42 to 43 without changing its actual item level. Pg. 7: Faded Entry changes its resource suffix from `abyssal` to `glowmere` without changing its title. The other cross-key title change is listed under redirects.

| Display name | Main key | Playtest key |
| --- | --- | --- |
| Lunar Bangle | `item:arm - 42 - lunar bangle` | `item:arm - 44 - lunar bangle` |
| Blizzard Bane | `item:back - 42 - blizzardbane` | `item:back - 43 - blizzardbane` |
| Cloak of Flame | `item:back - 42 - cloak of flame` | `item:back - 43 - cloak of flame` |
| Cloak of Frost | `item:back - 42 - cloak of frost` | `item:back - 43 - cloak of frost` |
| Abominable Ribcage | `item:back - 42 - ribcage` | `item:back - 44 - ribcage` |
| Secrets of Life | `item:back - 42 - secrets of life` | `item:back - 43 - secrets of life` |
| Shroud of Nature | `item:back - 42 - shroud of nature` | `item:back - 45 - shroud of nature` |
| Vithean Quiver | `item:back - 42 - vithean quiver` | `item:back - 44 - vithean quiver` |
| Wakeweaver | `item:back - 42 - wakeweaver` | `item:back - 45 - wakeweaver` |
| Beast Harness | `item:belt - 2 - beast harness` | `item:belt - 5 - beast harness` |
| Sableheart's Harness | `item:belt - 31 - sableheart's harness` | `item:belt - 38 - sableheart's harness` |
| Cord of Concentration | `item:belt - 42 - cord of concentration` | `item:belt - 43 - cord of concentration` |
| Ellipse Cord | `item:belt - 42 - ellipse cord` | `item:belt - 44 - ellipse cord` |
| Gem Encrusted Sash | `item:belt - 42 - gem encrusted girdle` | `item:belt - 44 - gem encrusted girdle` |
| Glacier Belt | `item:belt - 42 - glacier belt` | `item:belt - 44 - glacier belt` |
| Frostbite | `item:bow - 42 - frostbite` | `item:bow - 43 - frostbite` |
| Honsus' Bow | `item:bow - 42 - honsus' bow` | `item:bow - 44 - honsus' bow` |
| Imperium | `item:bow - 42 - imperium` | `item:bow - 45 - imperium` |
| Aegis Charm | `item:charm - 42 - aegis charm` | `item:charm - 43 - aegis charm` |
| Creator's Charm | `item:charm - 42 - creator's charm` | `item:charm - 43 - creator's charm` |
| Oceanic Charm | `item:charm - 42 - oceanic charm` | `item:charm - 44 - oceanic charm` |
| Ursine Charm | `item:charm - 42 - ursine charm` | `item:charm - 44 - ursine charm` |
| Amarionite Garb | `item:chest - 42 - amarionite garb` | `item:chest - 44 - amarionite garb` |
| Arachnid Carapace | `item:chest - 42 - arachnid carapace` | `item:chest - 44 - arachnid carapace` |
| Hunting Coat | `item:chest - 42 - hunting coat` | `item:chest - 45 - hunting coat` |
| Mana Strand Tunic | `item:chest - 42 - mana strand tunic` | `item:chest - 46 - mana strand tunic` |
| Trickster's Tunic | `item:chest - 42 - trickster's tunic` | `item:chest - 44 - trickster's tunic` |
| Meteor Metal Boots | `item:foot - 42 - meteor metal boots` | `item:foot - 44 - meteor metal boots` |
| Skittering Boots | `item:foot - 42 - skittering boots` | `item:foot - 44 - skittering boots` |
| Charred Boots | `item:foot - 5 - charred boots` | `item:foot - 4 - charred boots` |
| Pg. 7: Faded Entry | `item:gen - treasure hunter pg 7 (abyssal)` | `item:gen - treasure hunter pg 7 (glowmere)` |
| Gauntlets of Fiery Strength | `item:glove - 42 - gauntlets of fiery strength` | `item:glove - 43 - gauntlets of fiery strength` |
| Sea Shaper's Gloves | `item:glove - 42 - sea shaper's gloves` | `item:glove - 45 - sea shaper's gloves` |
| Mummy Wraps | `item:glove - 5 - mummy wraps` | `item:glove - 4 - mummy wraps` |
| Letters and Words | `item:hand - 42 - letters and words (common)` | `item:hand - 45 - letters and words (common)` |
| Letters and Words | `item:hand - 42 - letters and words (rare)` | `item:hand - 45 - letters and words (rare)` |
| Idol of Sivakaya | `item:hand - 5 - idol of sivakaya` | `item:hand - 4 - idol of sivakaya` |
| Fiery Thoughts | `item:head - 42 - fiery thoughts` | `item:head - 44 - fiery thoughts` |
| Helmet of Clarity | `item:head - 42 - helm of clarity` | `item:head - 43 - helm of clarity` |
| Moonlit Mask | `item:head - 42 - moonlit mask` | `item:head - 45 - moonlit mask` |
| Funeral Shroud | `item:head - 5 - funeral shroud` | `item:head - 4 - funeral shroud` |
| Astral March | `item:leg - 42 - astral march` | `item:leg - 45 - astral march` |
| Colorless Trousers | `item:leg - 42 - colorless trousers` | `item:leg - 44 - colorless trousers` |
| Aevum | `item:neck - 42 - aevum` | `item:neck - 45 - aevum` |
| Cosmic Barrier | `item:neck - 42 - cosmic barrier` | `item:neck - 43 - cosmic barrier` |
| Magma Droplet | `item:neck - 42 - magma droplet` | `item:neck - 43 - magma droplet` |
| Predator's Shard | `item:neck - 42 - predator's soulstone` | `item:neck - 43 - predator's soulstone` |
| Sibling's Locket | `item:neck - 42 - sibling's locket` | `item:neck - 44 - sibling's locket` |
| Tenet of Braxonia | `item:neck - 42 - tenet of braxonia` | `item:neck - 46 - tenet of braxonia` |
| Priel Insignia Ring | `item:ring - 4 - priel insignia ring` | `item:ring - 5 - priel insignia ring` |
| Gladiator's Coil | `item:ring - 42 - gladiator's coil` | `item:ring - 43 - gladiator's coil` |
| Halo of Twin Skies | `item:ring - 42 - halo of twin skies` | `item:ring - 43 - halo of twin skies` |
| Insistence | `item:ring - 42 - insistence` | `item:ring - 45 - insistence` |
| Orbital Loop | `item:ring - 42 - orbital loop` | `item:ring - 43 - orbital loop` |
| Reminder of Pride | `item:ring - 42 - reminder of pride` | `item:ring - 45 - reminder of pride` |
| Repellant Ring | `item:ring - 42 - repellant ring` | `item:ring - 44 - repellant ring` |
| Ring of Tidal Winds | `item:ring - 42 - ring of tidal winds` | `item:ring - 44 - ring of tidal winds` |
| Cometshard Shield | `item:secondary - 42 - cometshard shield` | `item:secondary - 44 - cometshard shield` |
| Sea Wind Shield | `item:secondary - 42 - sea wind shield` | `item:secondary - 44 - sea wind shield` |
| Shard of Infinity | `item:secondary - 42 - shard of infinity` | `item:secondary - 46 - shard of infinity` |
| Treant Eye Shield | `item:secondary - 42 - treant eye shield` | `item:secondary - 43 - treant eye shield` |
| Fernalla's Paintbrush | `item:wand - 42 - fernalla's paintbrush` | `item:wand - 44 - fernalla's paintbrush` |
| Flaming Staff | `item:wand - 42 - flaming staff` | `item:wand - 43 - flaming staff` |
| Warder's Staff | `item:wand - 42 - staff of the warder` | `item:wand - 43 - staff of the warder` |
| Advisor's Sword | `item:weap - 42 - advisor's sword` | `item:weap - 43 - advisor's sword` |
| Blade of Grace | `item:weap - 42 - blade of grace` | `item:weap - 43 - blade of grace` |
| Cycle's Edge | `item:weap - 42 - cycle's edge` | `item:weap - 45 - cycle's edge` |
| Elemental Fourblade | `item:weap - 42 - elemental four-blade` | `item:weap - 44 - elemental four-blade` |
| Gladiator's Axe | `item:weap - 42 - gladiator's axe` | `item:weap - 43 - gladiator's axe` |
| King's Gambit | `item:weap - 42 - king's gambit` | `item:weap - 44 - king's gambit` |
| Moonmaker | `item:weap - 42 - moonmaker` | `item:weap - 43 - moonmaker` |
| Obsidian Edge | `item:weap - 42 - obsidian edge` | `item:weap - 43 - obsidian edge` |
| Planar Spear | `item:weap - 42 - planar ice lance` | `item:weap - 43 - planar ice lance` |
| Spear of True North | `item:weap - 42 - spear of true north` | `item:weap - 45 - spear of true north` |
| Shifted Fate | `item:weap - 42 - sword of shifted fate` | `item:weap - 45 - sword of shifted fate` |
| Willowcutter | `item:weap - 42 - willowcutter` | `item:weap - 43 - willowcutter` |
| Bracer of Seeds | `item:wrist - 42 - bracer of seeds` | `item:wrist - 45 - bracer of seeds` |
| Bracer of the Blessed | `item:wrist - 42 - bracer of the blessed` | `item:wrist - 43 - bracer of the blessed` |
| Cleansing Brace | `item:wrist - 42 - cleansing brace` | `item:wrist - 43 - cleansing brace` |
| Frozen Grip | `item:wrist - 42 - frozen grip` | `item:wrist - 43 - frozen grip` |
| Mana Strand Bracer | `item:wrist - 42 - mana strand bracer` | `item:wrist - 46 - mana strand bracer` |
| Allbond | `item:wrist - 42 - the allbond` | `item:wrist - 46 - the allbond` |
| Thornwood Bracer | `item:wrist - 42 - thornwood bracer` | `item:wrist - 43 - thornwood bracer` |

### Display name changed

Move these pages and leave redirects after publication approval. The first two keep their stable key. The item keeps its in-game ID but changes both key and page title.

| Old title | New title | Identity |
| --- | --- | --- |
| A Faerie Drone | Faerie Drone | `character:faerie drone` |
| Lifeflame Brazier | Life Flame Brazier | `character:sm_prop_brazier_01:vitheosend:246.80:0.52:101.17` |
| Creeping Waistband | Observer's Waistband | Item ID `42273351`. `item:belt - 42 - creeping waistband` becomes `item:belt - 44 - creeping waistband`. |

### Truly gone

No character, quest, item, spell, skill or zone page in this comparison needs a Historical Content notice. The character and item keys that disappeared all have identifiable replacements. No quest, spell, skill or zone keys disappeared, and none of those four types changed an existing title.

## 3. Balance and source changes

### Item stats

- Of 1,537 continuing items matched by ID, 121 change a Standard-quality stat. All 121 gain Charisma and none loses it. Hunting Coat goes from 0 to 45, Secrets of Life from 0 to 35, Gem Encrusted Sash from 0 to 25, and Sivakayan Tricorner from 5 to 30.
- Two of those items trade away other stats. Coiling Belt goes from 10 to 8 in Strength, Endurance and Dexterity. Prismatic Warcord goes from 5 to 4 in Strength, Dexterity and Agility. No other Standard-quality stat changes on continuing items. Separately, 92 items change their actual item level, including 10 with unchanged stable keys.
- Harmony and dissonance are new fields. Of the new items, 19 have nonzero harmony and 85 have nonzero dissonance, including scrolls. Neither field is nonzero on any continuing item. On equipment, Worn Lute has 0.02 for each and Ovation has 0.30 harmony and 0.10 dissonance.
- The Charisma proficiency label changes from "Mind" to "Persuasion" in `CalcStats.MouseOverCha` and `ItemInfoWindow.DisplayItem`. Its data fields remain `cha`, `cha_scaling` and the existing Charisma-related class fields. This is a label change, not another item stat.

### Spell damage

Four continuing spells change `target_damage`, all Arcanist spells and all increases: Brax's Wrath 7,500 to 7,850, Ice Meteor 5,500 to 6,000, Sunburst 1,500 to 1,700, and Tenebris 4,500 to 4,800. These are asset base values. They do not include changes in combat formulas, including the separate wand damage-roll change in [the script review](script-changes.md#combat-attributes-and-status-effects).

### Vendor stock

Base stock goes from 668 to 911 slot rows. Counting distinct character and item pairs and matching the re-keyed characters and item IDs, there are 240 additions and no removals. The Bard network accounts for 138 of those additions. The number of character keys with base stock is 83 on main and 97 on playtest after replacing the old keys. Davidson Malarky now stocks Worn Lute, Tavern Song and Caesura skill books, and Bard scrolls. Halzee Frange and Joan Jetty stock Charismatic Presence. Alexandria Fadden and Amanda Rostley are existing vendors who add Inspiring Presence. Ripper's Keep's new non-Bard vendors account for the other 100 distinct additions.

### Loot and drop rates

`loot_drops` grows from 6,353 to 6,654 character and item pairs. After matching the character replacements and item IDs, 302 pairs are added and one is removed. Across the 6,352 continuing pairs, modeled per-kill probability changes for 316, with 34 increases and 282 decreases. These 316 are configured outcomes, not fixed `is_actual` drops. The separate `item_drops` table of item-to-item pools stays at 11 rows with no probability changes.

- The removed pair is Darkwarden Ealdred dropping Pg. 7: Faded Entry. Ghostly Captain in Glowmere Grotto now drops that same item ID at 100%. This is a source move, not an item retirement.
- Astra, Rogue of the Stars adds Melisma, The First Muse at 14.29%. The Skald's table gives Ovation, Painted Lute and Observer's Waistband at 33.33% each. Jinx's modeled chance for the renamed waistband falls from 68.94% to 6.83%. The raw loot rows agree with those values.
- The Vithean Chest (Round 2) entries for Gladiator's Axe and Gladiator's Coil both fall from 50% to 33.33%. A Skeleton Captain's modeled Ancient Bone chance rises from 89.61% to 93.54%. Skeleton Soldiers and Captains now have Old Song Book drops. One Soldier row is 2.96% and the Captain rows are 6.81%.

### Quest rewards and faction

- Comparing the 201 continuing quest resource variants by asset name, no XP, gold or reward item ID changes. The five new quest rewards are listed in section 1, all with zero gold. Flickering Souls (`Flickering Soul` resource) now has `kill_turn_in_holder = 1`, so Flicker of Souls dies on turn-in. That is a completion effect, not a reward change.
- The 22 faction definitions and continuing characters' faction assignments are unchanged. After matching the re-keyed characters, there are 71 additional character faction-modifier rows, 126 added hostility rows and 99 added alliance rows, with no removals in those sets. For example, The Skald adds +5 The Azure Guard and -2 The Children of Sivakaya on defeat, and is hostile to `Player` and allied to `OtherEvil` in the combat faction relations.
- The only three new quest faction rows belong to A Key to Ripper's Keep: -5 The Azure Guard, +1 The Citizens of Erenshor and +1 Ripper DeMerth.

## 4. New progression gaps

Ran `uv run erenshor -V main progression show --gaps` and `uv run erenshor -V playtest progression show --gaps`, then `progression show <key>` on each added gap. Main has 226 nodes without a tier, 219 without a way. Playtest has 231 without a tier, 224 without a way. No main gap drops out. Each of the five added nodes has zero recorded ways and no tier.

| Node | Why it has no recorded way |
| --- | --- |
| Training Dummy (`character:dpsdummy`) | This resource prefab has no recorded placement. The Port Azure and Ripper's Keep Training Dummy placements have their own keys. |
| Ghostly Cannoneer (`character:ghostly swashbuckler`) | This unplaced Ghostly Swashbuckler prefab shares a display name with the different, placed `character:ghostly cannoneer` in Glowmere Grotto. |
| Gravlo Posser (`character:gravlo posser`) | This resource copy has no recorded placement or stock. The reachable Paladin vendor in Ripper's Keep is `character:gravlo posser 1`. |
| Vermic Vineweaver (`character:vermic vineweaver`) | This resource copy has no recorded placement or stock. The reachable Druid vendor in Ripper's Keep is `character:vermic vineweaver:1`. |
| Transcendent Presence (`item:aura - bard 5`) | The item points to the level 35 Bard aura but has no `item_sources`, vendor or loot row, so the graph has no acquisition path. The data does not establish whether players should be able to acquire it in this build. |

## 5. Suspected pipeline bugs

- The Skald and his accompanists lack an encounter binding. `RaidSkaldEvent` links the four spawn points to The Skald, but their clean spawn rows have no protector or source script, and their graph ways require only the plane. The Skald is a boss in `knowledge_entries` but is typed `enemy` in `characters`. The raw `PlanarBosses` table covers the other planar boss lists but does not list The Skald. The raid-tier producer uses that table and arena rounds, so it misses this controller's boss.
- The new gates are under-modeled. Raw `SecretPassages` classifies Glowmere's `SayTrigger` as `InvisibleFloor` and has no binding to the wall or the `respite` keyword. The clean graph can reach the dungeon zone but cannot explain that passage. For Ripper's Keep, `doors` records Ripper's Gate Key on `door:ripper:542.11:62.57:291.40`, but the graph has no node for the gate and no way that expresses the key requirement. The ritual portal already has its quest condition and the direct spell route already has its moved landing.
- The graph includes the four unplaced character resource copies in section 4 even though separate copies carry the real placements. Review their grouping or eligibility before publishing them as encounterable entities. Do not infer that separate copies were removed or are inaccessible in-game from these graph rows alone.
- Several comparisons measure identity churn, not removals. Besides the replacement keys in section 2, the diff reports all 28 authored Sims, 93 equipment rows and 28 reference rows as replaced. The 28 Sim prefab paths and names are identical and all Sim keys include a Unity prefab GUID that changed across rips. Likewise, the knowledge compendium changes 852 of 892 rows when joined by position, but loses no distinct prefab path. Only four original distinct `(name, zone, level, boss flag, prefab path)` tuples are absent after dropping the position. Neither count supports a mass content removal.
- No broad gameplay NULL regression was found on common entity keys in characters, items, item stats, quests, quest variants, skills, spells or zones, excluding catalog-dependent image hashes. The only non-image non-null-to-null field in that check is Impact's self-proc reference. Both raw and clean spell rows lose it and its chance drops from 90 to 0, so it is an asset change rather than evidence of a clean-build loss.
