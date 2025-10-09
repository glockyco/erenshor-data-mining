"""Audit commands for wiki content validation."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

import typer

from erenshor.application.reporting import Category, Reporter, entity
from erenshor.cli.shared import (
    OperationResult,
    WikiEnvironment,
    setup_wiki_environment,
)

__all__ = [
    "audit_db_auras",
    "audit_db_auras_operation",
    "audit_db_consumables",
    "audit_db_consumables_operation",
    "audit_templates",
    "audit_templates_operation",
    "audit_updates",
    "audit_updates_operation",
]


logger = logging.getLogger(__name__)


app = typer.Typer()


@app.command("audit-db-consumables")
def audit_db_consumables(
    db: Path | None = typer.Option(None, help="Database path"),
    cache_dir: Path | None = typer.Option(None, help="Cache directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
    reports_dir: Path | None = typer.Option(None, help="Reports directory"),
) -> None:
    """Audit consumables vs. ability books in the database."""
    env = setup_wiki_environment(db, cache_dir, output_dir)
    result = audit_db_consumables_operation(env, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def audit_db_consumables_operation(
    env: WikiEnvironment, reports_dir: Path | None = None
) -> OperationResult:
    """Audit consumables in database - testable business logic."""
    from erenshor.infrastructure.database.repositories import (
        get_consumables_and_ability_books,
    )

    consumables, ability_books = get_consumables_and_ability_books(env.engine)

    summary_line = f"Found {len(consumables)} consumables and {len(ability_books)} ability books in the database."

    return OperationResult(
        success=True,
        updated=0,
        summary_line=summary_line,
    )


@app.command("audit-db-auras")
def audit_db_auras(
    db: Path | None = typer.Option(None, help="Database path"),
    cache_dir: Path | None = typer.Option(None, help="Cache directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
    reports_dir: Path | None = typer.Option(None, help="Reports directory"),
) -> None:
    """Audit auras in the database."""
    env = setup_wiki_environment(db, cache_dir, output_dir)
    result = audit_db_auras_operation(env, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def audit_db_auras_operation(
    env: WikiEnvironment, reports_dir: Path | None = None
) -> OperationResult:
    """Audit auras in database - testable business logic."""
    from erenshor.infrastructure.database.repositories import get_auras

    auras = get_auras(env.engine)

    summary_line = f"Found {len(auras)} auras in the database."

    return OperationResult(
        success=True,
        updated=0,
        summary_line=summary_line,
    )


@app.command("audit-templates")
def audit_templates(
    db: Path | None = typer.Option(None, help="Database path"),
    cache_dir: Path | None = typer.Option(None, help="Cache directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
    reports_dir: Path | None = typer.Option(None, help="Reports directory"),
) -> None:
    """Scan cached pages and summarize template usage (counts and fancy tables)."""
    env = setup_wiki_environment(db, cache_dir, output_dir)
    result = audit_templates_operation(env, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def audit_templates_operation(
    env: WikiEnvironment, reports_dir: Path | None = None
) -> OperationResult:
    """Audit templates - testable business logic."""
    source_dir = env.cache_storage.pages_dir

    if not source_dir.exists():
        return OperationResult(
            success=False,
            updated=0,
            summary_line=f"Source directory not found: {source_dir}",
            errors=[f"Source directory not found: {source_dir}"],
        )

    # Canonicalize template names: collapse underscores/spaces; keep Title Case key variants
    def canon(name: str) -> str:
        n = name.strip()
        # Stop at trailing braces or invalid chars
        n = re.split(r"[\|}\n]", n)[0]
        n = n.replace("_", " ")
        return n.strip()

    template_counts: Counter[str] = Counter()
    template_pages: dict[str, set[str]] = defaultdict(set)
    fancy_counts: Counter[str] = Counter()
    fancy_per_page: dict[str, dict[str, int]] = {}

    pattern = re.compile(r"\{\{\s*([A-Za-z][\w _\-]*)")
    for f in sorted(source_dir.glob("*.txt")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        # Count templates
        for m in pattern.finditer(text):
            tname = canon(m.group(1))
            if not tname:
                continue
            template_counts[tname] += 1
            template_pages[tname].add(f.stem)
        # Fancy tables
        fa = text.count("Fancy-armor")
        fw = text.count("Fancy-weapon")
        if fa:
            fancy_counts["Fancy-armor"] += fa
        if fw:
            fancy_counts["Fancy-weapon"] += fw
        if fa or fw:
            fancy_per_page[f.stem] = {"Fancy-armor": fa, "Fancy-weapon": fw}

    # Core templates to highlight first
    core = [
        "Ability",
        "Enemy",
        "Character",
        "Armor",
        "Weapon",
        "Mold",
        "Ability Books",
        "Consumable",
        "Item",
        "Auras",
        "Zone",
        "Pet",
        "Faction",
        "Enemy Stats",
    ]

    def pages_for(name: str) -> int:
        return len(template_pages.get(name, set()))

    summary = {
        "templates": [
            {
                "name": name,
                "occurrences": template_counts.get(name, 0),
                "pages": pages_for(name),
            }
            for name in core
        ],
        "fancy": {
            "Fancy-armor": fancy_counts.get("Fancy-armor", 0),
            "Fancy-weapon": fancy_counts.get("Fancy-weapon", 0),
            "pages": len(fancy_per_page),
            "distribution": {
                "Fancy-armor": dict(
                    Counter(v["Fancy-armor"] for v in fancy_per_page.values())
                ),
                "Fancy-weapon": dict(
                    Counter(v["Fancy-weapon"] for v in fancy_per_page.values())
                ),
            },
            "anomalies": {
                "Fancy-armor": sorted(
                    [
                        p
                        for p, v in fancy_per_page.items()
                        if v["Fancy-armor"] not in (0, 3)
                    ]
                ),
                "Fancy-weapon": sorted(
                    [
                        p
                        for p, v in fancy_per_page.items()
                        if v["Fancy-weapon"] not in (0, 3)
                    ]
                ),
            },
            "mismatches": {
                "Fancy-armor_without_Armor": sorted(
                    list(
                        (
                            template_pages.get("Fancy-armor", set())
                            - template_pages.get("Armor", set())
                        )
                    )
                ),
                "Armor_without_Fancy-armor": sorted(
                    list(
                        (
                            template_pages.get("Armor", set())
                            - template_pages.get("Fancy-armor", set())
                        )
                    )
                ),
                "Fancy-weapon_without_Weapon": sorted(
                    list(
                        (
                            template_pages.get("Fancy-weapon", set())
                            - template_pages.get("Weapon", set())
                        )
                    )
                ),
                "Weapon_without_Fancy-weapon": sorted(
                    list(
                        (
                            template_pages.get("Weapon", set())
                            - template_pages.get("Fancy-weapon", set())
                        )
                    )
                ),
            },
        },
        "others": [
            {
                "name": name,
                "occurrences": cnt,
                "pages": pages_for(name),
            }
            for name, cnt in sorted(
                ((n, c) for n, c in template_counts.items() if n not in core),
                key=lambda kv: (-kv[1], kv[0]),
            )
        ],
    }

    # Write JSON report if reports_dir provided
    if reports_dir:
        reports_dir = Path(reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "templates_usage.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

    return OperationResult(
        success=True,
        updated=len(template_pages),
        summary_line=f"Scanned {len(list(source_dir.glob('*.txt')))} pages, found {len(template_counts)} unique templates",
    )


@app.command("audit-updates")
def audit_updates(
    db: Path | None = typer.Option(None, help="Database path"),
    cache_dir: Path | None = typer.Option(None, help="Cache directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
    reports_dir: Path | None = typer.Option(None, help="Reports directory"),
) -> None:
    """Audit suspicious differences between before (cache) and after (updated) pages."""
    env = setup_wiki_environment(db, cache_dir, output_dir)
    result = audit_updates_operation(env, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def audit_updates_operation(
    env: WikiEnvironment, reports_dir: Path | None = None
) -> OperationResult:
    """Audit updates - testable business logic."""
    import re as _re

    from erenshor.shared.wiki_parser import parse as mw_parse

    cache_dir = env.cache_storage.pages_dir
    output_dir = env.output_storage.pages_dir

    def _load(path: Path) -> str:
        return (
            path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        )

    targets = {
        "weapon",
        "armor",
        "item",
        "consumable",
        "auras",
        "ability books",
        "ability",
        "mold",
        "enemy",
        "character",
    }

    from typing import Any

    def _first_tpl(text: str) -> Any:
        if not text:
            return None
        try:
            code = mw_parse(text)
        except Exception:
            return None
        tpls = [
            t for t in code.filter_templates() if str(t.name).strip().lower() in targets
        ]
        return tpls[0] if tpls else None

    def _tpl_name(t: Any) -> str:
        return str(t.name).strip() if t is not None else ""

    def _tpl_params(t: Any) -> dict[str, str]:
        params: dict[str, str] = {}
        if t is None:
            return params
        for p in t.params:
            params[str(p.name).strip()] = str(p.value).strip()
        return params

    # Summary dict contains mixed types: some keys have list[str], others have list[dict]
    summary: dict[str, list[str | dict[str, object]]] = {
        "broken_infobox_after": [],
        "multiple_infobox_after": [],
        "template_type_changed": [],
        "fields_regressed": [],
        "items_fancy_count_issues": [],
        "items_buy_without_vendor": [],
        "items_disallowed_fields_present": [],
        "enemies_itemlink_with_image_param": [],
        "spawn_policy_violations": [],
        "character_templates_remaining": [],
    }

    # Overview pages that don't need infoboxes
    overview_pages = {"Armor", "Weapons", "Fishing", "Auras"}

    # Compare pages in updated dir against cache
    for f_after in sorted(output_dir.glob("*.txt")):
        title = f_after.stem
        before_path = cache_dir / f_after.name
        before = _load(before_path)
        after = _load(f_after)
        if not after:
            continue

        # Parse templates
        t_after = _first_tpl(after)
        if t_after is None and title not in overview_pages:
            summary["broken_infobox_after"].append(title)
            continue
        try:
            code_after = mw_parse(after)
        except Exception:
            code_after = None
        t_after_name = _tpl_name(t_after)
        p_after = _tpl_params(t_after)

        # Count all target templates after
        multi_after = 0
        if code_after is not None:
            try:
                ct = [
                    t
                    for t in code_after.filter_templates()
                    if str(t.name).strip().lower() in targets
                ]
                multi_after = len(ct)
            except Exception as e:
                logger.warning(
                    f"Failed to count templates in {title} after update: {e}"
                )
        if multi_after > 1:
            summary["multiple_infobox_after"].append(
                {"title": title, "count": multi_after}
            )

        # Before template (if any)
        t_before = _first_tpl(before)
        t_before_name = _tpl_name(t_before)
        p_before = _tpl_params(t_before)

        # Expected template migrations during codebase updates
        allowed_migrations = {
            ("Consumable", "Item"),  # Migrating consumables to Item template
            ("Character", "Enemy"),  # Migrating all characters to Enemy template
            ("Weapon", "Item"),  # Unified item templates
            ("Armor", "Item"),  # Unified item templates
            ("Auras", "Item"),  # Unified item templates
        }

        # Only flag unexpected template changes
        if t_before_name and t_after_name and (t_before_name != t_after_name):
            if (t_before_name, t_after_name) not in allowed_migrations:
                summary["template_type_changed"].append(
                    {"title": title, "before": t_before_name, "after": t_after_name}
                )

        # Field regressions: non-empty in before -> empty/missing in after (with exceptions)
        exc_items = {"image", "imagecaption", "type", "relic", "classes", "description"}
        tpl_lower = t_after_name.lower()
        is_enemy = tpl_lower == "enemy"
        is_character = tpl_lower == "character"
        type_val = p_after.get("type", "")
        is_boss = "Boss" in type_val
        is_rare = "Rare" in type_val

        regressed: list[str] = []
        for k, v in p_before.items():
            vb = (v or "").strip()
            if not vb:
                continue
            va = (p_after.get(k) or "").strip()
            if va:
                continue
            if tpl_lower in {"weapon", "armor"} and k in exc_items:
                continue
            if k == "spawnchance":
                spawn_allowed = is_enemy and (is_boss or is_rare)
                if not spawn_allowed:
                    continue
            regressed.append(k)
        if regressed:
            summary["fields_regressed"].append(
                {"title": title, "fields": sorted(regressed)}
            )

        # Items-specific checks
        if tpl_lower in {"weapon", "armor"}:
            fw = after.count("Fancy-weapon")
            fa = after.count("Fancy-armor")
            if tpl_lower == "weapon" and fw != 3:
                summary["items_fancy_count_issues"].append(
                    {"title": title, "fancy_weapon_count": fw}
                )
            if tpl_lower == "armor" and fa != 3:
                summary["items_fancy_count_issues"].append(
                    {"title": title, "fancy_armor_count": fa}
                )
            ib = after
            m = _re.search(r"\{\{(Weapon|Armor)\n(.*?)\n\}\}", ib, _re.DOTALL)
            ib_body = m.group(2) if m else ""

            def _val(key: str) -> str:
                mm = _re.search(rf"\n\|{_re.escape(key)}=([^\n]*)", ib_body)
                return (mm.group(1) or "").strip() if mm else ""

            buy_val = _val("buy")
            vend_val = _val("vendorsource")
            if buy_val and not vend_val:
                summary["items_buy_without_vendor"].append(title)
            disallowed = []
            for k in exc_items:
                if _re.search(rf"\n\|{_re.escape(k)}=", ib_body):
                    disallowed.append(k)
            if disallowed:
                summary["items_disallowed_fields_present"].append(
                    {"title": title, "fields": disallowed}
                )

        # Enemy/Character droprates: flag image= usage and policy violations
        if is_enemy or is_character:
            dr = p_after.get("droprates", "") or ""
            if "image=" in dr:
                summary["enemies_itemlink_with_image_param"].append(title)
            sp = p_after.get("spawnchance", "")
            spawn_allowed = is_enemy and (is_boss or is_rare)
            if sp and not spawn_allowed:
                summary["spawn_policy_violations"].append(
                    {
                        "title": title,
                        "value": sp,
                        "template": t_after_name,
                        "type": type_val,
                    }
                )

    # Scan for Character templates in updated files (should use Enemy template)
    remaining: list[str] = []
    for f in sorted(output_dir.glob("*.txt")):
        text_all = (
            (output_dir / f.name).read_text(encoding="utf-8", errors="ignore")
            if f.exists()
            else ""
        )
        if not text_all:
            continue
        try:
            code_all = mw_parse(text_all)
            tpls_all = [
                t
                for t in code_all.filter_templates()
                if str(t.name).strip().lower() == "character"
            ]
            if tpls_all:
                remaining.append(f.stem)
        except Exception:
            if "{{Character" in text_all:
                remaining.append(f.stem)
    # Cast is safe: this key always contains list[str], not mixed types
    # Assigned to Summary TypedDict with Any value type for flexibility
    summary["character_templates_remaining"] = sorted(remaining)  # type: ignore[assignment]

    # Define audit rules with consistent naming
    AUDIT_RULES = {
        "broken_infobox_after": "audit.infobox.broken_after",
        "multiple_infobox_after": "audit.infobox.multiple",
        "template_type_changed": "audit.template.type_changed",
        "fields_regressed": "audit.fields.regressed",
        "items_fancy_count_issues": "audit.items.fancy_count_issues",
        "items_buy_without_vendor": "audit.items.buy_without_vendor",
        "items_disallowed_fields_present": "audit.items.disallowed_fields",
        "enemies_itemlink_with_image_param": "audit.drops.image_param",
        "spawn_policy_violations": "audit.spawn.policy_violation",
        "character_templates_remaining": "audit.character_templates_remaining",
    }

    # Human-readable messages for audit violations
    AUDIT_MESSAGES = {
        "audit.infobox.broken_after": "Infobox broken or missing after update",
        "audit.infobox.multiple": "Multiple infoboxes found after update",
        "audit.template.type_changed": "Template type changed during update",
        "audit.fields.regressed": "Field values lost during update",
        "audit.items.fancy_count_issues": "Weapon/armor fancy table count issues",
        "audit.items.buy_without_vendor": "Buy value present without vendor source",
        "audit.items.disallowed_fields": "Disallowed fields present in template",
        "audit.drops.image_param": "Image parameter in ItemLink drops",
        "audit.spawn.policy_violation": "Spawn chance assignment policy violation",
        "audit.character_templates_remaining": "Character templates not migrated to Enemy",
    }

    # Count total violations
    total_violations = sum(
        len(violations) if isinstance(violations, list) else 0
        for violations in summary.values()
    )

    # Use Reporter if reports_dir specified
    if reports_dir:
        reporter = Reporter.open(
            command="wiki audit-updates",
            args={"output_dir": str(output_dir)},
            reports_dir=reports_dir,
        )

        def _emit_list(rule_id: str, lst: list[str | dict[str, object]]) -> None:
            message = AUDIT_MESSAGES.get(rule_id, rule_id)
            for x in lst:
                title = x if isinstance(x, str) else x.get("title")
                # Ensure title is str or None for entity()
                page_title = (
                    str(title)
                    if title is not None and not isinstance(title, str)
                    else title
                )
                reporter.emit_violation(
                    rule_id=rule_id,
                    message=message,
                    entity=entity(page_title=page_title),
                    category=Category.AUDIT,
                    details=x if isinstance(x, dict) else {},
                )

        def _count(key: str) -> int:
            val = summary.get(key)
            if isinstance(val, list):
                return len(val)
            return 0

        # Emit all violations and metrics using consistent rule IDs
        violations_by_rule: dict[str, list[str | dict[str, object]]] = {}
        for summary_key, rule_id in AUDIT_RULES.items():
            if summary_key in summary:
                violations = summary[summary_key]
                _emit_list(rule_id, violations)
                reporter.metric(rule_id, _count(summary_key))
                violations_by_rule[rule_id] = violations

        # Generate human-readable violations report
        violations_report = _generate_violations_report(
            violations_by_rule, AUDIT_MESSAGES
        )
        violations_path = reporter.base_dir / "violations.md"
        violations_path.write_text(violations_report, encoding="utf-8")
        reporter.finish(exit_code=0)

    return OperationResult(
        success=True,
        updated=0,
        summary_line=f"Audited {len(list(output_dir.glob('*.txt')))} pages, found {total_violations} violations",
    )


def _generate_violations_report(
    violations_by_rule: dict[str, list[str | dict[str, object]]],
    audit_messages: dict[str, str],
) -> str:
    """Generate a human-readable violations report in Markdown format."""
    lines = ["# Audit Violations Report\n"]

    total_violations = sum(
        len(violations) if isinstance(violations, list) else 0
        for violations in violations_by_rule.values()
    )

    if total_violations == 0:
        lines.append("✅ No violations found!\n")
        return "\n".join(lines)

    lines.append(
        f"Found {total_violations} violations across {len(violations_by_rule)} categories.\n"
    )

    for rule_id, violations in violations_by_rule.items():
        if not violations or len(violations) == 0:
            continue

        message = audit_messages.get(rule_id, rule_id)
        count = len(violations) if isinstance(violations, list) else 0
        lines.append(f"## {message} ({count} violations)\n")

        if isinstance(violations, list):
            for violation in violations[:10]:  # Limit to first 10 for readability
                if isinstance(violation, str):
                    lines.append(f"- {violation}")
                elif isinstance(violation, dict):
                    title = violation.get("title", "Unknown")
                    details = violation.get("details", "")
                    if details:
                        lines.append(f"- {title}: {details}")
                    else:
                        lines.append(f"- {title}")

            if count > 10:
                lines.append(f"- ... and {count - 10} more")

        lines.append("")  # Empty line between sections

    return "\n".join(lines)
