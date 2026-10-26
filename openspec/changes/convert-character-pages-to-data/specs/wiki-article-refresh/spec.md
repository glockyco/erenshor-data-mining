# Spec Delta

## MODIFIED Requirements

### Requirement: Preserved fields follow the entity

For generated legacy roots of unconverted types, every root SHALL carry the entity's stable key in `stablekey`. Generation SHALL match a live legacy root to a generated one by stable key.

#### Scenario: Entities change order

- **WHEN** the entities of a legacy generated page change order between two builds
- **THEN** each preserved field stays with its stable key

### Requirement: Unmatched live roots survive generation

A live root that matches no generated entity SHALL stay unchanged, and generation SHALL list it for review. Generation SHALL NOT delete it.

#### Scenario: A root that an editor added

- **WHEN** a live page holds a root that generation does not produce
- **THEN** the root stays unchanged and the page is listed for review

### Requirement: Unkeyed roots are paired by name and field agreement

A live legacy root without a key SHALL match a generated root with the same entity name. When several roots share a name, generation SHALL pair them so the most field values agree. Equally good pairings that give different pages SHALL fail generation for that page, name it, and list stable keys to add by hand. This matching SHALL NOT establish coordinate-key movement continuity.

#### Scenario: Variants that share a name

- **WHEN** before Character cutover a live page has two unkeyed Malignant Thoughts infoboxes and only the second one holds the coordinates of the second generated variant
- **THEN** each infobox merges with the variant whose values it holds, and the coordinates stay with their variant

#### Scenario: Same-name roots that no value tells apart

- **WHEN** two unkeyed legacy generated roots admit equally good pairings that preserve different editor fields
- **THEN** generation fails for that page and names the stable keys to add

### Requirement: Generated companions replace their matching live companions

A merged legacy root SHALL take the companion templates of its generated root, such as `ItemTooltip` or `SpellTooltip`. Generated companions SHALL replace that root's live companions even when prose or editor markup stands between root and companion.

#### Scenario: A tooltip in an editor's table

- **WHEN** an editor placed the legacy generated `Item/Charm` companion of a charm inside a table
- **THEN** the regenerated companion replaces it inside the table, and no second companion appears

### Requirement: Every generated entity takes current data

For unconverted generated types, generation SHALL merge current generated values into every generated root template on a live page, including `Stance`, under that template's preservation rules.

#### Scenario: A stance value changes

- **WHEN** a game update changes a stance modifier while that type still uses legacy generation
- **THEN** the regenerated stance page shows the new modifier

## ADDED Requirements

### Requirement: Converted characters preserve fields through proven identity continuity

After accepted Character data cutover, generated Character roots SHALL follow the `wiki-character-data` preservation and native ownership-proof requirements. Authored dedicated SimPlayer and other retained manual legacy Character calls SHALL remain untouched.

#### Scenario: Converted character order and movement

- **WHEN** converted Character roots change order or a coordinate-bearing key changes
- **THEN** editor fields remain bound to their stable identities, and a changed key transfers them only through a proven native-lineage replacement or explicit reviewed lifecycle operation

### Requirement: Converted characters refresh through data and guarded membership

After accepted Character data cutover, current facts SHALL reach pages through deployed data modules. Generation SHALL create compact Character stubs for new identities and reconcile existing pages only for identity membership changes, with coordinate-key replacements governed by native lineage proof. Unchanged membership SHALL leave article bytes unchanged. There SHALL be no full-article Character fallback generation mode after cutover.

#### Scenario: Character facts change without membership change

- **WHEN** an update changes Character stats, loot, spawn conditions or build identity but not article identity membership
- **THEN** data publication updates the render without rewriting the article, editor fields or prose

#### Scenario: Character key disappears without continuity proof

- **WHEN** converted membership contains an old key absent from current data and no accepted lineage or lifecycle disposition exists
- **THEN** reconciliation leaves the article unchanged, reports the unresolved case and does not silently append a replacement root
