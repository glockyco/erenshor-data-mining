#!/usr/bin/env python3
"""Compare generated articles against current-build game tooltip evidence."""

from __future__ import annotations

import argparse
import re
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from functools import cache
from pathlib import Path
from typing import Any

import httpx
import mwparserfromhell
from smoke.mediawiki import api_url, parse_page
from smoke.render import _build_dom, _Node

from erenshor.application.extract.database_comparison import recorded_build_id
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_tooltips.capture import reconcile
from erenshor.application.wiki_tooltips.compare import (
    ObservedLine,
    fixed_dps,
    label,
    line_differences,
    lines_for,
    normalize_damage,
    quality_name,
    read_game_window,
    viewer_exclusion,
)
from erenshor.application.wiki_tooltips.report import ParityPaths, expected_coverage, read_json, write_json
from erenshor.application.wiki_tooltips.tmp import Span, Tone

_ART_ICONS = {
    "item-tooltip-quality-sparkle",
    "erenshor-icon",
    "item-tooltip-coin",
    "item-spell-details-icon",
    "mw-broken-media",
}
_BLOCKS = {"div", "p", "table", "tr", "td", "ul", "li", "blockquote"}
_TONE_CLASSES = frozenset(
    {
        *(f"item-tooltip-tier-{level}" for level in range(8)),
        "item-tooltip-value",
        "item-tooltip-stat-value",
        'item-tooltip-stat-value[data-value="0"]',
        "item-spell-level",
        "item-spell-duration",
        "item-spell-damage",
        "item-spell-flag",
        "item-spell-window-flag",
        "item-spell-positive",
        "item-spell-negative",
        "item-tooltip-charm-label",
        "item-tooltip-charm-explanation",
        "item-tooltip-aura-type",
        "item-tooltip-crafting-notes",
        "item-tooltip-aura-spell-name",
        "item-tooltip-book-warning",
    }
)
_CSS_TONES = {
    "#00f9ff": Tone.BLESSED,
    "#fc87ff": Tone.ASCENDED,
    "#f4cb6b": Tone.GOLD,
    "#f5e5a0": Tone.VALUE,
    "#a9afbd": Tone.MUTED,
    "#a7abba": Tone.MUTED,
    "#9dee94": Tone.POSITIVE,
    "#15e300": Tone.POSITIVE,
    "#ff6666": Tone.NEGATIVE,
    "#ff0000": Tone.DAMAGE,
    "yellow": Tone.EMPHASIS,
}
_STAT_LABELS = {
    "Str": "Strength:",
    "End": "Endurance:",
    "Dex": "Dexterity:",
    "Agi": "Agility:",
    "Int": "Intelligence:",
    "Wis": "Wisdom:",
    "Cha": "Charisma:",
    "HP": "Health:",
    "Mana": "Mana:",
    "AC": "Armor:",
    "Res": "Res.:",
    "MR": "Magic Resist:",
    "PR": "Poison Resist:",
    "ER": "Elem. Resist:",
    "VR": "Void Resist:",
}
_ITEM_FIELDS = (
    "itemPrice",
    "ItemName",
    "Slot",
    "Usable",
    "Str",
    "End",
    "Dex",
    "Agi",
    "Int",
    "Wis",
    "Cha",
    "HP",
    "Mana",
    "AC",
    "Res",
    "DMGtxt",
    "DMGNum",
    "DelTXT",
    "DelNum",
    "RangeText",
    "RangeNum",
    "MR",
    "PR",
    "ER",
    "VR",
    "InspirationTxt",
    "InspirationStat",
    "DissonanceTxt",
    "DissonanceStat",
    "Lore",
    "ReqLvl",
    "ClickSpell",
    "ClickDesc",
    "OtherTextParent",
)
_JOINED_STATS = {
    "DMGtxt": "DMGNum",
    "DelTXT": "DelNum",
    "RangeText": "RangeNum",
    "InspirationTxt": "InspirationStat",
    "DissonanceTxt": "DissonanceStat",
}


