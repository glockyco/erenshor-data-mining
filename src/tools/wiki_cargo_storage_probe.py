#!/usr/bin/env python3
"""Probe live wiki.gg Cargo storage and recreate behavior.

This tool intentionally defaults to a dry run. Pass ``--live`` to create temporary
sandbox templates/pages on the configured MediaWiki target. Live runs delete the
sandbox pages they create, but Cargo tables require manual admin cleanup through
Special:CargoTables / Special:DeleteCargoTable.

Usage:
    uv run python src/tools/wiki_cargo_storage_probe.py
    uv run python src/tools/wiki_cargo_storage_probe.py --live --candidate lua-nested
    uv run python src/tools/wiki_cargo_storage_probe.py --live --candidate all --prefix Probe20260709
"""

from __future__ import annotations

from erenshor.tools.wiki_cargo_probe.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
