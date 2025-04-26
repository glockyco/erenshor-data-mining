using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEngine;

public class ItemExportStep : IExportStep
{
    public const string ITEMS_PATH = "items"; // Path within Resources folder

    // --- Metadata ---
    public string StepName => "Items";
    public float ProgressWeight => 2.0f; // Items can generate multiple records

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(ItemDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Loading item assets...");

        // --- Data Fetching (Unity API - Resources.LoadAll) ---
        Item[] allItems = Resources.LoadAll<Item>(ITEMS_PATH);
        int totalBaseItems = allItems.Length;

        if (totalBaseItems == 0)
        {
            reporter.Report(1f, "No item assets found.");
            return;
        }

        reporter.Report(0.05f, $"Found {totalBaseItems} base items. Exporting variants...");
        await Task.Yield(); // Allow UI update

        // --- Processing & DB Interaction ---
        int batchSize = 50; // Records per batch (adjust as needed)
        var batchRecords = new List<ItemDBRecord>();
        int processedBaseItems = 0;
        int totalRecordCount = 0;

        for (int i = 0; i < totalBaseItems; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            Item item = allItems[i];
            if (item == null) continue; // Skip null items in the array

            // --- Extraction Logic (Specific to this step, including variants) ---
            List<ItemDBRecord> itemRecords = ExportItemVariants(item, i); // Use helper, pass index 'i'
            batchRecords.AddRange(itemRecords);

            processedBaseItems++;

            // --- Batch Insertion ---
            // Insert when batch is full OR it's the last base item and there are records pending
            if (batchRecords.Count >= batchSize || (processedBaseItems == totalBaseItems && batchRecords.Count > 0))
            {
                try
                {
                    db.RunInTransaction(() =>
                    {
                        // Use Insert, assuming ItemDBRecord's PK (Id + Quality) is unique per batch
                        // If duplicates are possible across batches (unlikely with quality suffix), use InsertOrReplaceAll
                        db.InsertAll(batchRecords);
                    });
                    totalRecordCount += batchRecords.Count;
                    batchRecords.Clear();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error inserting item batch (around base item index {i}, ID: {item?.Id ?? "N/A"}): {ex.Message}\n{ex.StackTrace}");
                    reporter.Report((float)processedBaseItems / totalBaseItems, $"Error inserting batch: {ex.Message}");
                    // Decide whether to re-throw or continue processing other items
                    // For now, re-throwing to halt the export on error.
                    throw;
                }

                // --- Progress Reporting (Based on base items processed) ---
                float progress = (float)processedBaseItems / totalBaseItems;
                reporter.Report(progress, $"Exported {totalRecordCount} item records ({processedBaseItems}/{totalBaseItems} base items)...");
                await Task.Yield();
            }
            else if (processedBaseItems == totalBaseItems) // Ensure final report if last item didn't fill a batch
            {
                 reporter.Report(1.0f, $"Exported {totalRecordCount} item records ({processedBaseItems}/{totalBaseItems} base items)...");
            }
        }
         // Final report in case the loop finishes exactly on a batch boundary
        if (processedBaseItems == totalBaseItems && totalRecordCount > 0) {
             reporter.Report(1.0f, $"Exported {totalRecordCount} item records ({processedBaseItems}/{totalBaseItems} base items)...");
        }
    }

    // Helper method to generate records for an item and its quality variants
    private List<ItemDBRecord> ExportItemVariants(Item item, int itemDbIndex)
    {
        var records = new List<ItemDBRecord>();

        // Skip invalid base items (missing ID or name)
        if (string.IsNullOrEmpty(item.Id))
        {
            Debug.LogWarning($"Skipping item '{item.name}' with missing ID.");
            return records; // Return empty list
        }
         if (string.IsNullOrEmpty(item.name))
        {
            Debug.LogWarning($"Skipping item with ID '{item.Id}' because it has no ScriptableObject name (ResourceName).");
            return records; // Return empty list
        }


        // Determine if this item type should have quality variants
        bool hasQualityVariants = item.RequiredSlot != Item.SlotType.General &&
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
                .Where(c => c != null && !string.IsNullOrEmpty(c.name)) // Ensure class and its name exist
                .Select(c => c.name);
            classesString = string.Join(", ", classNames);
        }

        string templateIngredientIds = "";
        if (item.TemplateIngredients != null && item.TemplateIngredients.Count > 0)
        {
            var ingredientIds = item.TemplateIngredients
                .Where(ing => ing != null && !string.IsNullOrEmpty(ing.Id)) // Ensure ingredient and its ID exist
                .Select(ing => ing.Id);
            templateIngredientIds = string.Join(", ", ingredientIds);
        }

        string templateRewardIds = "";
        if (item.TemplateRewards != null && item.TemplateRewards.Count > 0)
        {
            var rewardIds = item.TemplateRewards
                .Where(rew => rew != null && !string.IsNullOrEmpty(rew.Id)) // Ensure reward and its ID exist
                .Select(rew => rew.Id);
            templateRewardIds = string.Join(", ", rewardIds);
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
                WeaponDmg = item.CalcDmg(item.WeaponDmg, quality),
                WeaponDly = item.WeaponDly,
                Shield = item.Shield,
                WeaponProcChance = item.WeaponProcChance,
                WeaponProcOnHitId = item.WeaponProcOnHit?.Id, // Store Id if Spell exists

                // --- Effects & Interactions ---
                ItemEffectOnClickId = item.ItemEffectOnClick?.Id,
                ItemSkillUseId = item.ItemSkillUse?.Id,
                TeachSpellId = item.TeachSpell?.Id,
                TeachSkillId = item.TeachSkill?.Id,
                AuraId = item.Aura?.Id,
                WornEffectId = item.WornEffect?.Id,
                SpellCastTime = item.SpellCastTime,

                // --- Quest Interaction ---
                AssignQuestOnRead = item.AssignQuestOnRead?.DBName,
                CompleteOnRead = item.CompleteOnRead?.DBName,

                // --- Crafting & Templates ---
                Template = item.Template,
                TemplateIngredientIds = templateIngredientIds, // Use pre-calculated string
                TemplateRewardIds = templateRewardIds, // Use pre-calculated string

                // --- Economy & Inventory ---
                ItemValue = item.ItemValue,
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
                AttackSoundName = item.AttackSound != null ? item.AttackSound.name : null,
                ItemIconName = item.ItemIcon != null ? item.ItemIcon.name : null,
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
                ResourceName = item.name // Store the ScriptableObject's name
            };
            records.Add(record);
        }
        return records;
    }
}
