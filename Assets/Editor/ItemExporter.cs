using System;
using System.Collections.Generic;
using System.IO;
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
            { "itemCount", 0 },
            { "totalItems", 0 },
            { "completed", false }
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
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations, "Exported {0[itemCount]} items"),
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
        state["totalItems"] = items.Length;

        state["stage"] = "export_items";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.2f, $"Found {items.Length} items");
    }

    // Export a batch of items
    private void ExportItemsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        Item[] allItems = (Item[])state["items"];
        int itemIndex = (int)state["itemIndex"];
        int itemCount = (int)state["itemCount"];
        int totalItems = (int)state["totalItems"];

        // Process a larger batch of items for better performance
        int batchSize = 50;
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
                ItemDBRecord record = ExportItem(item);
                records.Add(record);
            }

            // Bulk insert all records at once
            foreach (var record in records)
            {
                db.Insert(record);
            }

            itemCount += records.Count;

            // Commit the transaction
            db.Commit();
        }
        catch (Exception ex)
        {
            // Rollback on error
            db.Rollback();
            Debug.LogError($"Error exporting items: {ex.Message}");
        }

        // Update state
        state["itemIndex"] = endIndex;
        state["itemCount"] = itemCount;

        // Calculate progress
        float progress = 0.2f + (0.8f * endIndex / totalItems);
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(progress, $"Exported {itemCount} items ({endIndex}/{totalItems})");

        // Check if all items have been processed
        if (endIndex >= allItems.Length)
        {
            // Mark the operation as completed
            state["completed"] = true;
        }
    }

    // Helper method to export an item to the database
    public ItemDBRecord ExportItem(Item item)
    {
        return new ItemDBRecord
        {
            Id = item.Id,
            ItemName = item.ItemName,
            ItemLevel = item.ItemLevel,
            HP = item.HP,
            AC = item.AC,
            Mana = item.Mana,
            WeaponDmg = item.WeaponDmg,
            WeaponDly = item.WeaponDly,
            Str = item.Str,
            End = item.End,
            Dex = item.Dex,
            Agi = item.Agi,
            Int = item.Int,
            Wis = item.Wis,
            Cha = item.Cha,
            Res = item.Res,
            MR = item.MR,
            ER = item.ER,
            PR = item.PR,
            VR = item.VR,
            RequiredSlot = (int)item.RequiredSlot,
            ThisWeaponType = (int)item.ThisWeaponType,
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
