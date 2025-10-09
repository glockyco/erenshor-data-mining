"""Mapping CLI (scaffold): scan and validate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from erenshor.domain.mapping import Rule, load_mapping_file, save_mapping_file
from erenshor.application.services.mapping_validation import (
    scan_conflicts,
    validate_completeness,
    validate_existence,
)
from erenshor.infrastructure.config.paths import get_path_resolver
from erenshor.infrastructure.config.settings import load_settings
from erenshor.infrastructure.database.repositories import (
    get_characters,
    get_engine,
    get_factions,
    get_items,
    get_skills,
    get_spells,
)

__all__ = [
    "autofill",
    "init_skeleton",
    "scan",
    "set_mapping",
    "show_mapping",
    "validate",
]


app = typer.Typer(help="Mapping utilities")


def _default_mapping_path() -> Path:
    """Get default mapping.json path using PathResolver."""
    resolver = get_path_resolver()
    return resolver.mapping_file


@app.command("scan")
def scan(db: Path | None = typer.Option(None, help="DB path")) -> None:
    settings = load_settings()
    if db is not None:
        settings.db_path = db
    engine = get_engine(settings.db_path)
    conflicts = scan_conflicts(engine)
    if not conflicts:
        typer.echo("No conflicts found (spells only for now)")
        return
    typer.echo(f"Found {len(conflicts)} conflict group(s):")
    for g in conflicts[:20]:
        typer.echo(f" - {g.display_name}: {len(g.entities)} entities")
    if len(conflicts) > 20:
        typer.echo(f" ... and {len(conflicts) - 20} more")


@app.command("validate")
def validate(
    mapping: Path | None = typer.Option(None, help="mapping.json path"),
    db: Path | None = typer.Option(None, help="DB path"),
) -> None:
    mp = mapping or _default_mapping_path()
    mf = load_mapping_file(mp)
    settings = load_settings()
    if db is not None:
        settings.db_path = db
    engine = get_engine(settings.db_path)
    conflicts = scan_conflicts(engine)
    missing = validate_completeness(mf, conflicts)
    existence_errors = validate_existence(mf, engine)
    typer.echo(
        f"Conflicts: {len(conflicts)}; Missing rules: {len(missing)}; Bad refs: {len(existence_errors)}"
    )
    for k in missing[:50]:
        typer.echo(f" - {k}")
    for e in existence_errors[:50]:
        typer.echo(f" ! {e}")
    if missing or existence_errors:
        raise typer.Exit(code=1)


@app.command("init")
def init_skeleton(
    mapping: Path | None = typer.Option(
        None, help="mapping.json path to create/update"
    ),
    db: Path | None = typer.Option(None, help="DB path"),
) -> None:
    """Create or update a mapping.json with placeholder rules for missing conflicts (spells only for now)."""
    mp = mapping or _default_mapping_path()
    mf = load_mapping_file(mp)
    settings = load_settings()
    if db is not None:
        settings.db_path = db
    engine = get_engine(settings.db_path)
    conflicts = scan_conflicts(engine)
    missing = validate_completeness(mf, conflicts)
    if not missing:
        typer.echo("No missing rules; mapping up to date")
        return
    added = 0
    for key in missing:
        # Add placeholder custom rule with no page; user must fill wiki_page_name
        mf.add(key, Rule(mapping_type="custom", wiki_page_name=None, reason=None))
        added += 1

    save_mapping_file(mf, mp)
    typer.echo(f"Added {added} placeholder rule(s) to {mp}")


def _build_display_name_index(engine: Any) -> dict[str, str]:
    """Return a map of mapping keys (e.g., 'item:RESNAME') to display names from DB."""
    idx: dict[str, str] = {}
    for s in get_spells(engine, obtainable_only=False):
        idx[f"spell:{s.ResourceName}"] = s.SpellName
    for it in get_items(engine, obtainable_only=False):
        idx[f"item:{it.ResourceName}"] = it.ItemName
    for sk in get_skills(engine):
        idx[f"skill:{sk.ResourceName}"] = sk.SkillName
    for ch in get_characters(engine):
        if ch.IsPrefab and ch.ObjectName:
            stable = ch.ObjectName
        else:
            scene = ch.Scene or "Unknown"
            x = f"{ch.X:.2f}" if ch.X is not None else "0.00"
            y = f"{ch.Y:.2f}" if ch.Y is not None else "0.00"
            z = f"{ch.Z:.2f}" if ch.Z is not None else "0.00"
            stable = f"{ch.ObjectName}|{scene}|{x}|{y}|{z}"
        idx[f"character:{stable}"] = ch.NPCName
    for faction in get_factions(engine):
        idx[f"faction:{faction.REFNAME}"] = faction.FactionDesc
    return idx


@app.command("autofill")
def autofill(
    mapping: Path | None = typer.Option(None, help="mapping.json path to update"),
    db: Path | None = typer.Option(None, help="DB path"),
    only_empty: bool = typer.Option(
        True, help="Only fill rules where wiki_page_name is empty/None"
    ),
    only_conflicts: bool = typer.Option(
        False, help="Restrict to entities that are in conflict groups"
    ),
) -> None:
    """Fill wiki_page_name fields with display names from the DB.

    This keeps existing non-empty names unchanged unless --only-empty is False.
    """
    mp = mapping or _default_mapping_path()
    mf = load_mapping_file(mp)
    settings = load_settings()
    if db is not None:
        settings.db_path = db
    engine = get_engine(settings.db_path)

    allowed_keys: set[str] | None = None
    if only_conflicts:
        allowed_keys = set()
        for g in scan_conflicts(engine):
            for e in g.entities:
                allowed_keys.add(f"{e.content_type}:{e.stable_identifier}")

    idx = _build_display_name_index(engine)
    updated = 0
    skipped = 0
    missing = 0
    for key, rule in mf.rules.items():
        if allowed_keys is not None and key not in allowed_keys:
            continue
        if only_empty and rule.wiki_page_name and rule.wiki_page_name.strip():
            skipped += 1
            continue
        name = idx.get(key)
        if not name:
            missing += 1
            continue
        rule.wiki_page_name = name
        updated += 1

    save_mapping_file(mf, mp)
    typer.echo(
        f"Autofilled {updated} rule(s); skipped existing={skipped}; missing={missing} (no DB match)"
    )


@app.command("show")
def show_mapping(
    entity_key: str = typer.Argument(
        ..., help="Entity key (e.g., 'spell:NONE - Exploding Arrow')"
    ),
    mapping: Path | None = typer.Option(None, help="mapping.json path"),
) -> None:
    """Show mapping details for an entity key."""
    mp = mapping or _default_mapping_path()
    mf = load_mapping_file(mp)

    rule = mf.rules.get(entity_key)
    if not rule:
        typer.echo(f"No mapping found for: {entity_key}")
        raise typer.Exit(code=1)

    typer.echo(f"Entity: {entity_key}")
    typer.echo(f"  Wiki Page: {rule.wiki_page_name or '(none)'}")
    typer.echo(f"  Display Name: {rule.display_name or '(none)'}")
    typer.echo(f"  Image Name: {rule.image_name or '(none)'}")
    typer.echo(f"  Mapping Type: {rule.mapping_type}")
    typer.echo(f"  Reason: {rule.reason or '(none)'}")


@app.command("set")
def set_mapping(
    entity_key: str = typer.Argument(
        ..., help="Entity key (e.g., 'spell:NONE - Exploding Arrow')"
    ),
    page: str | None = typer.Option(None, "--page", help="Wiki page name"),
    display: str | None = typer.Option(None, "--display", help="Display name override"),
    image: str | None = typer.Option(None, "--image", help="Image name override"),
    reason: str | None = typer.Option(None, "--reason", help="Reason for mapping"),
    mapping: Path | None = typer.Option(None, help="mapping.json path"),
) -> None:
    """Set or update a mapping for an entity.

    Examples:
        mapping set "spell:NONE - Exploding Arrow" --page "Exploding Arrow" --display "Exploding Arrow"
        mapping set "spell:AURA - Resonate" --page "Aura: Resonance" --display "Aura: Resonance" --image "Resonance_Icon"
        mapping set "character:Braxonian Planar Guardian Fire" --page "Braxonian Planar Guard (Fire)" --display "Braxonian Planar Guard"
    """
    if not page and not display and not image:
        typer.echo("Error: Must specify at least one of --page, --display, or --image")
        raise typer.Exit(code=1)

    mp = mapping or _default_mapping_path()
    mf = load_mapping_file(mp)

    # Get existing rule or create new one
    rule = mf.rules.get(entity_key)
    if not rule:
        rule = Rule(mapping_type="custom")

    # Update fields
    if page:
        rule.wiki_page_name = page
    if display:
        rule.display_name = display
    if image:
        rule.image_name = image
    if reason is not None:
        rule.reason = reason

    # Save
    mf.add(entity_key, rule)
    save_mapping_file(mf, mp)

    typer.echo(f"Updated mapping for: {entity_key}")
    if page:
        typer.echo(f"  Wiki Page: {page}")
    if display:
        typer.echo(f"  Display Name: {display}")
    if image:
        typer.echo(f"  Image Name: {image}")
