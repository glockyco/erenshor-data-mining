# Erenshor Scripts

Utility scripts for Erenshor data mining and comparison.

## compare_variants.py

Automatically compares two database variants to identify new content.

### Usage

```bash
# Compare main vs playtest
python scripts/compare_variants.py main playtest

# Compare playtest vs demo
python scripts/compare_variants.py playtest demo

# Specify output file
python scripts/compare_variants.py main playtest -o my_report.md

# Print to stdout instead of file
python scripts/compare_variants.py main playtest --print
```

### Output

Generates a markdown report with:
- Summary statistics (counts comparison)
- New zones
- New items (with slot, level, and lore)
- New spells (with type, classes, level, and description)
- New characters/NPCs (with level, HP, and location)
- New quests (with XP/gold rewards and description)

### Examples

```bash
# Generate playtest comparison report
python scripts/compare_variants.py main playtest -o playtest_changes.md

# Quick preview in terminal
python scripts/compare_variants.py main playtest --print | less
```