def _item_field_lines(lines: list[ObservedLine]) -> list[ObservedLine]:
    groups: dict[str, list[ObservedLine]] = defaultdict(list)
    for line in lines:
        groups[line.field].append(line)
    ordered = _ITEM_FIELDS + tuple(sorted(groups.keys() - set(_ITEM_FIELDS)))
    output = []
    for field in ordered:
        values = groups.pop(field, [])
        if field in _JOINED_STATS and len(values) == 1:
            numeric = groups.get(_JOINED_STATS[field], [])
            if len(numeric) == 1:
                label_line = values[0]
                values = [
                    ObservedLine(
                        label_line.source,
                        label_line.field,
                        label_line.index,
                        label_line.spans + label(" ") + numeric[0].spans,
                    )
                ]
                groups.pop(_JOINED_STATS[field])
        if field == "Usable" and len(values) == 1 and values[0].text.strip() != "General Item":
            line = values[0]
            classes = sorted(line.text.split())
            values = [ObservedLine(line.source, line.field, line.index, label(" ".join(classes)))]
        output.extend(values)
    return output


def has(node: _Node, name: str) -> bool:
    return name in node.classes()


def under(node: _Node, name: str) -> bool:
    parent = node.parent
    while parent is not None:
        if has(parent, name):
            return True
        parent = parent.parent
    return False


def stylesheet_tones(source: str) -> dict[str, Tone]:
    """Read colors for the maintained semantic classes used on tooltip rows."""
    tones = {}
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", source):
        for selector in selectors.split(","):
            name = selector.strip().removeprefix(".")
            if name not in _TONE_CLASSES:
                continue
            color = re.search(r"(?:^|;)\s*color:\s*([^;]+)", body)
            if color:
                tones[name] = parse_css_tone(color[1].strip())
    return tones


@cache
def _stylesheet_tones() -> dict[str, Tone]:
    return stylesheet_tones((Path(__file__).resolve().parents[1] / "wiki/gadgets/erenshor.css").read_text())


def rendered_lines(root: _Node, field: str) -> list[ObservedLine]:
    """Tokenize the rendered subtree, including its text outside known row classes."""
    class_tones = _stylesheet_tones()
    output: list[ObservedLine] = []
    current: list[Span] = []

    def close(origin: str) -> None:
        if any(span.text.strip() for span in current):
            output.append(ObservedLine("MediaWiki action=parse", origin, len(output) + 1, tuple(current)))
        current.clear()

    def walk(node: _Node, tone: Tone, italic: bool, origin: str) -> None:
        classes = node.classes()
        if node.tag in {"img", "script", "style", "link"} or _ART_ICONS.intersection(classes):
            return
        if node.tag == "br":
            close(origin)
            return
        block = node.tag in _BLOCKS
        if block:
            close(origin)
            origin = classes[0] if classes else origin
        for name in classes:
            tone = class_tones.get(name, tone)
        if "item-tooltip-stat-value" in classes and node.attrs.get("data-value") == "0":
            tone = class_tones.get('item-tooltip-stat-value[data-value="0"]', tone)
        inline = re.search(r"(?:^|;)\s*color:\s*(#[\da-fA-F]{6})(?:;|$)", node.attrs.get("style", ""))
        if inline:
            tone = parse_css_tone(inline[1])
        italic = (
            italic
            or node.tag in {"em", "i"}
            or bool(
                {
                    "item-spell-window-lines",
                    "item-tooltip-book-requirement",
                    "item-tooltip-book-class-req",
                    "item-tooltip-book-detail",
                    "item-tooltip-book-description",
                }.intersection(classes)
            )
        )
        if has(node, "item-spell-book-row"):
            italic = False
        for child in node.children:
            if isinstance(child, _Node):
                if has(child, "item-tooltip-class") and current:
                    current.append(Span(" ", tone, italic))
                walk(child, tone, italic, origin)
            else:
                current.append(Span(child, tone, italic))
        if block:
            close(origin)

    walk(root, Tone.NORMAL, False, field)
    close(field)
    return output


def parse_css_tone(color: str) -> Tone:
    from erenshor.application.wiki_tooltips.tmp import parse_tmp

    color = color.casefold()
    if tone := _CSS_TONES.get(color):
        return tone
    base = color.removeprefix("#")
    parsed = parse_tmp("color", source="MediaWiki action=parse", stable_key="renderer", field="style", color=base)
    return parsed[0][0].tone


def generated_item_keys(text: str) -> list[str]:
    """Use the generated Item root that precedes each companion call."""
    result = []
    pending = ""
    for template in mwparserfromhell.parse(text).filter_templates(recursive=False):
        name = str(template.name).strip()
        if name == "Item":
            pending = str(template.get("stablekey").value).strip() if template.has("stablekey") else ""
        elif pending and (name == "ItemTooltip" or name.startswith("Item/")):
            result.append(pending)
            pending = ""
    return result


