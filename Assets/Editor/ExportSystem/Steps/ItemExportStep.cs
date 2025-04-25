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
        // This needs to run on the main thread implicitly or explicitly if needed.
        // In Editor scripts, Resources.LoadAll is generally safe outside play mode.
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
                    Debug.LogError($"Error inserting item batch (around base item index {i}): {ex.Message}");
                    reporter.Report((float)processedBaseItems / totalBaseItems, $"Error inserting batch: {ex.Message}");
                    throw;
                }

                // --- Progress Reporting (Based on base items processed) ---
                float progress = (float)processedBaseItems / totalBaseItems;
                reporter.Report(progress, $"Exported {totalRecordCount} item records ({processedBaseItems}/{totalBaseItems} base items)...");
                await Task.Yield();
            }
            else if (processedBaseItems == totalBaseItems)
            {
                 reporter.Report(1.0f, $"Exported {totalRecordCount} item records ({processedBaseItems}/{totalBaseItems} base items)...");
            }
        }
    }

    // Helper method to generate records for an item and its quality variants (Adapted from ItemExporter)
    private List<ItemDBRecord> ExportItemVariants(Item item, int itemDbIndex)
    {
        var records = new List<ItemDBRecord>();

        // Skip invalid base items (missing ID)
        if (string.IsNullOrEmpty(item.Id))
        {
            Debug.LogWarning($"Skipping item '{item.name}' with missing ID.");
            return records; // Return empty list
        }

        // Determine if this item type should have quality variants
        bool hasQualityVariants = item.RequiredSlot != Item.SlotType.General &&
                                  item.Aura == null &&
                                  item.TeachSpell == null &&
                                  item.TeachSkill == null &&
                                  !item.Template;

        int maxQuality = hasQualityVariants ? 3 : 1;

        for (int quality = 1; quality <= maxQuality; quality++)
        {
            string classesString = "";
            if (item.Classes != null && item.Classes.Count > 0)
            {
                var classNames = item.Classes
                    .Where(c => c != null)
                    .Select(c => c.name);
                classesString = string.Join(", ", classNames);
            }

            var record = new ItemDBRecord
            {
                ItemDBIndex = itemDbIndex,
                Id = $"{item.Id}_q{quality}", // Composite ID including quality
                BaseItemId = item.Id,
                ItemName = item.ItemName,
                RequiredSlot = item.RequiredSlot.ToString(),
                ThisWeaponType = item.ThisWeaponType.ToString(),
                Classes = classesString,
                Quality = quality switch
                {
                    1 => "Normal",
                    2 => "Blessed",
                    3 => "Godly",
                    _ => quality.ToString() // Should not happen with maxQuality=3
                },
                ItemLevel = item.ItemLevel,
                HP = item.CalcACHPMC(item.HP, quality),
                AC = item.CalcACHPMC(item.AC, quality),
                Mana = item.CalcACHPMC(item.Mana, quality),
                WeaponDmg = item.CalcDmg(item.WeaponDmg, quality),
                WeaponDly = item.WeaponDly,
                Str = item.CalcStat(item.Str, quality),
                End = item.CalcStat(item.End, quality),
                Dex = item.CalcStat(item.Dex, quality),
                Agi = item.CalcStat(item.Agi, quality),
                Int = item.CalcStat(item.Int, quality),
                Wis = item.CalcStat(item.Wis, quality),
                Cha = item.CalcStat(item.Cha, quality),
                Res = item.CalcRes(item.Res, quality),
                MR = item.CalcStat(item.MR, quality),
                ER = item.CalcStat(item.ER, quality),
                PR = item.CalcStat(item.PR, quality),
                VR = item.CalcStat(item.VR, quality),
                ItemValue = item.ItemValue,
                Lore = item.Lore,
                Shield = item.Shield,
                WeaponProcChance = item.WeaponProcChance,
                SpellCastTime = item.SpellCastTime,
                HideHairWhenEquipped = item.HideHairWhenEquipped,
                HideHeadWhenEquipped = item.HideHeadWhenEquipped,
                Stackable = item.Stackable,
                Disposable = item.Disposable,
                Unique = item.Unique,
                Mining = item.Mining,
                FuelSource = item.FuelSource,
                Template = item.Template,
                SimPlayersCantGet = item.SimPlayersCantGet,
                FuelLevel = (int)item.FuelLevel,
                Relic = item.Relic,
                BookTitle = item.BookTitle,
                ResourceName = item.name // Store the ScriptableObject's name
            };
            records.Add(record);
        }
        return records;
    }
}
