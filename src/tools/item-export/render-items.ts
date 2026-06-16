#!/usr/bin/env bun
/**
 * Render an exported ItemDB JSON artifact to Markdown. Up to three sections:
 *   1. New equipment since a specified previous export (--since): gear whose
 *      Item.Id is absent from that baseline export — the "what this update added"
 *      diff. Omitted unless --since is given.
 *   2. New equipment in playtest: gear within an item-level window, excluding
 *      items already present in another variant's DB — the curated "what's new".
 *   3. Every ItemDB entry, sorted by index — the complete /additem reference.
 *
 * The presentation pass — never touches the game, never mutates the JSON, so the
 * export stays the complete full-fidelity data set while these views can be
 * filtered/projected freely.
 *
 * Usage:
 *   bun render-items.ts [--in items-<stamp>.json] [--out items.md] \
 *     [--min 38] [--max 50] [--exclude-db variant.sqlite] \
 *     [--since previous-export.json]
 *
 *   --min N / --max N  playtest section item-level window: min <= itemLevel < max.
 *   --exclude-db PATH  drop playtest gear whose Item.Id already exists in that
 *                      variant's clean SQLite DB (keep only gear new to this export).
 *   --since PATH       diff against a previous export's Item.Ids for section 1.
 *
 * Defaults: --in is the newest out/items-*.json; --out is the sibling .md.
 */
import { Database } from "bun:sqlite";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExportFile, ItemRow } from "./types";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));

/** Newest out/items-*.json (timestamped filenames sort chronologically). */
function latestExport(): string {
  const dir = resolve(SCRIPT_DIR, "out");
  const latest = readdirSync(dir)
    .filter((f) => /^items-.*\.json$/.test(f))
    .sort()
    .at(-1);
  if (!latest) throw new Error(`No items-*.json exports in ${dir}; run export-items.ts first.`);
  return resolve(dir, latest);
}

interface Args {
  in: string;
  out: string;
  min: number;
  max: number;
  excludeDb: string | undefined;
  since: string | undefined;
}

function parseArgs(argv: string[]): Args {
  let input: string | undefined;
  let out: string | undefined;
  let min = 38;
  let max = Number.POSITIVE_INFINITY;
  let excludeDb: string | undefined;
  let since: string | undefined;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--in") input = argv[++i];
    else if (a === "--out") out = argv[++i];
    else if (a === "--min") min = Number(argv[++i]);
    else if (a === "--max") max = Number(argv[++i]);
    else if (a === "--exclude-db") excludeDb = argv[++i];
    else if (a === "--since") since = argv[++i];
    else throw new Error(`Unknown argument: ${a}`);
  }
  if (Number.isNaN(min) || Number.isNaN(max)) throw new Error("--min/--max must be numbers");
  const resolvedIn = input ? resolve(input) : latestExport();
  return {
    in: resolvedIn,
    out: out ? resolve(out) : resolvedIn.replace(/\.json$/, ".md"),
    min,
    max,
    excludeDb: excludeDb ? resolve(excludeDb) : undefined,
    since: since ? resolve(since) : undefined,
  };
}

/** The set of Item.Ids present in a variant's clean items table. */
function loadDbIds(dbPath: string): Set<string> {
  const db = new Database(dbPath, { readonly: true });
  try {
    const rows = db
      .query<{ id: string }>("SELECT id FROM items WHERE id IS NOT NULL AND id != ''")
      .all();
    return new Set(rows.map((r) => r.id));
  } finally {
    db.close();
  }
}

/** Escape Markdown table delimiters in text cells. */
const cell = (v: string): string => v.replace(/\|/g, "\\|");

/** Slot/weapon label; Wand/Bow/Shield replace the raw weapon type for readers. */
function typeCell(it: ItemRow): string {
  if (it.isWand) return "Wand";
  if (it.isBow) return "Bow";
  if (it.shield) return "Shield";
  return it.weaponType === "None" ? "" : it.weaponType;
}

const isGear = (it: ItemRow): boolean => it.slot !== "General";

const SLOT_ORDER = [
  "Head", "Neck", "Shoulder", "Chest", "Back", "Arm", "Bracer", "Hand",
  "Waist", "Leg", "Foot", "Ring", "Charm", "Aura",
  "Primary", "Secondary", "PrimaryOrSecondary",
];

const slotRank = (slot: string): number => {
  const i = SLOT_ORDER.indexOf(slot);
  return i === -1 ? SLOT_ORDER.length : i;
};

/** Section comparator: logical slot order, then displayed name. */
const bySlotThenName = (a: ItemRow, b: ItemRow): number =>
  slotRank(a.slot) - slotRank(b.slot) ||
  (a.itemName || a.name).localeCompare(b.itemName || b.name);

const HEADERS = ["#", "Item", "iLvl", "Slot", "Type", "Classes"];

function row(it: ItemRow): string {
  const cells: Array<string | number> = [
    it.index,
    cell(it.itemName || it.name),
    it.itemLevel,
    cell(it.slot),
    cell(typeCell(it)),
    cell(it.classes.join(", ")),
  ];
  return `| ${cells.join(" | ")} |`;
}

function table(items: ItemRow[]): string[] {
  return [
    `| ${HEADERS.join(" | ")} |`,
    `| ${HEADERS.map(() => "---").join(" | ")} |`,
    ...items.map(row),
  ];
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const data = JSON.parse(readFileSync(args.in, "utf8")) as ExportFile;
  const excludeIds = args.excludeDb ? loadDbIds(args.excludeDb) : null;

  // Section 1 (optional): equipment new since a specified previous export.
  let sinceLines: string[] = [];
  let sinceCount = 0;
  if (args.since) {
    const prev = JSON.parse(readFileSync(args.since, "utf8")) as ExportFile;
    const prevIds = new Set(prev.items.map((it) => it.id));
    const newGear = data.items
      .filter((it) => isGear(it) && !prevIds.has(it.id))
      .sort(bySlotThenName);
    sinceCount = newGear.length;
    sinceLines = [
      "## New Equipment Since Previous Export",
      "",
      `Compared against \`${basename(args.since)}\` (exported ${prev.generatedAt}).`,
      "",
      ...table(newGear),
      "",
    ];
  }

  // Section 2: new equipment in playtest within the item-level window.
  const gear = data.items
    .filter((it) => isGear(it) && it.itemLevel >= args.min && it.itemLevel < args.max)
    .filter((it) => excludeIds === null || !excludeIds.has(it.id))
    .sort(bySlotThenName);

  // Section 3: every ItemDB entry, sorted by index.
  const all = [...data.items].sort((a, b) => a.index - b.index);

  const lines = [
    "# Erenshor Items",
    "",
    `Exported ${data.generatedAt}. The **#** column is the item's \`ItemDB\` index — the argument to the in-game \`/additem <#>\` command.`,
    "",
    ...sinceLines,
    "## New Equipment in Playtest",
    "",
    ...table(gear),
    "",
    "## All Items",
    "",
    ...table(all),
    "",
  ];

  writeFileSync(args.out, lines.join("\n"));
  const sinceMsg = args.since ? `${sinceCount} new + ` : "";
  console.log(`Wrote ${sinceMsg}${gear.length} gear + ${all.length} all items to ${args.out}`);
}

main();
