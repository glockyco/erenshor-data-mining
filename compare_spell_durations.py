#!/usr/bin/env python3
"""Compare spell durations between playtest (old) and main (new) databases."""

import sqlite3

# Connect to both databases
main_conn = sqlite3.connect("variants/main/erenshor-main.sqlite")
playtest_conn = sqlite3.connect("variants/playtest/erenshor-playtest.sqlite")

# Query both databases
main_cursor = main_conn.cursor()
playtest_cursor = playtest_conn.cursor()

main_spells = main_cursor.execute("""
    SELECT Id, SpellName, SpellDurationInTicks, ResourceName
    FROM Spells
    WHERE SpellDurationInTicks > 0
""").fetchall()

playtest_spells = playtest_cursor.execute("""
    SELECT Id, SpellName, SpellDurationInTicks, ResourceName
    FROM Spells
    WHERE SpellDurationInTicks > 0
""").fetchall()

# Create lookup dictionaries
main_dict = {row[0]: (row[1], row[2], row[3]) for row in main_spells}
playtest_dict = {row[0]: (row[1], row[2], row[3]) for row in playtest_spells}

# Compare and collect results (Old = Playtest, New = Main)
results = []
for spell_id, (name, old_ticks, resource_name) in playtest_dict.items():
    old_secs = old_ticks * 5.0

    if spell_id in main_dict:
        new_name, new_ticks, new_resource_name = main_dict[spell_id]
        new_secs = new_ticks * 3.0
        secs_diff = new_secs - old_secs

        # Calculate percentage change
        if old_secs > 0:
            pct_change = (secs_diff / old_secs) * 100.0
        else:
            pct_change = 0.0

        ticks_changed = old_ticks != new_ticks

        results.append(
            (
                spell_id,
                name,
                old_ticks,
                old_secs,
                new_ticks,
                new_secs,
                ticks_changed,
                secs_diff,
                pct_change,
                resource_name,
            )
        )
    else:
        # Not in main (shouldn't happen based on earlier results)
        results.append(
            (
                spell_id,
                name,
                old_ticks,
                old_secs,
                None,
                None,
                True,
                None,
                None,
                resource_name,
            )
        )

# Separate into two groups
ticks_changed = [r for r in results if r[6]]
ticks_same = [r for r in results if not r[6]]

# Sort each group by percentage change descending
ticks_changed.sort(key=lambda x: (-(x[8] if x[8] is not None else 0), x[1]))
ticks_same.sort(key=lambda x: (-(x[8] if x[8] is not None else 0), x[1]))


def print_table(rows, title):
    """Print a formatted table."""
    print(f"\n{title}")
    print("=" * 165)
    print(
        f"{'ID':<10} {'Spell Name':<35} {'Old(ticks)':<11} {'New(ticks)':<11} {'Old(sec)':<10} {'New(sec)':<10} {'Diff(sec)':<10} {'+Change':<10} {'ResourceName':<40}"
    )
    print("=" * 165)

    for row in rows:
        spell_id, name, ot, os, nt, ns, ticks_chg, diff, pct, resource_name = row
        nt_str = str(int(nt)) if nt is not None else "N/A"
        os_str = f"{int(os)}s" if os is not None else "N/A"
        ns_str = f"{int(ns)}s" if ns is not None else "N/A"
        diff_str = f"{diff:+.0f}s" if diff is not None else "N/A"
        pct_str = f"{pct:+.1f}%" if pct is not None else "N/A"

        print(
            f"{spell_id:<10} {name:<35} {int(ot):<11} {nt_str:<11} {os_str:<10} {ns_str:<10} {diff_str:<10} {pct_str:<10} {resource_name:<40}"
        )


# Print both tables
print_table(
    ticks_changed, f"SPELLS WITH CHANGED TICK COUNTS ({len(ticks_changed)} spells)"
)
print_table(ticks_same, f"SPELLS WITH SAME TICK COUNTS ({len(ticks_same)} spells)")

# Print summary
print("\n" + "=" * 165)
print(
    f"Summary: {len(ticks_changed)} with changed ticks, {len(ticks_same)} with same ticks"
)
print("Old (5 sec/tick), New (3 sec/tick)")

main_conn.close()
playtest_conn.close()
