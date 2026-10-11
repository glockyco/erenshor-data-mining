# Spec Delta

## Purpose

Defines how the clean database records item sources and uses that only game code defines, and how those records stay tied to that code across game updates.

## ADDED Requirements

### Requirement: Runtime item mechanics come from game data and pinned game code

The pipeline SHALL take each item of a runtime item mechanic from exported game data, or from an item ID that a code fact pins. It SHALL take each rule constant from a code fact that pins it. A game build that changes a pinned rule or ID SHALL fail `extract code-facts`.

#### Scenario: A game update changes a rule

- **WHEN** a new build changes the Time Stone's zones, the Flame Well's chances, the Candlekeeper conversion, or the fishing map chance
- **THEN** `extract code-facts` fails and names the fact

#### Scenario: A game update swaps a serialized item

- **WHEN** a new build points the Chessboard's `ReplaceStatue` field at another item
- **THEN** the next export and clean build name that item as the conversion's output without a code change

#### Scenario: A pinned item disappears

- **WHEN** an item ID that a code fact pins resolves to no item in the clean build
- **THEN** the clean build fails and names the ID

### Requirement: Item conversions

The clean database SHALL hold one row for each item that a game mechanic turns into another item, naming the input item, the output item, the zone, and the mechanic.

#### Scenario: The Candlekeeper figurine

- **WHEN** the clean build runs on the current main build
- **THEN** `item_conversions` holds one row from A Strange Figurine to the item in the Chessboard's `ReplaceStatue` field, in the Chessboard's zone

### Requirement: Fishing bonus catches

The clean database SHALL hold one row for each item that can replace a fishing catch in any water, with its chance per catch in percent.

#### Scenario: The torn map pieces

- **WHEN** the clean build runs on the current main build
- **THEN** each of the four torn map pieces has a fishing bonus chance of 1.25% per catch

#### Scenario: A short map pool

- **WHEN** the exported `Maps` pool has fewer entries than the game draws from
- **THEN** the clean build fails

### Requirement: Item zone restrictions

The clean database SHALL hold one row for each zone where an item's use has a different outcome, naming the item, the zone, and the outcome.

#### Scenario: The Time Stone

- **WHEN** the clean build runs on the current main build
- **THEN** the Time Stone has a `returned unused` row for Shivering Tomb (2) and for the Secluded Sanctuary, and no other zone row

### Requirement: Quality offerings

The clean database SHALL hold one row for each character that blesses offered equipment, naming the two required items and the rule: the success chance per stone pair, the chance per improvement level, the enhancement chance per stone pair, and the result and enhanced qualities.

#### Scenario: The Braxonian Flame Well

- **WHEN** the clean build runs on the current main build
- **THEN** each of the nine Braxonian Flame Well characters has a row requiring Sivakrux and Offering Stone, with 40 per stone pair, 8 per improvement level, 5 per stone pair for enhancement, Blessed as the result, and Ascended as the enhanced result
