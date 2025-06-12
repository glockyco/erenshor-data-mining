#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;

public class ItemListener : IAssetScanListener<Item>
{
    private readonly SQLiteConnection _db;
    private readonly List<ItemDBRecord> _records = new();

    private readonly WikiFancyWeaponFactory _weaponFactory;
    private readonly WikiFancyArmorFactory _armorFactory;

    private static readonly HashSet<string> WeaponSlots = new(StringComparer.OrdinalIgnoreCase)
    {
        "PrimaryOrSecondary", "Primary", "Secondary"
    };
    
    private static readonly HashSet<string> ArmorSlots = new(StringComparer.OrdinalIgnoreCase)
    {
        "Charm", "Head", "Neck", "Ring", "Hand", "Chest", "Arm", "Bracer", "Leg", "Waist", "Foot", "Back"
    };
    
    public ItemListener(SQLiteConnection db)
    {
        _db = db;
        _weaponFactory = new WikiFancyWeaponFactory(db);
        _armorFactory = new WikiFancyArmorFactory(db);
    }

    public void OnScanFinished()
    {
        foreach (var record in _records)
        {
            if (WeaponSlots.Contains(record.RequiredSlot))
            {
                record.WikiString = _weaponFactory.Create(record).ToString();
            }
            else if (ArmorSlots.Contains(record.RequiredSlot))
            {
                record.WikiString = _armorFactory.Create(record).ToString();
            }
            else
            {
                record.WikiString = "";
            }
        }
        
        _db.CreateTable<ItemDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ItemDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Item asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        int itemDbIndex = _records.Select(r => r.ItemDBIndex).Distinct().Count();

        _records.AddRange(CreateRecords(asset, itemDbIndex));
    }

