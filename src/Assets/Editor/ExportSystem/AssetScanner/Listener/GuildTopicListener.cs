#nullable enable

using System.Collections.Generic;
using Newtonsoft.Json;
using SQLite;
using UnityEditor;
using UnityEngine;

public class GuildTopicListener : IAssetScanListener<GuildTopic>
{
    private readonly SQLiteConnection _db;
    private readonly List<GuildTopicRecord> _records = new();

    public GuildTopicListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<GuildTopicRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<GuildTopicRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(GuildTopic asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var assetPath = AssetDatabase.GetAssetPath(asset);

        var record = new GuildTopicRecord
        {
            StableKey = StableKeyGenerator.ForGuildTopic(asset, assetPath),
            GuildTopicDBIndex = _records.Count,
            Id = asset.Id,
            ActivationWords = asset.ActivationWords != null ? JsonConvert.SerializeObject(asset.ActivationWords) : "[]",
            Responses = asset.Responses != null ? JsonConvert.SerializeObject(asset.Responses) : "[]",
            RelevantScenes = asset.RelevantScene != null ? JsonConvert.SerializeObject(asset.RelevantScene) : "[]",
            RequiredLevelToKnow = asset.RequiredLevelToKnow,
            ResourceName = asset.name
        };

        _records.Add(record);
    }
}
