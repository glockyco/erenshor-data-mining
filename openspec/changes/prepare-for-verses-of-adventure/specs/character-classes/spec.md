# Spec Delta

## Purpose

Defines where the set of playable classes comes from and how each consumer of the clean database covers every class that a game build ships, so that adding a class needs no code change.

## ADDED Requirements

### Requirement: Classes come from exported class assets

The clean database SHALL list each playable class that the game build ships as a class asset, with the name the game displays. The pipeline SHALL NOT add, drop or rename a class from a list in code.

#### Scenario: A build adds a class

- **WHEN** a game build ships a class asset that no earlier build had, such as the Bard in 0.8
- **THEN** the clean build lists that class next to the existing ones, without a code change

#### Scenario: A build without the new class

- **WHEN** the clean build runs on a build that ships six classes
- **THEN** it lists exactly those six classes

### Requirement: Consumers cover every exported class

The starter items, skill and spell levels, wiki pages and data modules, sheet queries and guide data SHALL cover each class in the clean database. A consumer SHALL fail its generation step and name the class when it meets a class it cannot present.

#### Scenario: Spells of the new class

- **WHEN** the clean database holds spells that the Bard can learn
- **THEN** the wiki spell pages, the spell data module and the spell sheet show the Bard and its level for each of those spells

#### Scenario: A class that a consumer cannot present

- **WHEN** a consumer needs a value for a class, such as a display label or an icon, and the class has none
- **THEN** generation fails with an error that names the class and the missing value, and writes no partial output