    private List<ItemDBRecord> CreateRecords(Item item, int itemDbIndex)
    {
        var records = new List<ItemDBRecord>();

        // Determine if this item type should have quality variants
        bool hasQualityVariants =
            item.RequiredSlot != Item.SlotType.General &&
            item.Aura == null &&
            item.TeachSpell == null &&
            item.TeachSkill == null &&
            !item.Template;

        int maxQuality = hasQualityVariants ? 3 : 1;

        // Prepare common data that doesn't change with quality
        string classesString = "";
        if (item.Classes != null && item.Classes.Count > 0)
        {
            var classNames = item.Classes
                .Where(c => c != null && !string.IsNullOrEmpty(c.name))
                .Select(c => c.name);
            classesString = string.Join(", ", classNames);
        }

        string templateIngredientIds = "";
        if (item.TemplateIngredients != null && item.TemplateIngredients.Count > 0)
        {
            var ingredientIds = item.TemplateIngredients
                .Where(ing => ing != null && !string.IsNullOrEmpty(ing.Id))
                .Select(ing => ing.Id);
            templateIngredientIds = string.Join(", ", ingredientIds);
        }

        string templateRewardIds = "";
        if (item.TemplateRewards != null && item.TemplateRewards.Count > 0)
        {
            var rewardIds = item.TemplateRewards
                .Where(rew => rew != null && !string.IsNullOrEmpty(rew.Id))
                .Select(rew => rew.Id);
            templateRewardIds = string.Join(", ", rewardIds);
        }

        string? attackSound = null;
        if (item.AttackSound != null)
        {
            var path = AssetDatabase.GetAssetPath(item.AttackSound);
            attackSound = System.IO.Path.GetFileNameWithoutExtension(path);
        }
            
        string? itemIconName = null;
        if (item.ItemIcon != null)
        {
            var path = AssetDatabase.GetAssetPath(item.ItemIcon);
            itemIconName = System.IO.Path.GetFileNameWithoutExtension(path);
        }

        for (int quality = 1; quality <= maxQuality; quality++)
        {
            var record = new ItemDBRecord
            {
                // --- Core Identification ---
                ItemDBIndex = itemDbIndex,
                Id = $"{item.Id}_q{quality}", // Composite ID including quality
                BaseItemId = item.Id,
                ItemName = item.ItemName,
                Lore = item.Lore,

                // --- Classification & Requirements ---
                RequiredSlot = item.RequiredSlot.ToString(),
                ThisWeaponType = item.ThisWeaponType.ToString(),
                Classes = classesString,
                Quality = quality switch
                {
                    1 => "Normal",
                    2 => "Blessed",
                    3 => "Godly",
                    _ => quality.ToString() // Fallback, should not happen with maxQuality=3
                },
                ItemLevel = item.ItemLevel,

                // --- Core Stats (Affected by Quality) ---
                HP = item.CalcACHPMC(item.HP, quality),
                AC = item.CalcACHPMC(item.AC, quality),
                Mana = item.CalcACHPMC(item.Mana, quality),
                Str = item.CalcStat(item.Str, quality),
                End = item.CalcStat(item.End, quality),
                Dex = item.CalcStat(item.Dex, quality),
                Agi = item.CalcStat(item.Agi, quality),
                Int = item.CalcStat(item.Int, quality),
                Wis = item.CalcStat(item.Wis, quality),
                Cha = item.CalcStat(item.Cha, quality),
                Res = item.CalcRes(item.Res, quality), // Resonance
                MR = item.CalcStat(item.MR, quality), // Magic Resist
                ER = item.CalcStat(item.ER, quality), // Elemental Resist
                PR = item.CalcStat(item.PR, quality), // Poison Resist
                VR = item.CalcStat(item.VR, quality), // Void Resist

                // --- Weapon/Combat Properties ---
                WeaponDmg = item.WeaponDmg == 0 ? 0 : item.CalcDmg(item.WeaponDmg, quality),
                WeaponDly = item.WeaponDly,
                Shield = item.Shield,
                WeaponProcChance = item.WeaponProcChance,
                WeaponProcOnHit = item.WeaponProcOnHit is null ? string.Empty : $"{item.WeaponProcOnHit.SpellName} ({item.WeaponProcOnHit.Id})",
                
                // --- Wand Properties ---
                IsWand = item.IsWand,
                WandRange = item.IsWand ? item.WandRange : item.WeaponDmg > 0 ? 1 : 0,
                WandProcChance = item.WandProcChance,
                WandEffect = item.WandEffect is null ? string.Empty : $"{item.WandEffect.SpellName} ({item.WandEffect.Id})",

                // --- Effects & Interactions ---
                ItemEffectOnClick = item.ItemEffectOnClick is null ? string.Empty : $"{item.ItemEffectOnClick.SpellName} ({item.ItemEffectOnClick.Id})",
                ItemSkillUse = item.ItemSkillUse is null ? string.Empty : $"{item.ItemSkillUse.SkillName} ({item.ItemSkillUse.Id})",
                TeachSpell = item.TeachSpell is null ? string.Empty : $"{item.TeachSpell.SpellName} ({item.TeachSpell.Id})",
                TeachSkill = item.TeachSkill is null ? string.Empty : $"{item.TeachSkill.SkillName} ({item.TeachSkill.Id})",
                Aura = item.Aura is null ? string.Empty : $"{item.Aura.SpellName} ({item.Aura.Id})",
                WornEffect = item.WornEffect is null ? string.Empty : $"{item.WornEffect.SpellName} ({item.WornEffect.Id})",
                SpellCastTime = item.SpellCastTime,

                // --- Quest Interaction ---
                AssignQuestOnRead = item.AssignQuestOnRead?.DBName,
                CompleteOnRead = item.CompleteOnRead?.DBName,

                // --- Crafting & Templates ---
                Template = item.Template,
                TemplateIngredientIds = templateIngredientIds,
                TemplateRewardIds = templateRewardIds,

                // --- Economy & Inventory ---
                ItemValue = item.ItemValue,
                SellValue = Mathf.RoundToInt(item.ItemValue * 0.65f),
                Stackable = item.Stackable,
                Disposable = item.Disposable,
                Unique = item.Unique,
                Relic = item.Relic,

                // --- Miscellaneous ---
                BookTitle = item.BookTitle,
                Mining = item.Mining,
                FuelSource = item.FuelSource,
                FuelLevel = (int)item.FuelLevel,
                SimPlayersCantGet = item.SimPlayersCantGet,

                // --- Visuals & Sound ---
                AttackSoundName = attackSound,
                ItemIconName = itemIconName,
                EquipmentToActivate = item.EquipmentToActivate,
                //ShoulderTrimL = item.ShoulderTrimL,
                //ShoulderTrimR = item.ShoulderTrimR,
                //ElbowTrimL = item.ElbowTrimL,
                //ElbowTrimR = item.ElbowTrimR,
                //KneeTrimL = item.KneeTrimL,
                //KneeTrimR = item.KneeTrimR,
                HideHairWhenEquipped = item.HideHairWhenEquipped,
                HideHeadWhenEquipped = item.HideHeadWhenEquipped,
                // Colors
                //ItemPrimaryColorR = item.ItemPrimaryColor.r,
                //ItemPrimaryColorG = item.ItemPrimaryColor.g,
                //ItemPrimaryColorB = item.ItemPrimaryColor.b,
                //ItemPrimaryColorA = item.ItemPrimaryColor.a,
                //ItemSecondaryColorR = item.ItemSecondaryColor.r,
                //ItemSecondaryColorG = item.ItemSecondaryColor.g,
                //ItemSecondaryColorB = item.ItemSecondaryColor.b,
                //ItemSecondaryColorA = item.ItemSecondaryColor.a,
                //ItemMetalPrimaryR = item.ItemMetalPrimary.r,
                //ItemMetalPrimaryG = item.ItemMetalPrimary.g,
                //ItemMetalPrimaryB = item.ItemMetalPrimary.b,
                //ItemMetalPrimaryA = item.ItemMetalPrimary.a,
                //ItemLeatherPrimaryR = item.ItemLeatherPrimary.r,
                //ItemLeatherPrimaryG = item.ItemLeatherPrimary.g,
                //ItemLeatherPrimaryB = item.ItemLeatherPrimary.b,
                //ItemLeatherPrimaryA = item.ItemLeatherPrimary.a,
                //ItemMetalDarkR = item.ItemMetalDark.r,
                //ItemMetalDarkG = item.ItemMetalDark.g,
                //ItemMetalDarkB = item.ItemMetalDark.b,
                //ItemMetalDarkA = item.ItemMetalDark.a,
                //ItemMetalSecondaryR = item.ItemMetalSecondary.r,
                //ItemMetalSecondaryG = item.ItemMetalSecondary.g,
                //ItemMetalSecondaryB = item.ItemMetalSecondary.b,
                //ItemMetalSecondaryA = item.ItemMetalSecondary.a,
                //ItemLeatherSecondaryR = item.ItemLeatherSecondary.r,
                //ItemLeatherSecondaryG = item.ItemLeatherSecondary.g,
                //ItemLeatherSecondaryB = item.ItemLeatherSecondary.b,
                //ItemLeatherSecondaryA = item.ItemLeatherSecondary.a,

                // --- Internal ---
                ResourceName = item.name
            };
            records.Add(record);
        }

        return records;
    }
}