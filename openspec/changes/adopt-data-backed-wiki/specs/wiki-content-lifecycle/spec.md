## MODIFIED Requirements

### Requirement: Content that nothing spawns is marked unused

The wiki SHALL mark a page about content that ships in the game files but that nothing in the current game spawns with a distinct `Historical Content` message. It SHALL not call that content removed. When the knowledge base of simulated-player chat lets chat name the content without being asked, the message SHALL say that simulated players can still name it in chat. The tooling SHALL derive that from the exported knowledge base, not from a hand-set flag. It SHALL place the page in `Category:Unused Content` and keep the rest of the page.

#### Scenario: A character that nothing spawns

- **WHEN** the facts file records `Queen Evadne` as unused
- **THEN** her page says that she is in the game files but that nothing in the current game spawns her
- **AND** the page appears in `Category:Unused Content`

#### Scenario: A character that chat still names

- **WHEN** the facts file records `Ancient Sentinel` as unused
- **AND** its knowledge entry has a zone, so random guild questions can name it
- **THEN** its page also says that simulated players can still name it in chat

#### Scenario: A character that chat names only on request

- **WHEN** the facts file records `Bazxzoth` as unused
- **AND** its knowledge entry has no zone
- **THEN** its page does not say that simulated players can name it in chat

### Requirement: Reviewed dispositions are applied with guards

The wiki tooling SHALL apply the pending notices, redirects, and disambiguation pages that the retired-page review reports, from the reviewed facts and the exported knowledge base only. When a live notice differs from them, it SHALL replace that notice and not add a second one. It SHALL write nothing while the review has an unexplained title or is incomplete. It SHALL skip a page that changed after the review read it, and it SHALL record each written page so that a rollback can restore it.

#### Scenario: A dry run

- **WHEN** a reviewer runs the apply command as a dry run
- **THEN** it lists each pending page with its action and new text
- **AND** it writes nothing

#### Scenario: An editor changes a page during the run

- **WHEN** a page changes after the review read it
- **THEN** the command does not write that page and reports it

#### Scenario: The facts change a live notice

- **WHEN** a new knowledge base lets chat name an unused character that already has the unused notice
- **THEN** the review reports the notice as pending
- **AND** the command replaces that notice, so the page keeps exactly one

#### Scenario: The review is not clean

- **WHEN** the review reports an unexplained title
- **THEN** the command stops before its first write

#### Scenario: A rollback

- **WHEN** a reviewer rolls back an applied run
- **THEN** every written page returns to its text before the run
