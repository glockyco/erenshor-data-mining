#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEditor;
using UnityEngine;

/// <summary>Exports only the authored prefab references loaded by scene managers.</summary>
public class AuthoredSimListener : IAssetScanListener<SimPlayerMngr>
{
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeys;
    private readonly Dictionary<string, AuthoredSimRecord> _sims = new();
    private readonly List<AuthoredSimReferenceRecord> _references = new();
    private readonly List<AuthoredSimEquipmentRecord> _equipment = new();

    public AuthoredSimListener(SQLiteConnection db, CharacterStableKeyResolver characterKeys)
    {
        _db = db;
        _characterKeys = characterKeys;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<AuthoredSimRecord>();
        _db.CreateTable<AuthoredSimReferenceRecord>();
        _db.CreateTable<AuthoredSimEquipmentRecord>();
        _db.DeleteAll<AuthoredSimReferenceRecord>();
        _db.DeleteAll<AuthoredSimEquipmentRecord>();
        _db.DeleteAll<AuthoredSimRecord>();
        _sims.Clear();
        _references.Clear();
        _equipment.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_sims.Values);
        _db.InsertAll(_references);
        _db.InsertAll(_equipment);
        _sims.Clear();
        _references.Clear();
        _equipment.Clear();
    }

    public void OnAssetFound(SimPlayerMngr manager)
    {
        var scene = manager.gameObject.scene;
        if (string.IsNullOrEmpty(scene.name))
            return;
        var sourceKey = GlobalObjectId.GetGlobalObjectIdSlow(manager).ToString();
        // code-fact: sim.authored_seed_load
        // code-fact: sim.authored_reference_list
        // Only ActualSims establishes authored membership. Name pools and unused
        // template prefabs never reach this listener's identity collection.
        for (var index = 0; index < manager.ActualSims.Count; index++)
        {
            var prefab = manager.ActualSims[index];
            if (prefab == null)
                throw new InvalidOperationException($"{sourceKey}.ActualSims[{index}] is null.");
            if (
                !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(
                    prefab,
                    out string guid,
                    out long localId
                )
            )
                throw new InvalidOperationException(
                    $"{prefab.name}: authored sim has no asset identity."
                );
            var path = AssetDatabase.GetAssetPath(prefab);
            if (!path.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException(
                    $"{prefab.name}: ActualSims must reference a prefab asset."
                );
            var key = StableKeyGenerator.ForAuthoredSim(guid, localId);
            _references.Add(
                new AuthoredSimReferenceRecord
                {
                    SourceComponentKey = sourceKey,
                    ReferenceIndex = index,
                    SourceScene = scene.name,
                    SourceScenePath = scene.path,
                    AuthoredSimStableKey = key,
                }
            );
            if (_sims.ContainsKey(key))
                continue;

            var character = Require<Character>(prefab);
            var npc = Require<NPC>(prefab);
            var sim = Require<SimPlayer>(prefab);
            var stats = Require<Stats>(prefab);
            var inventory = Require<Inventory>(prefab);
            // code-fact: sim.save_level_selects_zone
            // The runtime chooses a zone using saved level. No fixed position is exported.
            if (stats.CharacterClass == null)
                throw new InvalidOperationException($"{path}: authored sim has no class.");
            // code-fact: sim.existing_save_precedes_seed
            // code-fact: sim.new_save_uses_seed
            // Level, skill and equipment below are new-save inputs, not current state.
            _sims.Add(
                key,
                new AuthoredSimRecord
                {
                    StableKey = key,
                    PrefabGuid = guid,
                    PrefabLocalId = localId,
                    PrefabPath = path,
                    ObjectName = prefab.name,
                    RawCharacterStableKey = _characterKeys.GetStableKey(character),
                    NPCName = npc.NPCName,
                    // code-fact: sim.authored_class
                    SeedClassName = stats.CharacterClass.ClassName,
                    SeedLevel = stats.Level,
                    SeedSkillLevel = sim.SkillLevel,
                    // code-fact: sim.authored_gender
                    SeedIsMale = inventory.isMale,
                    // code-fact: sim.authored_hair
                    SeedHairName = sim.HairName,
                    // code-fact: sim.authored_hair_color
                    SeedHairColor = sim.HairColor,
                    // code-fact: sim.authored_skin_color
                    SeedSkinColor = sim.SkinColor,
                    // code-fact: sim.authored_gm_flag
                    IsGMCharacter = sim.IsGMCharacter,
                    // code-fact: sim.authored_rival_flag
                    Rival = sim.Rival,
                }
            );
            for (var position = 0; position < inventory.EquippedItems.Count; position++)
            {
                var item = inventory.EquippedItems[position];
                _equipment.Add(
                    new AuthoredSimEquipmentRecord
                    {
                        AuthoredSimStableKey = key,
                        Position = position,
                        ItemStableKey = item == null ? null : StableKeyGenerator.ForItem(item),
                    }
                );
            }
        }
    }

    private static T Require<T>(GameObject prefab)
        where T : Component
    {
        var component = prefab.GetComponent<T>();
        if (component == null)
            throw new InvalidOperationException(
                $"{prefab.name}: authored sim lacks {typeof(T).Name}."
            );
        return component;
    }
}
