/** One exported gear item. Field set mirrors the in-game `Item` ScriptableObject. */
export interface ItemRow {
  /** ItemDB array index — the argument to the in-game `/additem <#>` command. */
  index: number;
  /** Item.Id: stable string id used by ItemDatabase.GetItemByID. */
  id: string;
  /** Unity asset name (Object.name). */
  name: string;
  /** In-game display name (Item.ItemName). */
  itemName: string;
  itemLevel: number;
  /** RequiredSlot enum name (e.g. "Head", "Primary", "Charm"). */
  slot: string;
  /** ThisWeaponType enum name; "None" for non-weapons. */
  weaponType: string;
  weaponDmg: number;
  weaponDly: number;
  hp: number;
  ac: number;
  mana: number;
  str: number;
  end: number;
  dex: number;
  agi: number;
  int: number;
  wis: number;
  cha: number;
  res: number;
  mr: number;
  er: number;
  pr: number;
  vr: number;
  value: number;
  shield: boolean;
  isWand: boolean;
  isBow: boolean;
  unique: boolean;
  relic: boolean;
  rare: boolean;
  noTrade: boolean;
  /** Class restrictions by ClassName; empty means no class restriction. */
  classes: string[];
}

/** The JSON artifact written by export-items.ts and consumed by render-items.ts. */
export interface ExportFile {
  generatedAt: string;
  source: string;
  productName: string;
  gameVersion: string;
  scope: string;
  count: number;
  items: ItemRow[];
}
