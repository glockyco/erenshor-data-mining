using System;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SQLite;
using UnityEngine;

public class ItemExporter
{
    public const string ITEMS_PATH = "items";
    private readonly DatabaseManager _dbManager;

    public ItemExporter()
    {
        _dbManager = new DatabaseManager();
    }

    // Asynchronous version of ExportItemsToDB
    public void ExportItemsToDBAsync(DatabaseOperation.ProgressCallback progressCallback = null)
    {
        // Create a state object to track progress
        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DatabaseOperation.DB_PATH) },
            { "db", null },
            { "items", null },
            { "itemIndex", 0 },
            { "recordCount", 0 }, // Renamed from itemCount to reflect records generated
            { "totalBaseItems", 0 }, // Renamed from totalItems
            { "completed", false },
            { "progressCallback", progressCallback } // Store the callback
        };

        // Define the operations for each stage
        var stageOperations = new Dictionary<string, DatabaseManager.ExportOperation>
        {
            { "init", InitializeItemsDB },
            { "prepare_items", PrepareItems },
            { "export_items", ExportItemsBatch }
        };

        // Start the asynchronous operation
        _dbManager.ExportAsync(state,
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations, "Exported {0[recordCount]} item records"), // Updated message
            progressCallback);
    }

    // Initialize the database for items export
    private void InitializeItemsDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Create table for items
        db.CreateTable<ItemDBRecord>();

        // Clear existing item records
        db.DeleteAll<ItemDBRecord>();

        state["stage"] = "prepare_items";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.1f, "Database initialized");
    }

    // Prepare items data for export
    private void PrepareItems(SQLiteConnection db, Dictionary<string, object> state)
    {
        // Load all Item assets
        Item[] items = Resources.LoadAll<Item>(ITEMS_PATH);
        state["items"] = items;
        state["totalBaseItems"] = items.Length; // Store base item count

        state["stage"] = "export_items";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.2f, $"Found {items.Length} base items");
    }

    // Export a batch of items, including quality variants
    private void ExportItemsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        Item[] allItems = (Item[])state["items"];
        int itemIndex = (int)state["itemIndex"];
        int recordCount = (int)state["recordCount"];
        int totalBaseItems = (int)state["totalBaseItems"];

        // Process a batch of base items
        int batchSize = 20; // Reduced batch size slightly as we generate more records per item
        int endIndex = Math.Min(itemIndex + batchSize, allItems.Length);

        // Use a transaction for better performance
        db.BeginTransaction();

        try
        {
            // Create a list to hold records for bulk insert
            var records = new List<ItemDBRecord>();

            for (int i = itemIndex; i < endIndex; i++)
            {
                Item item = allItems[i];

                // Determine if this item type should have quality variants
                // Based on ItemInfoWindow logic: not general slot, not aura, not book, not template
                bool hasQualityVariants = item.RequiredSlot != Item.SlotType.General &&
                                          item.Aura == null &&
                                          item.TeachSpell == null &&
                                          item.TeachSkill == null &&
                                          !item.Template;

                int maxQuality = hasQualityVariants ? 3 : 1;

                for (int quality = 1; quality <= maxQuality; quality++)
                {
                    // Skip invalid base items (missing ID)
                    if (string.IsNullOrEmpty(item.Id))
                    {
                        Debug.LogWarning($"Skipping item '{item.name}' with missing ID.");
                        continue; // Skip this specific item entirely
                    }
                    // Pass the index 'i' to ExportItem
                    ItemDBRecord record = ExportItem(item, quality, i); // <-- Pass index 'i'
                    records.Add(record);
                }
            }

            // Bulk insert all records generated in this batch
            foreach (var record in records)
            {
                db.Insert(record);
            }

            recordCount += records.Count;

            // Commit the transaction
            db.Commit();
        }
        catch (Exception ex)
        {
            // Rollback on error
            db.Rollback();
            Debug.LogError($"Error exporting items batch (Base items {itemIndex}-{endIndex-1}): {ex.Message}\n{ex.StackTrace}");
            // Optionally re-throw or handle more gracefully
            // For now, we'll let the operation potentially continue with the next batch,
            // but the error is logged.
        }

        // Update state
        state["itemIndex"] = endIndex; // Progress based on base items processed
        state["recordCount"] = recordCount; // Update total records inserted

        // Calculate progress based on base items processed
        float progress = 0.2f + (0.8f * (float)endIndex / totalBaseItems);
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        // Update progress message to show base items processed
        callback?.Invoke(progress, $"Processed {endIndex}/{totalBaseItems} base items ({recordCount} records exported)");

        // Check if all base items have been processed
        if (endIndex >= allItems.Length)
        {
            // Mark the operation as completed
            state["completed"] = true;
        }
    }

    // Helper method to export an item to the database for a specific quality
    public ItemDBRecord ExportItem(Item item, int quality, int itemDbIndex)
    {
        string classesString = "";
        if (item.Classes != null && item.Classes.Count > 0)
        {
            var classNames = item.Classes
                .Where(c => c != null)
                .Select(c => c.name);
            classesString = string.Join(", ", classNames);
        }

        return new ItemDBRecord
        {
            Id = $"{item.Id}_q{quality}",
            BaseItemId = item.Id,
            Quality = quality,
            ItemDBIndex = itemDbIndex,
            ResourceName = item.name,
            ItemName = item.ItemName,
            ItemLevel = item.ItemLevel,
            Classes = classesString,
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
            RequiredSlot = item.RequiredSlot.ToString(),
            ThisWeaponType = item.ThisWeaponType.ToString(),
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
            BookTitle = item.BookTitle
        };
    }
}
