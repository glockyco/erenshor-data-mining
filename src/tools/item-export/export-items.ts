#!/usr/bin/env bun
/**
 * Export the entire Erenshor ItemDB from the running game via HotRepl to a
 * full-fidelity JSON artifact. Every non-null ItemDB entry is included; the
 * render pass derives any filtered views (e.g. "new gear") from it.
 *
 * Bulk data leaves the game through paged eval calls (<= PAGE_SIZE rows each)
 * so we never hit HotRepl's per-result caps (100 elements / ~100 KB). Each page
 * is a self-contained C# snippet: no persistent REPL state, no LINQ, and rows
 * cross the WebSocket as native JSON (no Wine/bottle path translation — the JSON
 * is written natively here on the host).
 *
 * Usage:
 *   bun export-items.ts [--out path.json] [--url ws://127.0.0.1:18590]
 *
 * Default output is out/items-<UTC timestamp>.json: each export keeps a distinct,
 * sortable filename so earlier snapshots stay available as render --since baselines.
 *
 * Prerequisite: the game is running with the HotRepl plugin loaded AND a
 * character/world is loaded (so GameData.ItemDB is populated).
 */
import { connect, HotReplError } from "@hotrepl/sdk";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExportFile, ItemRow } from "./types";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
/** < 100-element cap; keeps each serialized page well under the ~100 KB cap. */
const PAGE_SIZE = 50;

/** Filename-safe, lexicographically sortable UTC timestamp: YYYYMMDD-HHMMSS. */
function stamp(d: Date): string {
  const p = (n: number): string => String(n).padStart(2, "0");
  return (
    `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}-` +
    `${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}`
  );
}

interface Args {
  out: string | undefined;
  url: string;
}

function parseArgs(argv: string[]): Args {
  let out: string | undefined;
  let url = process.env.HOTREPL_URL ?? "ws://127.0.0.1:18590";
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--out") out = argv[++i];
    else if (a === "--url") url = argv[++i] ?? url;
    else throw new Error(`Unknown argument: ${a}`);
  }
  return { out: out ? resolve(out) : undefined, url };
}

/** C# expression: count of non-null ItemDB entries. */
const COUNT_CODE = `
var __db = GameData.ItemDB.ItemDB;
int __n = 0;
for (int __i = 0; __i < __db.Length; __i++) { if (__db[__i] != null) __n++; }
__n
`;

/**
 * C# expression returning non-null ItemDB entries [off, off+page) as a
 * List<Dictionary<string,object>>, which the server serializes to native JSON.
 * "index" is the ItemDB array position (the /additem argument).
 */
const pageCode = (off: number, page: number): string => `
var __db = GameData.ItemDB.ItemDB;
var __out = new System.Collections.Generic.List<System.Collections.Generic.Dictionary<string, object>>();
int __seen = 0;
for (int __i = 0; __i < __db.Length; __i++) {
  var __it = __db[__i];
  if (__it == null) continue;
  if (__seen >= ${off} && __seen < ${off + page}) {
    string[] __cls;
    if (__it.Classes == null) { __cls = new string[0]; }
    else {
      __cls = new string[__it.Classes.Count];
      for (int __c = 0; __c < __it.Classes.Count; __c++) {
        __cls[__c] = __it.Classes[__c] == null ? "" : __it.Classes[__c].ClassName;
      }
    }
    __out.Add(new System.Collections.Generic.Dictionary<string, object> {
      { "index", __i },
      { "id", __it.Id },
      { "name", __it.name },
      { "itemName", __it.ItemName },
      { "itemLevel", __it.ItemLevel },
      { "slot", __it.RequiredSlot.ToString() },
      { "weaponType", __it.ThisWeaponType.ToString() },
      { "weaponDmg", __it.WeaponDmg },
      { "weaponDly", __it.WeaponDly },
      { "hp", __it.HP },
      { "ac", __it.AC },
      { "mana", __it.Mana },
      { "str", __it.Str },
      { "end", __it.End },
      { "dex", __it.Dex },
      { "agi", __it.Agi },
      { "int", __it.Int },
      { "wis", __it.Wis },
      { "cha", __it.Cha },
      { "res", __it.Res },
      { "mr", __it.MR },
      { "er", __it.ER },
      { "pr", __it.PR },
      { "vr", __it.VR },
      { "value", __it.ItemValue },
      { "shield", __it.Shield },
      { "isWand", __it.IsWand },
      { "isBow", __it.IsBow },
      { "unique", __it.Unique },
      { "relic", __it.Relic },
      { "rare", __it.RareItem },
      { "noTrade", __it.NoTradeNoDestroy },
      { "classes", __cls }
    });
  }
  __seen++;
}
__out
`;

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  console.log(`Connecting to HotRepl at ${args.url} ...`);
  let session;
  try {
    session = await connect({ url: args.url });
  } catch (cause) {
    const detail = cause instanceof Error ? cause.message : String(cause);
    throw new Error(
      `Could not connect to HotRepl at ${args.url}. Is the game running with the ` +
        `HotRepl plugin loaded? (${detail})`,
    );
  }

  try {
    const product = (await session.eval<string>("UnityEngine.Application.productName")).value ?? "";
    const version = (await session.eval<string>("UnityEngine.Application.version")).value ?? "";
    console.log(`Connected: ${product} ${version}`);

    const dbLen =
      (
        await session.eval<number>(
          "GameData.ItemDB == null || GameData.ItemDB.ItemDB == null ? -1 : GameData.ItemDB.ItemDB.Length",
        )
      ).value ?? -1;
    if (dbLen < 0) {
      throw new Error(
        "GameData.ItemDB is not populated. Load a character/world in-game, then retry.",
      );
    }
    console.log(`ItemDB has ${dbLen} entries.`);

    const count = (await session.eval<number>(COUNT_CODE)).value ?? 0;
    console.log(`Non-null items: ${count}`);

    const items: ItemRow[] = [];
    for (let off = 0; off < count; off += PAGE_SIZE) {
      const res = await session.eval<ItemRow[]>(pageCode(off, PAGE_SIZE));
      if (res.truncated) {
        throw new Error(
          `Page at offset ${off} was truncated at ${res.truncatedBytes ?? "?"} bytes; lower PAGE_SIZE.`,
        );
      }
      items.push(...(res.value ?? []));
      console.log(`  fetched ${items.length}/${count}`);
    }

    if (items.length !== count) {
      console.warn(
        `Warning: expected ${count} rows but assembled ${items.length}. ` +
          "Game state may have changed mid-export.",
      );
    }

    const now = new Date();
    const outPath =
      args.out ?? resolve(SCRIPT_DIR, "out", `items-${stamp(now)}.json`);
    const out: ExportFile = {
      generatedAt: now.toISOString(),
      source: args.url,
      productName: product,
      gameVersion: version,
      scope: "all ItemDB entries",
      count: items.length,
      items,
    };
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, `${JSON.stringify(out, null, 2)}\n`);
    console.log(`Wrote ${items.length} items to ${outPath}`);
    console.log(`Next: bun render-items.ts --since <previous-export.json>`);
  } finally {
    session.close();
  }
}

main().catch((err: unknown) => {
  if (err instanceof HotReplError) {
    console.error(`HotRepl error [${err.kind}/${err.code}]: ${err.message}`);
  } else if (err instanceof Error) {
    console.error(err.message);
  } else {
    console.error(String(err));
  }
  process.exit(1);
});
