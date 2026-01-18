#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Exports game constants from GameData static fields.
/// These values affect game mechanics and differ between variants.
/// </summary>
public class GameConstantListener : IAssetScanListener<Object>
{
    private readonly SQLiteConnection _db;
    private readonly List<GameConstantRecord> _records = new();

    public GameConstantListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        Debug.Log($"[{GetType().Name}] Collecting GameData constants...");

        // Combat/Balance modifiers - these are the most important for comparing variants
        AddConstant("HPScale", GameData.HPScale, "NPC HP multiplier applied at spawn");
        AddConstant("ServerHPMod", GameData.ServerHPMod, "Server HP modifier (user adjustable)");
        AddConstant("ServerXPMod", GameData.ServerXPMod, "Server XP modifier");
        AddConstant("ServerDMGMod", GameData.ServerDMGMod, "Server damage modifier");
        AddConstant("ServerLootRate", GameData.ServerLootRate, "Server loot rate modifier");
        AddConstant("RespawnTimeMod", GameData.RespawnTimeMod, "Respawn time modifier");
        AddConstant("RunSpeedMod", GameData.RunSpeedMod, "Run speed modifier");

        // Feature flags - presence/absence indicates new features
        AddConstant("XPLossOnDeath", GameData.XPLossOnDeath, "Whether XP is lost on death");

        // DISABLED: Server settings only exist in playtest variant
        // TryAddConstant("NPCFlee", () => GameData.NPCFlee, "Whether NPCs can flee");
        // TryAddConstant("Jail", () => GameData.Jail, "Whether jail mechanic is enabled");
        // TryAddConstant("ServerPop", () => GameData.ServerPop, "Server population setting");
        // TryAddConstant("XPLock", () => GameData.XPLock, "XP lock level (0 = disabled)");

        Debug.Log($"[{GetType().Name}] Collected {_records.Count} constants");
    }

    public void OnScanFinished()
    {
        _db.CreateTable<GameConstantRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<GameConstantRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Object asset)
    {
        // This listener doesn't scan assets - all work is done in OnScanStarted
    }

    private void AddConstant(string key, float value, string? description = null)
    {
        _records.Add(new GameConstantRecord
        {
            Key = key,
            Value = value.ToString("G"),
            ValueType = "float",
            Description = description
        });
    }

    private void AddConstant(string key, int value, string? description = null)
    {
        _records.Add(new GameConstantRecord
        {
            Key = key,
            Value = value.ToString(),
            ValueType = "int",
            Description = description
        });
    }

    private void AddConstant(string key, bool value, string? description = null)
    {
        _records.Add(new GameConstantRecord
        {
            Key = key,
            Value = value ? "true" : "false",
            ValueType = "bool",
            Description = description
        });
    }

    /// <summary>
    /// Try to add a constant that may not exist in all game variants.
    /// Uses a delegate to handle fields that may not compile in older variants.
    /// </summary>
    private void TryAddConstant<T>(string key, System.Func<T> getter, string? description = null)
    {
        try
        {
            var value = getter();
            switch (value)
            {
                case float f:
                    AddConstant(key, f, description);
                    break;
                case int i:
                    AddConstant(key, i, description);
                    break;
                case bool b:
                    AddConstant(key, b, description);
                    break;
                default:
                    _records.Add(new GameConstantRecord
                    {
                        Key = key,
                        Value = value?.ToString() ?? "null",
                        ValueType = typeof(T).Name.ToLowerInvariant(),
                        Description = description
                    });
                    break;
            }
        }
        catch (System.Exception ex)
        {
            Debug.LogWarning($"[{GetType().Name}] Could not read {key}: {ex.Message}");
        }
    }
}
