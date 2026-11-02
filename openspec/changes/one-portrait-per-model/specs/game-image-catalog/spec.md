# Spec Delta

## MODIFIED Requirements

### Requirement: Wiki picture titles are unambiguous

A build SHALL fail when one title names two different pictures, and name both entities. Before approved render lookup, it SHALL also reject a character render title covering multiple exported model keys unless a valid reviewed same-look declaration covers their exact membership. This check SHALL include characters without pictures, pages, or publication visibility and SHALL compare final normalized wiki titles.

#### Scenario: An item render and a character render share a title

- **WHEN** an item with an approved render and a character with an approved render have the same image name, and their renders differ
- **THEN** the build fails and names both

#### Scenario: One character kind covers different models

- **WHEN** two characters with the same display name and image name have different model keys and no reviewed same-look declaration
- **THEN** the clean build fails before looking up approved renders
- **AND** the error lists the final render title, member stable keys, model keys, and affected pages

#### Scenario: No approved portrait exists yet

- **WHEN** a shared title covers different model keys without a same-look declaration and none has an approved capture
- **THEN** the clean build still fails

#### Scenario: A collision crosses page and visibility boundaries

- **WHEN** characters on different pages, unused characters, or characters with no page resolve to one render title with different unmarked model keys
- **THEN** the clean build reports every conflicting member

#### Scenario: Image names normalize to one title

- **WHEN** different image names normalize to the same wiki render title and cover unmarked different model keys
- **THEN** the build rejects the title instead of treating the image names as separate subjects

## ADDED Requirements

### Requirement: Same-look declarations bind reviewed model membership

Different model keys SHALL share a character portrait subject only through an explicit same-look declaration naming the covered characters, expected model keys, capture representative, reason, and visual review evidence. A declaration SHALL fail validation when a member or expected model changes, membership is incomplete or overlapping, its representative is outside the group, or its review evidence is absent.

#### Scenario: Asset identities differ but reviewed models look the same

- **WHEN** a review compares every model key in a declaration and accepts them as one look
- **THEN** those exact members can share one subject and representative capture
- **AND** their source model keys remain available for inspection

#### Scenario: A game update changes a member's model

- **WHEN** a declared member has a model key different from the one reviewed
- **THEN** the clean build fails and requires a new review or separate subject

#### Scenario: A new member joins a shared title

- **WHEN** a title gains a character not covered by its declaration
- **THEN** a different model key is not accepted by inheritance or by transitive same-look membership

### Requirement: Portrait consumers preserve each character look

Every character SHALL resolve to its own approved look's portrait, not another model's portrait chosen by name, article, or deduplication representative. Wiki output SHALL retain the association between portrait titles and character members. The map SHALL retain the association between portrait pixel hashes and spawn members. Several looks on one article or in one search result SHALL remain available without changing gameplay facts.

#### Scenario: A character name has two looks

- **WHEN** two same-named character members have separately approved looks
- **THEN** wiki output associates each render title with the members it depicts
- **AND** each map spawn alternative selects its own member's portrait hash

#### Scenario: Gameplay-identical members look different

- **WHEN** characters have equal names, statistics, and loot but different resolved looks
- **THEN** portrait selection does not collapse them to one representative look
- **AND** the combined spawn probabilities, loot, and article identities stay unchanged

#### Scenario: Distinct subjects have equal pixels

- **WHEN** separate character subjects have approved renders with equal decoded pixels
- **THEN** they retain their own titles and member associations while sharing one catalog picture
