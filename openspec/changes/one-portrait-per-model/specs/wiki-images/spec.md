# Spec Delta

## MODIFIED Requirements

### Requirement: Every character model has a capture source

The image workflow SHALL list each resolved character portrait subject once, with its model keys and complete character membership, whether or not the wiki has a picture for it. Different looks SHALL have different subjects and render titles. It SHALL show the subject, render title, pages including unused pages, kind, and game object to capture. Different model keys SHALL share a subject only under a valid reviewed same-look declaration.

#### Scenario: Characters share a model

- **WHEN** the Vithean Chests of several arena rounds share one model and subject
- **THEN** the manifest captures the subject `Vithean Chest` once, for `Vithean Chest render.png`, from the chest of a generated page
- **AND** the manifest records all covered character members

#### Scenario: A character has no page

- **WHEN** a character's model is not shown on any page
- **THEN** the manifest still selects the character for capture, with no pages

#### Scenario: A page with the unused notice

- **WHEN** `Queen Evadne` carries the unused notice
- **THEN** the manifest names her model with that page and selects her prefab for capture

#### Scenario: Same-named characters have different looks

- **WHEN** a character kind contains two different looks assigned separate image names
- **THEN** the manifest contains a capture source for each look under its own subject and title
- **AND** no representative is selected from the other look

## ADDED Requirements

### Requirement: Capture approvals bind the resolved look

A character capture approval SHALL bind the subject, title, model membership, selected source, build, preset, and approved bytes. Capture review SHALL expose these facts beside the image. A stale approval SHALL NOT supply a newly split or changed look merely because its subject matches. Unchanged approved renders SHALL remain reusable when their reviewed identity still matches.

#### Scenario: A shared subject splits

- **WHEN** one subject becomes two separately named looks
- **THEN** the old approval is not copied to both subjects
- **AND** each look needs matching reviewed provenance before its render enters the catalog

#### Scenario: The source changes after review

- **WHEN** a manifest changes the model membership or selected capture source of an approved subject
- **THEN** the approval is rejected for that manifest and the workflow requests review

#### Scenario: A legacy approval has no model membership

- **WHEN** an existing approval records a subject but cannot prove which model members it depicts
- **THEN** the migration requires explicit provenance review or recapture before using it for the new resolved look

### Requirement: Split portrait titles preserve published files

A portrait title split SHALL preserve resolution of the previously published title to the look it already depicted. A project-owned file whose title changes SHALL move with its history and leave direct redirects. Other looks SHALL use their own approved titles. Editor-owned renders and screenshots SHALL remain untouched. The dry run SHALL expose the retained look, moves, redirects, creates, and conflicts before publication.

#### Scenario: One old title becomes two portrait titles

- **WHEN** a reviewed split gives two looks their own titles and the old project-owned file depicts one of them
- **THEN** the plan retains that file at a still-used title or moves it to that look's new title
- **AND** the old title continues to resolve directly to that look's file
- **AND** the other look receives only its own reviewed render

#### Scenario: The old file cannot be assigned to a look

- **WHEN** review cannot establish which split look the published file depicts
- **THEN** the affected split is blocked from publication until its file disposition is explicitly reviewed
- **AND** the old file remains unchanged

#### Scenario: A screenshot belongs to an editor

- **WHEN** a character's render subject splits while an editor screenshot exists under the old screenshot title
- **THEN** generated output retains that screenshot reference separately from the new render subjects
- **AND** the bot neither moves nor copies nor deletes the screenshot

### Requirement: Portrait publication needs separate approval

Visual approval of captures and approval of title wording SHALL NOT authorize live writes. Publication SHALL require explicit approval of the reviewed file and article or generated-data publication plan before the first wiki mutation. Missing captures, unresolved file ownership conflicts, or unresolved old-title dispositions SHALL block publication of the affected split.

#### Scenario: Captures are approved but publication is not

- **WHEN** all portrait captures pass review and no live publication plan has been approved
- **THEN** files, redirects, descriptions, articles, and data modules remain unwritten on the live wiki

#### Scenario: A split cannot be published completely

- **WHEN** one required new portrait has no approved render or a required file operation conflicts with an editor-owned file
- **THEN** the affected split's dependent page or data changes are not published
- **AND** the plan reports what prevents that split from being published
