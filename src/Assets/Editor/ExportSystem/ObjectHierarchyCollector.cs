#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

/// <summary>Captures referenced subjects, controller hosts, and their complete ancestry.</summary>
public sealed class ObjectHierarchyCollector : IAssetScanListener<Object>
{
    private readonly SQLiteConnection _db;
    private readonly Dictionary<string, ObjectHierarchyRecord> _records = new();

    public ObjectHierarchyCollector(SQLiteConnection db) => _db = db;

    public string Capture(GameObject target)
    {
        string key = ActivationTargetResolver.ObjectKey(target);
        for (var current = target.transform; current != null; current = current.parent)
        {
            string currentKey = ActivationTargetResolver.ObjectKey(current.gameObject);
            if (_records.ContainsKey(currentKey))
                break;
            _records.Add(
                currentKey,
                new ObjectHierarchyRecord
                {
                    ObjectKey = currentKey,
                    ParentObjectKey =
                        current.parent == null
                            ? null
                            : ActivationTargetResolver.ObjectKey(current.parent.gameObject),
                    Scene = current.gameObject.scene.name ?? "",
                    ActiveSelf = current.gameObject.activeSelf,
                    IsSceneObject =
                        current.gameObject.scene.IsValid()
                        && !PrefabUtility.IsPartOfPrefabAsset(current.gameObject),
                }
            );
        }
        return key;
    }

    public void OnAssetFound(Object asset) { }

    public void OnScanStarted() => _records.Clear();

    public void OnScanFinished()
    {
        _db.CreateTable<ObjectHierarchyRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ObjectHierarchyRecord>();
            _db.InsertAll(_records.Values);
        });
        _records.Clear();
    }
}
