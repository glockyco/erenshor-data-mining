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
    private readonly List<ItemRecord> _itemRecords = new();
    private readonly List<ItemStatsRecord> _itemStatsRecords = new();
    private readonly List<ItemClassRecord> _itemClassRecords = new();
    private readonly List<CraftingRecipeRecord> _craftingRecipeRecords = new();
    private readonly List<CraftingRewardRecord> _craftingRewardRecords = new();

    private const float VendorBuybackPercentage = 0.65f;

    public ItemListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.RunInTransaction(() =>
        {
            _db.DropTable<ItemRecord>();
            _db.DropTable<ItemStatsRecord>();
            _db.DropTable<ItemClassRecord>();

            _db.CreateTable<ItemRecord>();
            _db.CreateTable<ItemStatsRecord>();
            _db.CreateTable<ItemClassRecord>();

            _db.InsertAll(_itemRecords);
            _db.InsertAll(_itemStatsRecords);
            _db.InsertAll(_itemClassRecords);
        });
        _itemRecords.Clear();
        _itemStatsRecords.Clear();
        _itemClassRecords.Clear();

        // Create and insert crafting tables after parent records are inserted
        _db.CreateTable<CraftingRecipeRecord>();
        _db.CreateTable<CraftingRewardRecord>();

        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<CraftingRecipeRecord>();
            _db.DeleteAll<CraftingRewardRecord>();

            _db.InsertAll(_craftingRecipeRecords);
            _db.InsertAll(_craftingRewardRecords);
        });
        _craftingRecipeRecords.Clear();
        _craftingRewardRecords.Clear();
    }

    public void OnAssetFound(Item asset)
    {
        int itemDbIndex = _itemRecords.Select(r => r.ItemDBIndex).Distinct().Count();

        _itemRecords.Add(CreateItemRecord(asset, itemDbIndex));
        _itemStatsRecords.AddRange(CreateItemStatsRecords(asset));
        _itemClassRecords.AddRange(CreateItemClassRecords(asset));
        _craftingRecipeRecords.AddRange(CreateCraftingRecipeRecords(asset));
        _craftingRewardRecords.AddRange(CreateCraftingRewardRecords(asset));
    }

    private ItemRecord CreateItemRecord(Item item, int itemDbIndex)
    {
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
        
        string? wandAttackSound = null;
        if (item.WandAttackSound != null)
        {
            var path = AssetDatabase.GetAssetPath(item.WandAttackSound);
            wandAttackSound = System.IO.Path.GetFileNameWithoutExtension(path);
        }
        
        string? bowAttackSound = null;
        if (item.BowAttackSound != null)
        {
            var path = AssetDatabase.GetAssetPath(item.BowAttackSound);
            bowAttackSound = System.IO.Path.GetFileNameWithoutExtension(path);
        }
            
        string? itemIconName = null;
        if (item.ItemIcon != null)
        {
            var path = AssetDatabase.GetAssetPath(item.ItemIcon);
            itemIconName = System.IO.Path.GetFileNameWithoutExtension(path);
        }

        var itemRecord = new ItemRecord
        {
            // --- Core Identification ---
            ItemDBIndex = itemDbIndex,
            Id = item.Id,
            ItemName = item.ItemName,
            Lore = item.Lore,

            // --- Classification & Requirements ---
            RequiredSlot = item.RequiredSlot.ToString(),
            ThisWeaponType = item.ThisWeaponType.ToString(),
            Classes = classesString,
            ItemLevel = item.ItemLevel,

            // --- Weapon/Combat Properties ---
            WeaponDly = item.WeaponDly,
            Shield = item.Shield,
            WeaponProcChance = item.WeaponProcChance,
            WeaponProcOnHit = item.WeaponProcOnHit?.name ?? string.Empty,

            // --- Wand Properties ---
            IsWand = item.IsWand,
            WandRange = item.IsWand ? item.WandRange : item.WeaponDmg > 0 ? 1 : 0,
            WandProcChance = item.WandProcChance,
            WandEffect = item.WandEffect?.name ?? string.Empty,
            WandBoltColorR = item.WandBoltColor.r,
            WandBoltColorG = item.WandBoltColor.g,
            WandBoltColorB = item.WandBoltColor.b,
            WandBoltColorA = item.WandBoltColor.a,
            WandBoltSpeed = item.WandBoltSpeed,
            WandAttackSoundName = wandAttackSound,
            
            // --- Bow Properties ---
            IsBow = item.IsBow,
            BowEffect = item.BowEffect?.name ?? string.Empty,
            BowProcChance = item.BowProcChance,
            BowRange = item.BowRange,
            BowArrowSpeed = item.BowArrowSpeed,
            BowAttackSoundName = bowAttackSound,

            // --- Effects & Interactions ---
            ItemEffectOnClick = item.ItemEffectOnClick?.name ?? string.Empty,
            ItemSkillUse = item.ItemSkillUse?.name ?? string.Empty,
            TeachSpell = item.TeachSpell?.name ?? string.Empty,
            TeachSkill = item.TeachSkill?.name ?? string.Empty,
            Aura = item.Aura?.name ?? string.Empty,
            WornEffect = item.WornEffect?.name ?? string.Empty,
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
            SellValue = Mathf.RoundToInt(item.ItemValue * VendorBuybackPercentage),
            Stackable = item.Stackable,
            Disposable = item.Disposable,
            Unique = item.Unique,
            Relic = item.Relic,
            NoTradeNoDestroy = item.NoTradeNoDestroy,

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

        return itemRecord;
    }

    private List<ItemStatsRecord> CreateItemStatsRecords(Item item)
    {
        var hasQualityVariants =
            item.RequiredSlot != Item.SlotType.General &&
            item.Aura == null &&
            item.TeachSpell == null &&
            item.TeachSkill == null &&
            !item.Template;

        var maxQuality = hasQualityVariants ? 3 : 1;

        var itemStatsRecords = new List<ItemStatsRecord>();
        for (var quality = 1; quality <= maxQuality; quality++)
        {
            var itemStatsRecord = new ItemStatsRecord
            {
                ItemResourceName = item.name,
                Quality = quality switch
                {
                    1 => "Normal",
                    2 => "Blessed",
                    3 => "Godly",
                    _ => quality.ToString() // Fallback, should not happen with maxQuality=3
                },

                WeaponDmg = item.WeaponDmg == 0 ? 0 : item.CalcDmg(item.WeaponDmg, quality),

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
                
                // --- Stat Scaling Properties ---
                StrScaling = item.StrScaling,
                EndScaling = item.EndScaling,
                DexScaling = item.DexScaling,
                AgiScaling = item.AgiScaling,
                IntScaling = item.IntScaling,
                WisScaling = item.WisScaling,
                ChaScaling = item.ChaScaling,
                ResistScaling = item.ResistScaling,
                MitigationScaling = item.MitigationScaling,
            };
            
            itemStatsRecords.Add(itemStatsRecord);
        }

        return itemStatsRecords;
    }

    private List<ItemClassRecord> CreateItemClassRecords(Item item)
    {
        var records = new List<ItemClassRecord>();

        if (item.Classes != null && item.Classes.Count > 0)
        {
            // Use HashSet to prevent duplicate ItemResourceName+ClassName combinations
            var uniqueClasses = new HashSet<string>();

            foreach (var characterClass in item.Classes)
            {
                if (characterClass != null && !string.IsNullOrEmpty(characterClass.name))
                {
                    // Only add if we haven't seen this class name for this item before
                    if (uniqueClasses.Add(characterClass.name))
                    {
                        records.Add(new ItemClassRecord
                        {
                            ItemResourceName = item.name,
                            ClassName = characterClass.name
                        });
                    }
                }
            }
        }

        return records;
    }

    /// <summary>
    /// Creates CraftingRecipeRecords from an item's template ingredients.
    /// Counts duplicate ingredients to determine quantities.
    /// </summary>
    private List<CraftingRecipeRecord> CreateCraftingRecipeRecords(Item item)
    {
        var records = new List<CraftingRecipeRecord>();

        if (item.TemplateIngredients == null || item.TemplateIngredients.Count == 0)
            return records;

        // Count occurrences to determine quantities
        var ingredientCounts = new Dictionary<string, int>();
        foreach (var ingredient in item.TemplateIngredients)
        {
            if (ingredient != null && !string.IsNullOrEmpty(ingredient.Id))
            {
                if (!ingredientCounts.ContainsKey(ingredient.Id))
                    ingredientCounts[ingredient.Id] = 0;
                ingredientCounts[ingredient.Id]++;
            }
        }

        // Create records with slot numbers
        int slot = 1;
        foreach (var kvp in ingredientCounts)
        {
            records.Add(new CraftingRecipeRecord
            {
                RecipeItemId = item.Id,
                MaterialSlot = slot,
                MaterialItemId = kvp.Key,
                MaterialQuantity = kvp.Value
            });
            slot++;
        }

        return records;
    }

    /// <summary>
    /// Creates CraftingRewardRecords from an item's template rewards.
    /// Counts duplicate rewards to determine quantities.
    /// </summary>
    private List<CraftingRewardRecord> CreateCraftingRewardRecords(Item item)
    {
        var records = new List<CraftingRewardRecord>();

        if (item.TemplateRewards == null || item.TemplateRewards.Count == 0)
            return records;

        // Count occurrences to determine quantities
        var rewardCounts = new Dictionary<string, int>();
        foreach (var reward in item.TemplateRewards)
        {
            if (reward != null && !string.IsNullOrEmpty(reward.Id))
            {
                if (!rewardCounts.ContainsKey(reward.Id))
                    rewardCounts[reward.Id] = 0;
                rewardCounts[reward.Id]++;
            }
        }

        // Create records with slot numbers
        int slot = 1;
        foreach (var kvp in rewardCounts)
        {
            records.Add(new CraftingRewardRecord
            {
                RecipeItemId = item.Id,
                RewardSlot = slot,
                RewardItemId = kvp.Key,
                RewardQuantity = kvp.Value
            });
            slot++;
        }

        return records;
    }
}