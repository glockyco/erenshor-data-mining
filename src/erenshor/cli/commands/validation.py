"""Miscellaneous commands for wiki operations."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from erenshor.application.reporting import Category, Reporter, entity
from erenshor.infrastructure.database.repositories import get_item_stats, get_items
from erenshor.infrastructure.wiki.template_contract import check_contracts
from erenshor.cli.shared import (
    OperationResult,
    WikiEnvironment,
    setup_wiki_environment,
)
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.wiki_parser import (
    find_templates as mw_find_templates,
)
from erenshor.shared.wiki_parser import (
    parse as mw_parse,
)
from erenshor.shared.wiki_parser import (
    template_params as mw_template_params,
)

__all__ = [
    "check_templates",
    "check_templates_operation",
    "summarize_reports",
    "summarize_reports_operation",
    "validate_characters",
    "validate_characters_operation",
    "validate_items",
    "validate_items_operation",
]


app = typer.Typer()


@app.command("validate-characters")
def validate_characters(
    db: Path | None = typer.Option(None, help="Database path"),
    cache_dir: Path | None = typer.Option(None, help="Cache directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
    reports_dir: Path | None = typer.Option(None, help="Reports directory"),
) -> None:
    """Validate character/enemy pages for required fields and constraints."""
    env = setup_wiki_environment(db, cache_dir, output_dir)
    result = validate_characters_operation(env, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def validate_characters_operation(
    env: WikiEnvironment, reports_dir: Path | None = None
) -> OperationResult:
    """Validate characters - testable business logic."""
    sim_dir = env.output_storage.pages_dir
    if not sim_dir.exists():
        return OperationResult(
            success=False,
            updated=0,
            errors=["No updated pages. Run 'update characters' first."],
            summary_line="Validation failed - no updated pages found",
        )

    required_fields = {
        "name",
        "image",
        "imagecaption",
        "type",
        "faction",
        "factionChange",
        "zones",
        "coordinates",
        "spawnchance",
        "respawn",
        "guaranteeddrops",
        "droprates",
        "level",
        "experience",
        "health",
        "mana",
        "ac",
        "strength",
        "endurance",
        "dexterity",
        "agility",
        "intelligence",
        "wisdom",
        "charisma",
        "magic",
        "poison",
        "elemental",
        "void",
    }

    reporter = Reporter.open(
        command="wiki validate-characters",
        args={"output_dir": str(env.output_storage.pages_dir)},
        reports_dir=reports_dir,
    )
    from typing import Any

    violations: list[dict[str, Any]] = []
    checked = 0
    page_meta: dict[str, dict[str, Any]] = {}

    for f in sorted(sim_dir.glob("*.txt")):
        text = f.read_text(encoding="utf-8")
        try:
            code = mw_parse(text)
        except Exception:
            continue
        tpls = mw_find_templates(code, ["Enemy", "Character"])
        if not tpls:
            continue
        inf = tpls[0]
        checked += 1
        params = {str(p.name).strip(): str(p.value).strip() for p in inf.params}
        missing = sorted(list(required_fields - set(params.keys())))
        type_val = params.get("type", "")
        is_boss = "Boss" in type_val
        is_rare = "Rare" in type_val
        meta = page_meta.get(f.stem) or {}
        is_unique_meta = bool(meta.get("is_unique"))
        is_friendly_meta = bool(meta.get("is_friendly"))
        coords_val = params.get("coordinates", "")
        spawn_val = params.get("spawnchance", "")
        v: dict[str, Any] = {}

        if missing:
            v["missing_fields"] = missing
            reporter.emit_violation(
                rule_id="characters.missing_fields",
                message="Missing required fields",
                entity=entity(page_title=f.stem),
                category=Category.VALIDATE,
                details={"fields": missing},
            )

        # Coordinates rules:
        # - Allowed for Boss (type indicates) OR when DB marks entity as unique
        coords_allowed = is_boss or is_unique_meta
        if not coords_allowed and coords_val:
            v["coordinates_should_be_blank"] = coords_val
            reporter.emit_violation(
                rule_id="characters.coords_policy",
                message="Coordinates should be blank",
                entity=entity(page_title=f.stem),
                category=Category.VALIDATE,
                details={"value": coords_val},
            )

        # Spawn chance rules:
        # - Allowed only for hostile enemies (not friendly) that are Boss or Rare
        spawn_allowed = (not is_friendly_meta) and (is_boss or is_rare)
        if not spawn_allowed and spawn_val:
            v["spawnchance_should_be_blank"] = spawn_val
            reporter.emit_violation(
                rule_id="characters.spawn_policy",
                message="Spawnchance should be blank",
                entity=entity(page_title=f.stem),
                category=Category.VALIDATE,
                details={"value": spawn_val},
            )

        if v:
            v["page"] = f.stem
            v["type"] = type_val
            violations.append(v)

    reporter.metric("checked_pages", checked)
    exit_code = 2 if violations else 0
    reporter.finish(exit_code=exit_code)

    if violations:
        return OperationResult(
            success=False,
            updated=checked,
            errors=[f"{len(violations)} validation failures"],
            summary_line=f"{reporter.summary_line()} -- Validation failed",
        )

    return OperationResult(
        success=True,
        updated=checked,
        summary_line=f"{reporter.summary_line()} -- Validation passed",
    )


@app.command("validate-items")
def validate_items(
    db: Path | None = typer.Option(None, help="Database path"),
    cache_dir: Path | None = typer.Option(None, help="Cache directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
    reports_dir: Path | None = typer.Option(None, help="Reports directory"),
) -> None:
    """Validate item pages for structure and policy compliance."""
    env = setup_wiki_environment(db, cache_dir, output_dir)
    result = validate_items_operation(env, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def validate_items_operation(
    env: WikiEnvironment, reports_dir: Path | None = None
) -> OperationResult:
    """Validate items - testable business logic."""
    import re as _re

    sim_dir = env.output_storage.pages_dir
    if not sim_dir.exists():
        return OperationResult(
            success=False,
            updated=0,
            errors=["No updated pages. Run 'update items' first."],
            summary_line="Validation failed - no updated pages found",
        )

    reporter = Reporter.open(
        command="wiki validate-items",
        args={"output_dir": str(env.output_storage.pages_dir)},
        reports_dir=reports_dir,
    )
    from typing import Any

    violations: list[dict[str, Any]] = []
    checked = 0
    num_fields = [
        "str",
        "end",
        "dex",
        "agi",
        "int",
        "wis",
        "cha",
        "res",
        "damage",
        "delay",
        "health",
        "mana",
        "armor",
        "magic",
        "poison",
        "elemental",
        "void",
    ]

    for f in sorted(sim_dir.glob("*.txt")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "{{Weapon" not in text and "{{Armor" not in text:
            continue
        checked += 1
        v: dict[str, Any] = {"page": f.stem}

        # Header formatting
        idx_w = text.find("{{Weapon")
        idx_a = text.find("{{Armor")
        idx_ib = (
            min([i for i in [idx_w, idx_a] if i != -1])
            if (idx_w != -1 or idx_a != -1)
            else -1
        )
        header_ok = True
        if idx_ib != -1:
            line = text[idx_ib : text.find("\n", idx_ib)]
            header_ok = "|" not in line
        if not header_ok:
            v["header_format"] = "first line contains parameters"

        # Fancy counts and placement
        fw = text.count("Fancy-weapon")
        fa = text.count("Fancy-armor")
        if "{{Weapon" in text and fw != 3:
            v["fancy_weapon_count"] = fw
        if "{{Armor" in text and fa != 3:
            v["fancy_armor_count"] = fa
        idx_fw = text.find("Fancy-weapon")
        idx_fa = text.find("Fancy-armor")
        if idx_ib != -1:
            if idx_fw != -1 and idx_fw < idx_ib:
                v["fancy_before_infobox_weapon"] = True
            if idx_fa != -1 and idx_fa < idx_ib:
                v["fancy_before_infobox_armor"] = True

        # Extract first infobox body
        m = _re.search(r"\{\{Item\n(.*?)\n\}\}", text, _re.DOTALL)
        ib_body = m.group(1) if m else ""

        def _val(key: str) -> str:
            mm = _re.search(rf"\n\|{_re.escape(key)}=([^\n]*)", ib_body)
            return (mm.group(1) or "").strip() if mm else ""

        buy_val = _val("buy")
        vend_val = _val("vendorsource")
        sell_present = bool(_re.search(r"\n\|sell=", ib_body))
        if buy_val and not vend_val:
            v["buy_without_vendor"] = True
        if not sell_present:
            v["missing_sell"] = True

        # Disallowed fields in infobox
        disallowed = []
        for k in ["image", "imagecaption", "type", "relic", "classes", "description"]:
            if _re.search(rf"\n\|{k}=", ib_body):
                disallowed.append(k)
        if disallowed:
            v["disallowed_infobox_fields"] = disallowed

        # Blank numeric stats in Fancy
        blank_numeric = False
        for fld in num_fields:
            if f"| {fld} = \n" in text:
                blank_numeric = True
                break
        if blank_numeric:
            v["blank_numeric_in_fancy"] = True

        if len(v) > 1:
            violations.append(v)
            reporter.emit_violation(
                rule_id="items.structure",
                message="Structure validation failures",
                entity=entity(page_title=f.stem),
                category=Category.VALIDATE,
                details={k: v[k] for k in v.keys() if k != "page"},
            )

    # Deep verification against DB for Fancy values
    linker = RegistryLinkResolver(env.registry)
    items = get_items(env.engine, obtainable_only=False)

    def classify_required_slot(slot: str | None) -> str | None:
        s = (slot or "").strip()
        sl = s.lower()
        if s in ("Primary", "PrimaryOrSecondary", "Secondary"):
            return "weapon"
        if s and sl not in ("general", "aura"):
            return "armor"
        return None

    # Helper to extract tier values from Fancy templates using mwparserfromhell
    def _tier_values(text: str, template_name: str, tier: str) -> dict[str, str]:
        code = mw_parse(text)
        tpls = [
            t for t in code.filter_templates() if str(t.name).strip() == template_name
        ]
        for t in tpls:
            params = mw_template_params(t)
            if (params.get("tier") or "").strip() == str(tier):

                def norm(v: str) -> str:
                    vv = (v or "").strip()
                    if vv == "" or vv.lower() == "false":
                        return "0"
                    if vv.lower() == "true":
                        return "1"
                    return vv

                keys = [
                    "damage",
                    "res",
                    "str",
                    "end",
                    "dex",
                    "agi",
                    "int",
                    "wis",
                    "cha",
                    "health",
                    "mana",
                    "armor",
                    "magic",
                    "poison",
                    "elemental",
                    "void",
                ]
                return {k: norm(params.get(k, "")) for k in keys}
        return {}

    # Map quality to fancy tier index
    def _quality_to_tier(q: str) -> str:
        return {"Normal": "0", "Blessed": "1", "Godly": "2"}.get(q, "0")

    for it in items:
        try:
            kind = classify_required_slot(it.RequiredSlot)
            if kind not in ("weapon", "armor"):
                continue
            page_title = linker.resolve_item_title(it.ResourceName, it.ItemName, it.Id)
            page_path = sim_dir / f"{page_title}.txt"
            if not page_path.exists():
                continue
            text = page_path.read_text(encoding="utf-8", errors="ignore")
            template_name = "Fancy-weapon" if kind == "weapon" else "Fancy-armor"
            stats_rows = get_item_stats(env.engine, it.Id)

            # Build expected per-tier values from DB rows (by quality)
            expected_by_tier: dict[str, dict[str, str]] = {}
            for r in stats_rows:
                tier = _quality_to_tier(r.Quality)
                expected_by_tier[tier] = {
                    "damage": str(r.WeaponDmg or 0),
                    "res": str(r.Res or 0),
                    "str": str(r.Str or 0),
                    "end": str(r.End or 0),
                    "dex": str(r.Dex or 0),
                    "agi": str(r.Agi or 0),
                    "int": str(r.Int or 0),
                    "wis": str(r.Wis or 0),
                    "cha": str(r.Cha or 0),
                    "health": str(r.HP or 0),
                    "mana": str(r.Mana or 0),
                    "armor": str(r.AC or 0),
                    "magic": str(r.MR or 0),
                    "poison": str(r.PR or 0),
                    "elemental": str(r.ER or 0),
                    "void": str(r.VR or 0),
                }

            # Compare for tiers 0..2
            for tier in ("0", "1", "2"):
                if tier not in expected_by_tier:
                    continue
                wiki_vals = _tier_values(text, template_name, tier)
                if not wiki_vals:
                    violations.append({"page": page_title, "missing_fancy_tier": tier})
                    reporter.emit_violation(
                        rule_id="items.fancy.tier_missing",
                        message=f"Missing Fancy tier {tier}",
                        entity=entity(page_title=page_title),
                        category=Category.VALIDATE,
                        details={"tier": tier},
                    )
                    continue

                mism: dict[str, dict[str, str]] = {}
                exp = expected_by_tier[tier]
                for k, dbv in exp.items():
                    wv = wiki_vals.get(k, "0")
                    # Normalize zero/blank equivalence
                    if (dbv == "0" and wv == "") or (dbv == "" and wv == "0"):
                        continue
                    if dbv != wv:
                        mism[k] = {"db": dbv, "wiki": wv}

                if mism:
                    violations.append(
                        {"page": page_title, "tier": tier, "field_mismatches": mism}
                    )
                    reporter.emit_violation(
                        rule_id="items.fancy.tier_mismatch",
                        message=f"Fancy tier {tier} mismatches vs DB",
                        entity=entity(page_title=page_title),
                        category=Category.VALIDATE,
                        details={"tier": tier, "field_mismatches": mism},
                    )
        except Exception as exc:
            pv = page_title if "page_title" in locals() else str(it.ItemName)
            violations.append({"page": pv, "error": f"Deep validation error: {exc}"})
            reporter.emit_error(
                message="Deep validation error",
                exception=exc,
                entity=entity(page_title=pv),
                category=Category.VALIDATE,
                details={},
            )

    reporter.metric("checked_pages", checked)
    exit_code = 2 if violations else 0
    reporter.finish(exit_code=exit_code)

    if violations:
        return OperationResult(
            success=False,
            updated=checked,
            errors=[f"{len(violations)} validation failures"],
            summary_line=f"{reporter.summary_line()} -- Validation failed",
        )

    return OperationResult(
        success=True,
        updated=checked,
        summary_line=f"{reporter.summary_line()} -- Validation passed",
    )


@app.command("summarize-reports")
def summarize_reports(
    run_id: str | None = typer.Option(
        None, help="Run ID to summarize; defaults to latest"
    ),
    reports_dir: Path | None = typer.Option(
        None, help="Reports directory (default: out/reports)"
    ),
) -> None:
    """Print a concise summary for a single reporting run (latest by default)."""
    # This command doesn't need full WikiEnvironment, pass None for unused parameters
    env = None  # Not used in summarize_reports_operation
    result = summarize_reports_operation(env, run_id, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def summarize_reports_operation(
    env: WikiEnvironment | None,
    run_id: str | None = None,
    reports_dir: Path | None = None,
) -> OperationResult:
    """Summarize reports - testable business logic."""
    if reports_dir is None:
        reports_dir = Path("out/reports")

    if not reports_dir.exists():
        return OperationResult(
            success=False,
            updated=0,
            errors=[f"Reports directory not found: {reports_dir}"],
            summary_line="Failed to find reports directory",
        )

    def _latest_run(d: Path) -> Path | None:
        subs = [p for p in d.iterdir() if p.is_dir()]
        if not subs:
            return None
        return sorted(subs, key=lambda p: p.name, reverse=True)[0]

    run_dir = reports_dir / run_id if run_id else _latest_run(reports_dir)
    if not run_dir or not run_dir.exists():
        return OperationResult(
            success=False,
            updated=0,
            errors=["No report runs found."],
            summary_line="No report runs found",
        )

    summary_path = run_dir / "summary.json"
    manifest_path = run_dir / "manifest.json"
    if not summary_path.exists():
        return OperationResult(
            success=False,
            updated=0,
            errors=[f"summary.json not found in {run_dir}"],
            summary_line="Summary file not found",
        )

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest_path.exists()
            else {}
        )
    except Exception as exc:
        return OperationResult(
            success=False,
            updated=0,
            errors=[f"Failed to read run summary: {exc}"],
            summary_line="Failed to read summary",
        )

    counts = summary.get("counts", {})

    # Build detailed summary output
    lines = []
    lines.append(f"Run: {run_dir.name}")
    if manifest:
        lines.append(f"  command: {manifest.get('command')}")
        lines.append(
            f"  started: {manifest.get('started_at')}  finished: {manifest.get('finished_at')}  exit: {manifest.get('exit_code')}"
        )
    lines.append("Counts:")
    lines.append(
        f"  violations: {counts.get('violations', 0)}  errors: {counts.get('errors', 0)}  updates: {counts.get('updates', 0)}  events: {counts.get('total_events', 0)}"
    )
    lines.append(f"Run directory: {run_dir}")

    summary_output = "\n".join(lines)

    return OperationResult(
        success=True,
        updated=0,
        summary_line=summary_output,
    )


@app.command("check-templates")
def check_templates(
    templates_dir: Path = typer.Option(
        Path("templates_cache"), help="Directory containing fetched templates"
    ),
    fmt: str = typer.Option(
        "text", "--fmt", "--format", help="Output format: text|json"
    ),
) -> None:
    """Check template contracts and dependencies."""
    result = check_templates_operation(templates_dir, fmt)
    if result.summary_line:
        typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def check_templates_operation(
    templates_dir: Path, fmt: str = "text"
) -> OperationResult:
    """Check templates - testable business logic."""
    results = check_contracts(templates_dir)

    if fmt == "json":
        # manual dict conversion for stability
        payload = {
            "results": [
                {
                    "template": r.template,
                    "context": r.context,
                    "missing_in_template": r.missing_in_template,
                    "extra_in_template": r.extra_in_template,
                    "template_fields": r.template_fields,
                    "context_fields": r.context_fields,
                }
                for r in results
            ]
        }
        reports_dir = Path("out/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "templates_contract.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        return OperationResult(
            success=True,
            updated=len(results),
            summary_line=f"Wrote contract report to {reports_dir / 'templates_contract.json'}",
        )

    # text format
    if not results:
        return OperationResult(
            success=False,
            updated=0,
            errors=[
                "No templatedata found for mapped templates. Run 'wiki fetch-templates' first."
            ],
            summary_line="No template data found",
        )

    lines = []
    for r in results:
        lines.append(f"{r.template} vs {r.context}")
        if r.missing_in_template:
            lines.append("  missing in template: " + ", ".join(r.missing_in_template))
        if r.extra_in_template:
            lines.append("  extra in template: " + ", ".join(r.extra_in_template))

    return OperationResult(
        success=True,
        updated=len(results),
        summary_line="\n".join(lines),
    )
