#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEditor;
using UnityEngine;

public class ClassStartingItemsListener : IAssetScanListener<CharSelectManager>
{
    private static readonly string[] ExpectedClassNames =
    {
        "Arcanist",
        "Paladin",
        "Duelist",
        "Druid",
        "Stormcaller",
        "Reaver",
    };

    private readonly SQLiteConnection _db;
    private readonly List<ClassStartingItemRecord> _records = new();
    private readonly HashSet<string> _sourceConfigurations = new(StringComparer.Ordinal);
    private readonly HashSet<string> _classesWithItems = new(StringComparer.Ordinal);
    private int _managerCount;
    private string? _validationFailure;

    public ClassStartingItemsListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnAssetFound(CharSelectManager manager)
    {
        _managerCount++;
        TrackSourceConfiguration(manager);

        Add("Arcanist", manager.ArcanistStart);
        Add("Paladin", manager.WarStart);
        Add("Duelist", manager.DueslistStart);
        Add("Druid", manager.DruidStart);
        Add("Stormcaller", manager.StormStart);
        Add("Reaver", manager.ReaverStart);
    }

    public void OnScanFinished()
    {
        ValidateConfiguration();

        _db.CreateTable<ClassStartingItemRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ClassStartingItemRecord>();
            _db.InsertAll(_records);
        });

        _records.Clear();
        _sourceConfigurations.Clear();
        _classesWithItems.Clear();
        _managerCount = 0;
        _validationFailure = null;
    }

    private void TrackSourceConfiguration(CharSelectManager manager)
    {
        string scenePath = manager.gameObject.scene.path;
        if (!string.IsNullOrEmpty(scenePath))
        {
            _sourceConfigurations.Add($"scene:{scenePath}");
            return;
        }

        string prefabPath = AssetDatabase.GetAssetPath(manager.gameObject);
        if (!string.IsNullOrEmpty(prefabPath))
        {
            _sourceConfigurations.Add($"prefab:{prefabPath}");
            return;
        }

        _validationFailure ??= "CharSelectManager has no scene or prefab source path";
    }

    private void Add(string className, List<Item>? items)
    {
        if (items == null || items.Count == 0)
        {
            _validationFailure ??= $"{className} has no configured starting items";
            return;
        }

        for (int sortOrder = 0; sortOrder < items.Count; sortOrder++)
        {
            Item item = items[sortOrder];
            if (item == null)
            {
                _validationFailure ??=
                    $"{className} has a null starting item at position {sortOrder}";
                return;
            }

            _records.Add(
                new ClassStartingItemRecord
                {
                    ClassName = className,
                    SortOrder = sortOrder,
                    ItemStableKey = StableKeyGenerator.ForItem(item),
                }
            );
        }

        _classesWithItems.Add(className);
    }

    private void ValidateConfiguration()
    {
        if (_validationFailure != null)
        {
            throw new InvalidOperationException(_validationFailure);
        }

        if (_managerCount != 1 || _sourceConfigurations.Count != 1)
        {
            throw new InvalidOperationException(
                $"Expected exactly one CharSelectManager source configuration, found "
                    + $"{_managerCount} manager(s) across {_sourceConfigurations.Count} source(s): "
                    + $"{string.Join(", ", _sourceConfigurations)}"
            );
        }

        foreach (string className in ExpectedClassNames)
        {
            if (!_classesWithItems.Contains(className))
            {
                throw new InvalidOperationException($"{className} has no exported starting items");
            }
        }
    }
}
