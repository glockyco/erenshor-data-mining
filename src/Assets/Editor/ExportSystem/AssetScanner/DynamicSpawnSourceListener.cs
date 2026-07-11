#nullable enable

using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using SQLite;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

public class DynamicSpawnSourceListener : IAssetScanListener<MonoBehaviour>
{
    private const string VithArenaFightPositionStrategy = "vith_arena_fight";
    private const string VitheoFightPositionStrategy = "vitheo_fight";

    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly DynamicSpawnCatalog _catalog;
    private readonly DynamicSpawnErrorEnvelope _envelope = new();
    private readonly List<DynamicCharacterSpawnRecord> _spawnRecords = new();
    private readonly List<CharacterChainedSpawnRecord> _chainedRecords = new();

    public DynamicSpawnErrorEnvelope Envelope => _envelope;

    private bool _hasErrors = false;
    public bool HasErrors => _hasErrors;

    private struct ResolvedCharacterSpawn
    {
        public Character Character;
        public Vector3 Position;
    }

    public DynamicSpawnSourceListener(
        SQLiteConnection db,
        CharacterStableKeyResolver characterKeyResolver,
        DynamicSpawnCatalog catalog)
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
        _catalog = catalog;
    }

    public void OnAssetFound(MonoBehaviour comp)
    {
        var type = comp.GetType();
        if (type.Assembly.GetName().Name != "Assembly-CSharp") return;
        if (type == typeof(SpawnPoint) || type == typeof(SpawnPointTrigger)) return;

        var scriptName = type.Name;

        var hostTransform = comp.transform;
        var hostScene = comp.gameObject.scene.name ?? "";
        var isChainedHost = comp.GetComponent<Character>() != null
            && PrefabUtility.IsPartOfPrefabAsset(comp.gameObject);

        // Walk public instance fields by reflection — matches catalog field names directly
        var fields = type.GetFields(BindingFlags.Public | BindingFlags.Instance);
        foreach (var field in fields)
        {
            var fieldName = field.Name;
            var entry = _catalog.Classify(scriptName, fieldName);
            if (entry.Classification == DynamicSpawnClassification.Denied) continue;

            var value = field.GetValue(comp);
            if (value == null) continue;

            var characters = ResolveCharacters(value);
            if (characters.Count == 0) continue;

            if (entry.Classification == DynamicSpawnClassification.Unknown)
            {
                // Field resolves to a Character prefab but isn't classified — record finding
                RecordFinding(comp, scriptName, fieldName, field, value, characters[0]);
                continue;
            }

            // Allowed — emit spawn rows
            var eventPosition = entry.IncludeHostPosition ? hostTransform.position : (Vector3?)null;
            if (isChainedHost)
            {
                foreach (var character in characters)
                {
                    // Category B — host is a Character prefab; write to chained table
                    var parentKey = _characterKeyResolver.GetStableKey(comp.GetComponent<Character>()!);
                    var childKey = _characterKeyResolver.GetStableKey(character);
                    _chainedRecords.Add(new CharacterChainedSpawnRecord
                    {
                        ParentStableKey = parentKey,
                        ChildStableKey = childKey,
                        SourceScript = scriptName,
                    });
                }
            }
            else if (entry.PositionStrategy == VithArenaFightPositionStrategy)
            {
                foreach (var resolved in ResolveVithArenaFightSpawns(comp, value, scriptName, fieldName))
                    AddDynamicSpawnRecord(resolved.Character, resolved.Position, hostScene, scriptName, eventPosition);
            }
            else if (entry.PositionStrategy == VitheoFightPositionStrategy)
            {
                var positions = ResolveVitheoFightPositions(comp, fieldName);
                foreach (var character in characters)
                {
                    foreach (var position in positions)
                        AddDynamicSpawnRecord(character, position, hostScene, scriptName, eventPosition);
                }
            }
            else
            {
                // Category A — emit spawn rows at the host's position(s)
                foreach (var character in characters)
                {
                    var positions = ResolvePositions(comp, entry.PositionField);
                    foreach (var pos in positions)
                        AddDynamicSpawnRecord(character, pos, hostScene, scriptName, eventPosition);
                }
            }
        }
    }

    public void OnScanFinished()
    {
        try
        {
            // Insert spawn records (deduplicate by Key)
            _db.CreateTable<DynamicCharacterSpawnRecord>();
            var uniqueSpawns = new Dictionary<string, DynamicCharacterSpawnRecord>();
            foreach (var rec in _spawnRecords)
                uniqueSpawns[rec.Key] = rec;
            _db.RunInTransaction(() =>
            {
                _db.DeleteAll<DynamicCharacterSpawnRecord>();
                foreach (var rec in uniqueSpawns.Values)
                    _db.InsertOrReplace(rec);
            });
            UnityEngine.Debug.Log($"[DynamicSpawn] Inserted {uniqueSpawns.Count} spawn records (from {_spawnRecords.Count} raw)");

            // Insert chained spawn records (deduplicate by composite)
            _db.CreateTable<CharacterChainedSpawnRecord>();
            var uniqueChained = new Dictionary<(string, string, string), CharacterChainedSpawnRecord>();
            foreach (var rec in _chainedRecords)
                uniqueChained[(rec.ParentStableKey, rec.ChildStableKey, rec.SourceScript)] = rec;
            _db.RunInTransaction(() =>
            {
                _db.DeleteAll<CharacterChainedSpawnRecord>();
                foreach (var rec in uniqueChained.Values)
                    _db.InsertOrReplace(rec);
            });
            UnityEngine.Debug.Log($"[DynamicSpawn] Inserted {uniqueChained.Count} chained records (from {_chainedRecords.Count} raw)");
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError($"[DynamicSpawn] OnScanFinished error: {ex}");
        }

        // Detect stale catalog entries (scripts in catalog but not in Assembly-CSharp)
        var assemblyTypes = new HashSet<string>();
        foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            if (assembly.GetName().Name != "Assembly-CSharp") continue;
            foreach (var t in assembly.GetTypes())
                assemblyTypes.Add(t.Name);
        }
        foreach (var scriptName in _catalog.KnownScripts)
        {
            if (!assemblyTypes.Contains(scriptName))
            {
                _envelope.StaleEntries.Add(new DynamicSpawnErrorEnvelope.StaleEntry
                {
                    Kind = "unknown",
                    ScriptType = scriptName,
                    FieldName = "<all fields>",
                });
            }
        }

        _spawnRecords.Clear();
        _chainedRecords.Clear();

        if (_envelope.HasErrors)
        {
            _envelope.PrintHumanSummary();
            _hasErrors = true;
        }
    }

    private List<Character> ResolveCharacters(object value)
    {
        var result = new List<Character>();

        switch (value)
        {
            case GameObject go:
            {
                try
                {
                    var c = go.GetComponent<Character>();
                    if (c != null) result.Add(c);
                }
                catch (UnassignedReferenceException) { }
                break;
            }
            case Character c:
                result.Add(c);
                break;
            case IList list:
            {
                foreach (var item in list)
                {
                    if (item is GameObject go2)
                    {
                        try
                        {
                            var c = go2.GetComponent<Character>();
                            if (c != null) result.Add(c);
                        }
                        catch (UnassignedReferenceException) { }
                    }
                    else if (item is Character c2)
                    {
                        result.Add(c2);
                    }
                }
                break;
            }
        }

        return result;
    }

    private void AddDynamicSpawnRecord(Character character, Vector3 pos, string hostScene, string scriptName, Vector3? eventPosition)
    {
        var childKey = _characterKeyResolver.GetStableKey(character);
        var key = eventPosition.HasValue
            ? $"{childKey}|{hostScene}|{pos.x}|{pos.y}|{pos.z}|{scriptName}|event:{eventPosition.Value.x}|{eventPosition.Value.y}|{eventPosition.Value.z}"
            : $"{childKey}|{hostScene}|{pos.x}|{pos.y}|{pos.z}|{scriptName}";
        _spawnRecords.Add(new DynamicCharacterSpawnRecord
        {
            Key = key,
            CharacterStableKey = childKey,
            Scene = hostScene,
            X = pos.x,
            Y = pos.y,
            Z = pos.z,
            SourceScript = scriptName,
            EventX = eventPosition?.x,
            EventY = eventPosition?.y,
            EventZ = eventPosition?.z,
        });
    }

    private List<ResolvedCharacterSpawn> ResolveVithArenaFightSpawns(
        MonoBehaviour host,
        object value,
        string scriptName,
        string fieldName)
    {
        var result = new List<ResolvedCharacterSpawn>();
        if (!(value is IList list))
            return result;

        var positionFields = VithArenaFightPositionFields(list.Count);
        if (positionFields.Count != list.Count)
        {
            UnityEngine.Debug.LogWarning(
                $"[DynamicSpawn] {scriptName}.{fieldName} has {list.Count} entries; " +
                "VithArena.SpawnPiece only defines placement for 1-3 enemies");
            return result;
        }

        for (var i = 0; i < list.Count; i++)
        {
            var character = ResolveCharacterReference(list[i]);
            if (character == null)
                continue;

            if (!TryResolvePosition(host, positionFields[i], out var position))
            {
                UnityEngine.Debug.LogWarning(
                    $"[DynamicSpawn] {scriptName}.{fieldName} could not resolve {positionFields[i]}; skipping enemy {i}");
                continue;
            }

            result.Add(new ResolvedCharacterSpawn
            {
                Character = character,
                Position = position,
            });
        }

        return result;
    }

    private List<Vector3> ResolveVitheoFightPositions(MonoBehaviour host, string fieldName)
    {
        if (fieldName == "AzynthiCorruptor")
            return ResolvePositions(host, "CorruptorSpawn");

        var positions = ResolvePositions(host, "arenaNav");
        var count = fieldName switch
        {
            "LegionTier1" => Math.Max(positions.Count - 1, 0),
            "LegionTier2" => Math.Min(5, positions.Count),
            "LegionTier3" => Math.Min(4, positions.Count),
            "LegionTier4" => positions.Count,
            "LegionTier5" => Math.Min(2, positions.Count),
            _ => positions.Count,
        };
        return positions.GetRange(0, Math.Min(count, positions.Count));
    }

    private static List<string> VithArenaFightPositionFields(int count)
    {
        if (count == 1) return new List<string> { "SpawnLoc1" };
        if (count == 2) return new List<string> { "SpawnLoc2", "SpawnLoc3" };
        if (count == 3) return new List<string> { "SpawnLoc1", "SpawnLoc2", "SpawnLoc3" };
        return new List<string>();
    }

    private Character? ResolveCharacterReference(object item)
    {
        if (item is GameObject go)
        {
            try
            {
                return go.GetComponent<Character>();
            }
            catch (UnassignedReferenceException) { return null; }
        }

        return item as Character;
    }

    private bool TryResolvePosition(MonoBehaviour host, string fieldName, out Vector3 position)
    {
        position = default;
        var field = host.GetType().GetField(fieldName, BindingFlags.Public | BindingFlags.Instance);
        if (field == null) return false;

        var val = field.GetValue(host);
        if (val is Transform t)
        {
            position = t.position;
            return true;
        }
        if (val is GameObject go)
        {
            position = go.transform.position;
            return true;
        }

        return false;
    }

    private List<Vector3> ResolvePositions(MonoBehaviour host, string? positionField)
    {
        if (string.IsNullOrEmpty(positionField))
            return new List<Vector3> { host.transform.position };

        // Support comma-separated position fields (e.g. "Spawn1,Spawn2")
        var fieldNames = positionField.Split(',');
        var result = new List<Vector3>();

        foreach (var name in fieldNames)
        {
            var trimmed = name.Trim();
            var field = host.GetType().GetField(trimmed, BindingFlags.Public | BindingFlags.Instance);
            if (field == null) continue;

            var val = field.GetValue(host);
            if (val is Transform t)
            {
                result.Add(t.position);
            }
            else if (val is GameObject go)
            {
                result.Add(go.transform.position);
            }
            else if (val is IList list)
            {
                foreach (var item in list)
                {
                    if (item is Transform tr)
                        result.Add(tr.position);
                    else if (item is GameObject go2)
                        result.Add(go2.transform.position);
                }
            }
        }

        // Fall back to host transform if no position fields resolved
        if (result.Count == 0)
            result.Add(host.transform.position);

        return result;
    }

    private void RecordFinding(
        MonoBehaviour host, string scriptName, string fieldName,
        FieldInfo field, object value, Character exampleCharacter)
    {
        var fieldKind = field.FieldType.Name;
        string? prefabPath = null;
        string? stableKey = null;
        string? displayName = null;

        var go = exampleCharacter.gameObject;
        prefabPath = AssetDatabase.GetAssetPath(go);
        stableKey = _characterKeyResolver.GetStableKey(exampleCharacter);
        displayName = go.name;

        _envelope.Findings.Add(new DynamicSpawnErrorEnvelope.Finding
        {
            ScriptType = scriptName,
            FieldName = fieldName,
            FieldKind = fieldKind,
            ExamplePrefabPath = prefabPath,
            ExampleStableKey = stableKey,
            ExampleDisplayName = displayName,
            HostScenePath = host.gameObject.scene.path,
        });
    }
}
