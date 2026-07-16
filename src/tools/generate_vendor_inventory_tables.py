#!/usr/bin/env python3
"""Generate paste-ready wiki vendor inventory tables from the clean database.

Usage:
    uv run python src/tools/generate_vendor_inventory_tables.py
    uv run python src/tools/generate_vendor_inventory_tables.py --all
"""

from erenshor.tools.vendor_inventory_tables import main

if __name__ == "__main__":
    raise SystemExit(main())
