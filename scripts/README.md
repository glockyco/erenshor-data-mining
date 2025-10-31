# Erenshor Scripts

Utility scripts for Erenshor data mining and comparison.

## validate_database.py

Validates database for data quality issues like duplicate IDs and missing fields.

### Usage

```bash
# Validate a specific variant
python scripts/validate_database.py main
python scripts/validate_database.py playtest

# Validate all variants
python scripts/validate_database.py --all

# Generate a report file
python scripts/validate_database.py playtest -o validation_report.md
```

### Checks

- **Duplicate IDs**: Items, Spells, Skills, Characters, Quests
- **Missing ResourceNames**: Items, Spells, Skills
- **Data consistency issues**

### Exit Codes

- `0`: All validations passed
- `1`: Validation failed with errors

### Examples

```bash
# Quick validation check before deployment
python scripts/validate_database.py playtest

# Generate report for all variants
python scripts/validate_database.py --all -o validation.md
```

---

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
