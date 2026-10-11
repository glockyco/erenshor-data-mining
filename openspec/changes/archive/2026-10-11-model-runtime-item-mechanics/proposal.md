# Proposal

## Why

Four item mechanics live only in game code, so the clean database cannot describe them, and `ItemSources` and `ItemUses` (task 5.4 of `publish-wiki-cargo-data`) would publish without them (design D11 of `adopt-data-backed-wiki`, issue #285):

- The Chessboard turns the Candlekeeper figurine into a mold when it summons its boss (`Chessboard.cs:107-112`).
- The Time Stone does nothing but return to the player in Shivering Tomb (2) and the Secluded Sanctuary (`SpellVessel.cs:2277-2284`).
- The Braxonian Flame Well blesses one piece of equipment offered with equal numbers of Sivakrux and Offering Stones (`TradeWindow.cs:175-255`, called at line 321).
- One fishing catch in 20 is replaced by one of the four torn map pieces (`Fishing.cs:69-74`).

The pipeline already pins the fishing rule as the code fact `fishing.map_bonus`, but only the Adventure Guide reads it. The Chessboard's item references are not exported at all.

## What Changes

- Export the `Item` fields of the `Chessboard` component (the eight figurines and `ReplaceStatue`), so the Candlekeeper figurine and its mold come from game data.
- Add code facts that pin the Candlekeeper conversion, the Time Stone scene gate, and the Flame Well offering rule, and give the existing `fishing.map_bonus` fact a clean-build consumer. A game update that changes any of them fails `extract code-facts`.
- Write each mechanic into the clean database:
  - item conversions: the Candlekeeper figurine yields its mold at the Chessboard;
  - fishing bonus catches: each torn map piece has a chance per catch in any water;
  - item zone restrictions: the Time Stone returns unused in its two zones;
  - quality offerings: Sivakrux and Offering Stones bless equipment at the Braxonian Flame Well, with the success and enhancement rule.
- Leave the Cargo schema and its publication to `publish-wiki-cargo-data` task 5.4, which reads these tables.

Non-goals: the other Chessboard figurines (their summoned bosses are already exported), Cargo tables or templates, and article text.

## Capabilities

### New Capabilities
- `runtime-item-mechanics`: how the clean database records item sources and uses that only game code defines, and how they stay tied to that code across game updates.

### Modified Capabilities

## Impact

- Unity export: `Chessboard` item fields into a new raw table.
- `src/tools/CodeFacts/specs/erenshor-facts.json`: three new facts.
- `src/erenshor/application/processor/`: a new processor module and four clean tables in `writer.py`, with unit tests.
- A main-variant export, code-facts extraction, and clean build to verify the rows.