def published_titles(database: Path, findings: list[dict[str, Any]]) -> dict[str, list[str]]:
    titles: dict[str, list[str]] = defaultdict(list)
    with closing(sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)) as db:
        for table in ("items", "spells", "skills", "stances"):
            for key, title in db.execute(f"SELECT stable_key, wiki_page_name FROM {table} WHERE is_wiki_generated=1"):
                if not title:
                    findings.append({"key": key, "error": "Published identity has no article title"})
                    continue
                titles[title].append(key)
    return dict(sorted(titles.items()))


def eligible_wiki_roots(root: _Node, keys: list[str], text: str) -> dict[str, _Node]:
    mounts: dict[str, _Node] = {}
    item_nodes = []
    for node in root.walk():
        if has(node, "erenshor-ability-tooltip"):
            key = node.attrs.get("data-erenshor-key", "")
            if not key or key in mounts:
                raise ValueError(f"Missing or duplicate rendered ability identity: {key!r}")
            mounts[key] = node
        if has(node, "item-tooltip-quality-set") or (
            has(node, "item-tooltip") and not under(node, "item-tooltip-quality-set")
        ):
            item_nodes.append(node)
    for key, node in zip(generated_item_keys(text), item_nodes, strict=True):
        if key in mounts:
            raise ValueError(f"Duplicate rendered item identity: {key!r}")
        mounts[key] = node
    if set(keys) != set(mounts):
        missing = sorted(set(keys) - mounts.keys())
        extra = sorted(mounts.keys() - set(keys))
        raise ValueError(f"Missing keys: {missing}. Extra keys: {extra}")
    return mounts


def quality_cards(root: _Node, quantities: tuple[int, ...]) -> dict[str, _Node]:
    cards = {}
    for node in root.walk():
        quality = node.attrs.get("data-erenshor-quality")
        if quality is None:
            continue
        if quality in cards:
            raise ValueError(f"Duplicate rendered quality card: {quality}")
        cards[quality] = node
    expected = {quality_name(quantity) for quantity in quantities} if len(quantities) > 1 else set()
    if set(cards) != expected:
        raise ValueError(f"Expected quality cards {sorted(expected)}, have {sorted(cards)}")
    return cards


def _expected_fields(window: dict[str, Any], key: str, exclusions: list[dict[str, Any]]) -> list[ObservedLine]:
    lines: list[ObservedLine] = []
    fields = read_game_window(window, key)
    for name, group in fields.items():
        for observed in lines_for(window["source"], name, group):
            line = observed
            if not line.text.strip():
                continue
            if reason := viewer_exclusion(line, level_scaled_mana=window.get("level_scaled_mana", False)):
                exclusions.append(
                    {
                        "key": key,
                        "source": line.source,
                        "field": name,
                        "line": line.text,
                        "reason": reason,
                    }
                )
                continue
            normalized = normalize_damage(line) if name == "SpellDetailsDesc" else line
            if normalized != line:
                exclusions.append(
                    {
                        "key": key,
                        "source": line.source,
                        "field": name,
                        "line": line.text,
                        "wiki_line": normalized.text,
                        "reason": "D14 damage interval",
                    }
                )
            if window["source"] == "ItemInfoWindow.DisplayItem" and name in _STAT_LABELS:
                normalized = ObservedLine(
                    line.source,
                    line.field,
                    line.index,
                    label(_STAT_LABELS[name] + " ") + normalized.spans,
                )
            lines.append(normalized)
    return lines


def _adjacent_item_details(card: _Node) -> list[_Node]:
    if card.parent is None or not has(card, "item-tooltip"):
        return []
    details = []
    next_sibling = False
    for sibling in card.parent.children:
        if sibling is card:
            next_sibling = True
            continue
        if not next_sibling:
            continue
        if isinstance(sibling, str):
            if sibling.strip():
                break
            continue
        if has(sibling, "item-spell-details"):
            details.append(sibling)
        else:
            break
    return details


