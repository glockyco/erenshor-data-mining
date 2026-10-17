#nullable enable

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using SQLite;
using UnityEditor;
using UnityEngine;

public sealed class ScriptedActivatorListener : IAssetScanListener<MonoBehaviour>
{
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeys;
    private readonly ActivationTargetResolver _targets;
    private readonly Dictionary<Type, ActivationCatalogEntry> _catalog = new();
    private readonly List<ScriptedActivatorRecord> _sources = new();
    private readonly List<ScriptedActivatorReferenceRecord> _references = new();
    private readonly Dictionary<string, ScriptedActivatorTargetRecord> _subjects = new();

    // Exact shipped types make a changed reference shape an export failure,
    // rather than accepting an empty or differently interpreted collection.
    private static readonly Dictionary<
        Type,
        (string rule, Dictionary<string, Type> fields)
    > Contracts = new()
    {
        // code-fact: guide.gates.shiver_start
        // code-fact: guide.gates.shiver_update
        // code-fact: guide.gates.shiver_init
        [typeof(ShiverEvent)] = (
            "shiver_event",
            new()
            {
                ["FirstKio"] = typeof(GameObject),
                ["Kio"] = typeof(GameObject),
                ["WelcomeCrew"] = typeof(List<GameObject>),
                ["Hider"] = typeof(GameObject),
                ["SpawnTriggers"] = typeof(List<GameObject>),
                ["Phantom"] = typeof(GameObject),
                ["WarmFlame"] = typeof(GameObject),
            }
        ),
        // code-fact: guide.gates.memory_enter
        // code-fact: guide.gates.memory_exit
        [typeof(MemorySphere)] = (
            "memory_sphere",
            new() { ["Memory"] = typeof(GameObject), ["RequiredInInventory"] = typeof(Item) }
        ),
        // code-fact: guide.gates.siv_gaze
        // code-fact: guide.gates.siv_enter
        // code-fact: guide.gates.siv_exit
        [typeof(SivTorchLight)] = ("siv_torch_gaze", new() { ["BreakWall"] = typeof(GameObject) }),
        // code-fact: guide.gates.angel
        [typeof(ShiveringAngel)] = ("shivering_angel", new()),
        // code-fact: guide.gates.phantom_host
        // code-fact: guide.gates.phantom_wards
        [typeof(ShiveringPhantomWardListener)] = (
            "shivering_phantom_wards",
            new() { ["ward1"] = typeof(Character), ["ward2"] = typeof(Character) }
        ),
        // code-fact: guide.gates.fernalla_reset
        // code-fact: guide.gates.fernalla_reveal
        [typeof(FernallaFight)] = (
            "restored_fernalla",
            new()
            {
                ["RestoredFernalla"] = typeof(GameObject),
                ["FernSpawnPoint"] = typeof(SpawnPoint),
            }
        ),
        // code-fact: guide.gates.soluna_reset
        // code-fact: guide.gates.soluna_reveal
        [typeof(SolunaFight)] = (
            "restored_soluna",
            new() { ["RestoredSoluna"] = typeof(GameObject), ["SolunaSpawn"] = typeof(SpawnPoint) }
        ),
        // code-fact: guide.gates.brax_reset
        // code-fact: guide.gates.brax_death
        // code-fact: guide.gates.brax_reveal
        [typeof(BraxFightEvent)] = (
            "restored_brax",
            new() { ["GodBraxRestored"] = typeof(GameObject), ["BraxSpawn"] = typeof(SpawnPoint) }
        ),
        // code-fact: guide.gates.vitheo_reveal
        [typeof(VithArena)] = (
            "restored_vitheo",
            new() { ["RestoredVitheo"] = typeof(GameObject) }
        ),
        // code-fact: guide.gates.npc_alive
        [typeof(NPCAliveListener)] = (
            "npc_alive",
            new()
            {
                ["SpawnPoint"] = typeof(SpawnPoint),
                ["DespawnIfAlive"] = typeof(List<GameObject>),
                ["SpawnIfAlive"] = typeof(List<GameObject>),
            }
        ),
        [typeof(MorphTrigger)] = (
            "morph_trigger",
            new() { ["Enable"] = typeof(List<GameObject>), ["Disable"] = typeof(List<GameObject>) }
        ),
        [typeof(PietyTrigger)] = (
            "piety_guardians",
            new() { ["RequiredQuest"] = typeof(Quest), ["Guardians"] = typeof(List<GameObject>) }
        ),
        // code-fact: guide.gates.shout_essential_block
        // code-fact: guide.gates.shout_essentials
        // code-fact: guide.gates.shout_completion
        [typeof(NPCShoutListener)] = (
            "npc_shout_essentials",
            new()
            {
                ["TriggerQuest"] = typeof(Quest),
                ["UseEssentialSpawnsToBlockThisInstance"] = typeof(bool),
            }
        ),
        // code-fact: guide.gates.reliquary_sources
        // code-fact: guide.gates.reliquary_wards
        [typeof(ReliquaryFiend)] = ("reliquary_wards", new()),
        // code-fact: guide.gates.reliquary_claim_awake
        // code-fact: guide.gates.reliquary_claim_saved
        // code-fact: guide.gates.reliquary_claim_loaded
        [typeof(ReliqDisableFiendSpawn)] = ("reliquary_account_claim", new()),
        // Health-phase activation is not an encounter-won requirement.
        // code-fact: guide.gates.fernalla_portal_phases
        [typeof(FernallaPortalBoss)] = (
            "fernalla_portal_wards",
            new()
            {
                ["Ward1"] = typeof(GameObject),
                ["Ward2"] = typeof(GameObject),
                ["Ward3"] = typeof(GameObject),
            }
        ),
        // code-fact: guide.gates.bellwain_start
        // code-fact: guide.gates.bellwain_reveal
        [typeof(AngelScript)] = (
            "bellwain_reveal",
            new() { ["TheBellwains"] = typeof(GameObject) }
        ),
        // These are identities, not fixed spawn locations. Rune slots relocate them.
        // code-fact: guide.gates.planning_portal_positions
        // code-fact: planning.builds
        // code-fact: guide.gates.planning_portal_place
        // code-fact: guide.gates.planning_portal_items
        // code-fact: guide.gates.planning_raid_portals
        [typeof(PlanningTable)] = (
            "planning_portals",
            new()
            {
                ["Soluna"] = typeof(GameObject),
                ["Hidden"] = typeof(GameObject),
                ["Ripper"] = typeof(GameObject),
                ["Silkengrass"] = typeof(GameObject),
                ["Braxonian"] = typeof(GameObject),
                ["Windwashed"] = typeof(GameObject),
                ["BraxPort"] = typeof(GameObject),
                ["FernPort"] = typeof(GameObject),
                ["VithPort"] = typeof(GameObject),
                ["SolPort"] = typeof(GameObject),
            }
        ),
        // The destination comes from saved teleport origin, not the serialized default.
        // code-fact: guide.gates.reliquary_return_portal
        [typeof(ReliqPortalListener)] = (
            "reliquary_return_portal",
            new() { ["ReliqZL"] = typeof(Zoneline), ["ReliqPort"] = typeof(GameObject) }
        ),
    };

