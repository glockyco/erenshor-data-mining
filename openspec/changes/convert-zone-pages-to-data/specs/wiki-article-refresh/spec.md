# Spec Delta

## MODIFIED Requirements

### Requirement: Zone pages merge into the live page

Until the zone type completes its approved data-backed cutover, zone pages SHALL be generated from the fetched live page, like the other unconverted articles. The repository SHALL NOT hold a copy of a zone article. Each legacy Zone field other than title SHALL keep its live value when that value is not blank. A generated value SHALL fill only a blank field or a new page.

After the approved zone cutover and complete scene-group accounting, refresh SHALL create compact data-backed stubs for new zone pages and SHALL reconcile existing articles only for true article membership or lifecycle changes. Existing converted articles SHALL retain their exact source bytes when article membership is unchanged. Changes to facts or to a generated group under an existing valid anchor SHALL update data without rewriting the article. Reconciliation SHALL preserve editor-owned fields, prose and every unaffected template call. Legacy hand-written Zone calls SHALL remain compatible, but SHALL NOT provide a fallback full-article refresh path for converted generated identities.

#### Scenario: An editor changed a zone page

- **WHEN** an editor added a paragraph to an unconverted zone page on the wiki and the page is fetched and regenerated
- **THEN** the regenerated page holds that paragraph

#### Scenario: An editor corrected the connections

- **WHEN** an editor removed from the legacy connects field a zone that players cannot reach, and the raw game data still has that zone line
- **THEN** pre-cutover regeneration keeps the editor's field value

#### Scenario: A fact changes after conversion

- **WHEN** a new build changes a converted zone's shared level summary or gated connection without changing article membership
- **THEN** data publication changes the infobox
- **AND** refresh leaves the existing article source byte-identical

#### Scenario: A grouped page gains a member under the same anchor

- **WHEN** a new scene maps to an existing grouped article and its current root anchor remains valid
- **THEN** refresh updates the generated membership relation without editing the article

#### Scenario: A page splits after conversion

- **WHEN** a reviewed mapping moves a group member to another article
- **THEN** native guarded reconciliation and the existing lifecycle workflow account for the changed memberships
- **AND** unaffected editor text and calls remain unchanged