def _item(actual: _Node, entry: dict[str, Any], exclusions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key = entry["stable_key"]
    exclusion_start = len(exclusions)
    expected = _item_field_lines(_expected_fields(entry, key, exclusions))
    if entry.get("details"):
        details = _expected_fields(entry["details"], key, exclusions)
        expected.extend(line for line in details if line.field == "SpellDetailsName")
        expected.extend(line for line in details if line.field != "SpellDetailsName")
    actual_lines = [
        line for line in rendered_lines(actual, "Item tooltip") if line.field != "item-tooltip-quality-label"
    ]
    for details in _adjacent_item_details(actual):
        actual_lines.extend(rendered_lines(details, "Item spell details"))
    if any(row["reason"] == "viewer book knowledge" for row in exclusions[exclusion_start:]):
        visible = []
        for line in actual_lines:
            if line.field in {"item-tooltip-book-requirement", "item-tooltip-book-class-req"}:
                exclusions.append(
                    {
                        "key": key,
                        "source": line.source,
                        "field": line.field,
                        "line": line.text,
                        "reason": "viewer book knowledge",
                    }
                )
            else:
                visible.append(line)
        actual_lines = visible
    dps = [line for line in actual_lines if line.field == "item-tooltip-dps"]
    if dps:
        raw = entry["fields"]
        dps_value = fixed_dps(raw["DMGNum"]["text"], raw["DelNum"]["text"].removesuffix(" sec"), raw["Slot"]["text"])
        if len(dps) == 1 and dps[0].text.strip() == f"Base DPS: {dps_value}":
            actual_lines.remove(dps[0])
            exclusions.append(
                {
                    "key": key,
                    "source": "MediaWiki action=parse",
                    "field": "Base DPS",
                    "line": dps[0].text,
                    "reason": "D14 fixed weapon DPS",
                }
            )
    return line_differences(expected, actual_lines)


def _ability(actual: _Node, entry: dict[str, Any], key: str, exclusions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actual_lines = rendered_lines(actual, "Ability tooltip")
    if key.startswith("stance:"):
        fields = _expected_fields(entry, key, exclusions)
        return line_differences(
            [line for field in ("Name", "Desc") for line in fields if line.field == field], actual_lines
        )
    expected = _expected_fields(entry["hover"], key, exclusions)
    order = {field: index for index, field in enumerate(("Name", "Kind", "Desc", "Mana", "Type"))}
    expected.sort(key=lambda line: order[line.field])
    compact_differences = line_differences(expected, actual_lines)
    if entry["kind"] == "spell":
        details = [
            line for line in _expected_fields(entry["details"], key, exclusions) if line.field == "SpellDetailsDesc"
        ]
        spellbook_rows = [
            line
            for line in _expected_fields(entry, key, exclusions)
            if line.text.startswith(("Mana Cost:", "Cooldown:"))
        ]
        for prefix, location in (("Mana Cost:", "Spell Line:"), ("Cooldown:", "Cast Time:")):
            selected = [line for line in spellbook_rows if line.text.startswith(prefix)]
            after = next((i + 1 for i, line in enumerate(details) if line.text.startswith(location)), len(details))
            details[after:after] = selected
        panel = actual.parent
        if panel is None or not has(panel, "item-ability-panel"):
            raise ValueError("No standalone spell details panel")
        details_node = [node for node in panel.walk() if has(node, "item-spell-details-content")]
        if len(details_node) != 1:
            raise ValueError("Missing or duplicate standalone spell details contents")
        compact_differences.extend(line_differences(details, rendered_lines(details_node[0], "Spell details")))
    return compact_differences


def compare(paths: ParityPaths, base_url: str) -> dict[str, Any]:
    before = paths.inputs()
    evidence = read_json(paths.evidence)
    build = recorded_build_id(paths.database)
    if evidence.get("build") != build or evidence.get("installed_build") != build or evidence.get("failures") != []:
        raise ValueError(f"Game evidence does not represent complete clean database build {build}")
    entries = evidence["entries"]
    exclusions = reconcile(paths.database, entries)
    if evidence.get("exclusions") != exclusions:
        raise ValueError("Game evidence exclusions do not match the clean database")
    wanted = expected_coverage(entries, exclusions)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[entry["stable_key"]].append(entry)
        if entry.get("stance_key"):
            grouped[entry["stance_key"]].append(entry)
    findings: list[dict[str, Any]] = []
    coverage: Counter[str] = Counter()
    expected_differences: list[dict[str, Any]] = []
    storage = WikiStorage(paths.wiki)
    with httpx.Client(timeout=30) as client:
        for title, keys in published_titles(paths.database, findings).items():
            try:
                text = storage.read_generated_by_title(title)
                if text is None:
                    raise ValueError("Missing generated article")
                parsed = parse_page(client, api_url(base_url), title, source=text)
                root = _build_dom(parsed.html)
                for node in root.walk():
                    if (
                        has(node, "scribunto-error")
                        or has(node, "error")
                        or (has(node, "new") and node.attrs.get("title", "").startswith("Template:"))
                    ):
                        raise ValueError(f"Render error: {node.text()}")
                mounts = eligible_wiki_roots(root, keys, text)
            except (ValueError, RuntimeError, httpx.HTTPError) as error:
                findings.append({"page": title, "keys": keys, "error": str(error)})
                continue
            for key, node in mounts.items():
                try:
                    kind = key.split(":", 1)[0]
                    observations = grouped[key]
                    if not observations:
                        raise ValueError("No game observation")
                    if kind == "item":
                        cards = quality_cards(node, tuple(entry["quantity"] for entry in observations))
                        for entry in observations:
                            quality = quality_name(entry["quantity"]) if cards else None
                            if quality:
                                expected_differences.append(
                                    {
                                        "key": key,
                                        "quality": quality,
                                        "reason": "D14 separate equipment card",
                                    }
                                )
                            result = _item(cards[quality] if quality else node, entry, expected_differences)
                            coverage["item_cards"] += 1
                            if result:
                                findings.append({"key": key, "page": title, "quality": quality, "differences": result})
                    else:
                        if len(observations) != 1:
                            raise ValueError("Duplicate game observation")
                        if result := _ability(node, observations[0], key, expected_differences):
                            findings.append({"key": key, "page": title, "differences": result})
                    coverage[kind] += 1
                except (ValueError, KeyError, ZeroDivisionError) as error:
                    findings.append({"key": key, "page": title, "error": str(error)})
    coverage.setdefault("item_cards", 0)
    if coverage != wanted:
        findings.append({"error": f"Expected complete coverage {wanted}, compared {dict(coverage)}"})
    if paths.inputs() != before:
        findings.append({"error": "Renderer inputs changed during comparison"})
    return {
        "schema": 1,
        "build": build,
        "complete": not findings,
        "inputs": before,
        "coverage": dict(coverage),
        "exclusions": exclusions,
        "expected_differences": expected_differences,
        "findings": findings,
    }


def summary(report: dict[str, Any]) -> str:
    lines = [f"Build {report['build']}", f"Coverage: {report['coverage']}", "", "Excluded identities:"]
    lines.extend(f"  {entry['stable_key']}: {entry['reason']}" for entry in report["exclusions"])
    lines.extend(("", "Approved differences and viewer exclusions:"))
    counts = Counter(row["reason"] for row in report["expected_differences"])
    examples = {}
    for row in report["expected_differences"]:
        examples.setdefault(row["reason"], row)
    for reason, count in sorted(counts.items()):
        example = examples[reason]
        lines.append(f"  {reason}: {count} (e.g. {example['key']}: {example.get('line', example.get('quality'))})")
    lines.extend(("", f"Findings: {len(report['findings'])}"))
    by_entity = Counter(finding.get("key", "render:").split(":", 1)[0] for finding in report["findings"])
    lines.extend(f"  {category}: {count}" for category, count in sorted(by_entity.items()))
    for finding in report["findings"]:
        lines.append("  " + " / ".join(str(finding[k]) for k in ("page", "key", "quality") if finding.get(k)))
        if "error" in finding:
            lines.append(f"    {finding['error']}")
        for change in finding.get("differences", []):
            for side in ("game", "wiki"):
                for line in change[side]:
                    text = "".join(
                        f"[{span['tone']}{' italic' if span['italic'] else ''}]{span['text']}" for span in line["spans"]
                    )
                    lines.append(f"    {side} {line['source']}.{line['field']}:{line['index']}: {text}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--wiki", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    paths = ParityPaths(args.root, args.database, args.wiki)
    report = compare(paths, args.base_url)
    latest = paths.output / "latest.json"
    write_json(latest, report)
    latest.with_suffix(".txt").write_text(summary(report))
    if report["complete"]:
        write_json(paths.report, report)
    print(f"Build {report['build']}: {report['coverage']}")
    print(f"Excluded identities: {len(report['exclusions'])}. Findings: {len(report['findings'])}. See {latest}.")
    if report["findings"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