    public ScriptedActivatorListener(
        SQLiteConnection db,
        CharacterStableKeyResolver characterKeys,
        ActivationTargetResolver targets,
        DynamicSpawnCatalog catalog
    )
    {
        _db = db;
        _characterKeys = characterKeys;
        _targets = targets;
        foreach (var entry in catalog.Activations)
        {
            Type? type = null;
            foreach (var candidate in Contracts.Keys)
                if (candidate.Name == entry.Script)
                    type = candidate;
            if (type == null)
                throw new InvalidOperationException(
                    $"Unsupported activation script: {entry.Script}"
                );
            var contract = Contracts[type];
            if (entry.Rule != contract.rule || entry.Fields.Count != contract.fields.Count)
                throw new InvalidOperationException(
                    $"Activation contract changed for {entry.Script}"
                );
            foreach (var name in entry.Fields)
            {
                var field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public);
                if (
                    !contract.fields.TryGetValue(name, out var expected)
                    || field == null
                    || field.FieldType != expected
                )
                    throw new InvalidOperationException(
                        $"Missing or retyped activation field: {entry.Script}.{name}"
                    );
            }
            _catalog.Add(type, entry);
        }
        if (_catalog.Count != Contracts.Count)
            throw new InvalidOperationException(
                "Required scripted activation catalog entries are missing"
            );
    }

    public void OnAssetFound(MonoBehaviour asset)
    {
        if (!_catalog.TryGetValue(asset.GetType(), out var entry))
            return;
        var host = asset.gameObject;
        bool placed = host.scene.IsValid() && !PrefabUtility.IsPartOfPrefabAsset(host);
        var character = asset.GetComponent<Character>();
        // Character-held controller metadata belongs to a character, not to a
        // fictional placement at the prefab transform's coordinates.
        if (!placed && (character == null || asset is not (NPCShoutListener or ReliquaryFiend)))
            return;
        if (
            character == null
            && asset is (NPCShoutListener or ReliquaryFiend or ShiveringPhantomWardListener)
        )
            throw new InvalidOperationException(
                $"Activation controller {entry.Script} requires a host Character on {host.name}"
            );
        var characterKey = character != null ? _characterKeys.GetStableKey(character) : null;
        var components = host.GetComponents(asset.GetType());
        int componentIndex = Array.IndexOf(components, asset);
        var sourceKey =
            (placed ? ActivationTargetResolver.ObjectKey(host) : characterKey!)
            + ":script:"
            + entry.Script
            + ":"
            + componentIndex.ToString(CultureInfo.InvariantCulture);
        var position = host.transform.position;
        _sources.Add(
            new ScriptedActivatorRecord
            {
                SourceKey = sourceKey,
                RuleId = entry.Rule,
                Script = entry.Script,
                SourceScene = placed ? host.scene.name : null,
                SourceObjectName = host.name,
                X = placed ? position.x : (float?)null,
                Y = placed ? position.y : (float?)null,
                Z = placed ? position.z : (float?)null,
                IsEnabled = asset.isActiveAndEnabled,
                ComponentIsEnabled = asset.enabled,
                HostCharacterStableKey = characterKey,
            }
        );
        AddReference(sourceKey, "$host", 0, placed ? (object)host : character!, placed);
        if (asset is ReliqDisableFiendSpawn)
        {
            var spawn = asset.GetComponent<SpawnPoint>();
            if (spawn == null)
                throw new InvalidOperationException(
                    $"Reliquary account suppressor requires a host SpawnPoint: {sourceKey}"
                );
            AddReference(sourceKey, "$host_spawn_point", 0, spawn, placed);
        }
        foreach (var name in entry.Fields)
        {
            var value = asset.GetType().GetField(name)!.GetValue(asset);
            if (value is IList list)
            {
                for (int index = 0; index < list.Count; index++)
                    AddReference(sourceKey, name, index, list[index], placed);
                if (list.Count == 0)
                    AddReference(sourceKey, name, -1, null, placed, "empty_collection");
            }
            else
            {
                bool optional = asset is NPCShoutListener or ShiveringPhantomWardListener;
                if (!optional && (value == null || value is UnityEngine.Object obj && obj == null))
                    throw new InvalidOperationException(
                        $"Missing configured activation reference: {entry.Script}.{name} on {sourceKey}"
                    );
                AddReference(sourceKey, name, 0, value, placed);
            }
        }
        if (asset is ReliqPortalListener portal)
            AddReference(sourceKey, "$portal_active_self", 0, portal.ReliqPort.activeSelf, placed);
    }

    private void AddReference(
        string sourceKey,
        string field,
        int index,
        object? value,
        bool placed,
        string? emptyKind = null
    )
    {
        var referenceId =
            sourceKey + ":field:" + field + ":" + index.ToString(CultureInfo.InvariantCulture);
        var record = new ScriptedActivatorReferenceRecord
        {
            ReferenceId = referenceId,
            SourceKey = sourceKey,
            Field = field,
            ReferenceIndex = index,
            ReferenceKind = emptyKind ?? "null",
        };
        GameObject? sceneTarget = null;
        if (value is UnityEngine.Object obj && obj == null)
            value = null;
        switch (value)
        {
            case bool flag:
                record.ReferenceKind = "bool";
                record.BoolValue = flag;
                break;
            case Quest quest:
                record.ReferenceKind = "quest";
                record.ReferenceKey = StableKeyGenerator.ForQuest(quest);
                break;
            case Item item:
                record.ReferenceKind = "item";
                record.ReferenceKey = StableKeyGenerator.ForItem(item);
                break;
            case Character character:
                record.ReferenceKind = "character";
                record.ReferenceKey = _characterKeys.GetStableKey(character);
                if (character.gameObject.scene.IsValid())
                    sceneTarget = character.gameObject;
                break;
            case SpawnPoint spawnPoint:
                record.ReferenceKind = "spawn_point";
                record.ReferenceKey = _targets.GetStableKey(spawnPoint);
                sceneTarget = spawnPoint.gameObject;
                break;
            case Zoneline zoneLine:
                record.ReferenceKind = "zone_line";
                record.ReferenceKey = _targets.GetStableKey(zoneLine);
                sceneTarget = zoneLine.gameObject;
                break;
            case GameObject go:
                if (!go.scene.IsValid() || PrefabUtility.IsPartOfPrefabAsset(go))
                    throw new InvalidOperationException(
                        $"Activation target must be placed: {referenceId}"
                    );
                record.ReferenceKind = "object";
                record.ReferenceKey = ActivationTargetResolver.ObjectKey(go);
                sceneTarget = go;
                break;
            case null:
                break;
            default:
                throw new InvalidOperationException(
                    $"Unsupported activation reference: {referenceId} ({value.GetType()})"
                );
        }
        _references.Add(record);
        if (!placed || sceneTarget == null)
            return;
        if (field == "$host" || value is Character or SpawnPoint or Zoneline)
            AddSubjects(referenceId, sceneTarget, "reference", false);
        else
        {
            AddSubjects(referenceId, sceneTarget, "enable", true);
            AddSubjects(referenceId, sceneTarget, "disable", false);
        }
    }

    private void AddSubjects(string referenceId, GameObject target, string mode, bool enabling)
    {
        foreach (var subject in _targets.Resolve(target, enabling))
        {
            var id = referenceId + ":" + mode + ":" + subject.Kind + ":" + subject.Key;
            _subjects[id] = new ScriptedActivatorTargetRecord
            {
                TargetId = id,
                ReferenceId = referenceId,
                ResolutionMode = mode,
                Kind = subject.Kind,
                Key = subject.Key,
                Scene = subject.Scene,
                ObjectName = subject.ObjectName,
                IsEnabled = subject.IsEnabled,
            };
        }
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ScriptedActivatorRecord>();
        _db.CreateTable<ScriptedActivatorReferenceRecord>();
        _db.CreateTable<ScriptedActivatorTargetRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ScriptedActivatorTargetRecord>();
            _db.DeleteAll<ScriptedActivatorReferenceRecord>();
            _db.DeleteAll<ScriptedActivatorRecord>();
            _db.InsertAll(_sources);
            _db.InsertAll(_references);
            _db.InsertAll(_subjects.Values);
        });
        _sources.Clear();
        _references.Clear();
        _subjects.Clear();
    }
}
