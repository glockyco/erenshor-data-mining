#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

/// <summary>
/// Scans quest-gated activation components to discover which quests must be
/// completed to activate zone lines and characters.
///
/// Three activation mechanisms exist in the game:
///   QuestSpawnListener:     Quest OR ActiveQuest → enables targets, self-destructs.
///   MultiQuestListener:     Quest AND Quest2 → enables targets, self-destructs.
///   DynamicContentManager:  Persistent checker. ActivateWorldItems entries each
///                           have a single RefQuest and a list of affected GameObjects.
///
/// Multiple sources targeting the same zone line or character create additional
/// OR groups — any single group being fully satisfied unlocks it.
///
/// Target resolution rules:
///   - Zoneline:   emit ZoneLineQuestUnlockRecord. Zone lines with activeSelf=false
///     on their own GO (and not the direct target) are skipped — enabling a parent
///     GO does not propagate to children whose own activeSelf is false.
///   - Character:  emit CharacterQuestUnlockRecord directly.
///   - SpawnPoint: the spawnable Character lives on prefabs in CommonSpawns/RareSpawns,
///     not in the scene hierarchy, so GetComponentsInChildren<Character> misses it.
///     Walk those spawn lists instead to emit CharacterQuestUnlockRecords.
///     This handles patterns where a disabled SpawnPoint GO (e.g. BassleSpawn) is
///     enabled by an external QuestSpawnListener rather than the SpawnPoint's own
///     SpawnUponQuestComplete field.
/// </summary>
public class QuestActivationListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly ZoneLineStableKeyResolver _zoneLineKeyResolver;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly List<ZoneLineQuestUnlockRecord> _zoneLineRecords = new();
    private readonly List<CharacterQuestUnlockRecord> _characterRecords = new();

    // Dedup: prevent duplicate records when the same (target, group, quest) is
    // encountered multiple times (e.g. nested hierarchies or shared targets).
    private readonly HashSet<(string, int, string)> _seenZoneLineUnlocks = new();
    private readonly HashSet<(string, int, string)> _seenCharacterUnlocks = new();

    private int _nextGroupId;

    public QuestActivationListener(
        SQLiteConnection db,
        ZoneLineStableKeyResolver zoneLineKeyResolver,
        CharacterStableKeyResolver characterKeyResolver)
    {
        _db = db;
        _zoneLineKeyResolver = zoneLineKeyResolver;
        _characterKeyResolver = characterKeyResolver;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ZoneLineQuestUnlockRecord>();
        _db.CreateTable<CharacterQuestUnlockRecord>();

        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ZoneLineQuestUnlockRecord>();
            _db.DeleteAll<CharacterQuestUnlockRecord>();

            _db.InsertAll(_zoneLineRecords);
            _db.InsertAll(_characterRecords);
        });

        Debug.Log($"[{GetType().Name}] Exported {_zoneLineRecords.Count} zone line unlock records, " +
                  $"{_characterRecords.Count} character unlock records");

        _zoneLineRecords.Clear();
        _characterRecords.Clear();
        _seenZoneLineUnlocks.Clear();
        _seenCharacterUnlocks.Clear();
    }

    public void OnAssetFound(GameObject go)
    {
        // Skip non-scene objects (prefabs without a scene)
        if (go.scene.name == null)
            return;

        foreach (var listener in go.GetComponents<QuestSpawnListener>())
        {
            ProcessQuestSpawnListener(listener);
        }

        foreach (var listener in go.GetComponents<MultiQuestListener>())
        {
            ProcessMultiQuestListener(listener);
        }

        foreach (var manager in go.GetComponents<DynamicContentManager>())
        {
            ProcessDynamicContentManager(manager);
        }
    }

    private void ProcessQuestSpawnListener(QuestSpawnListener listener)
    {
        if (listener.EnableOnQuestComplete == null || listener.EnableOnQuestComplete.Count == 0)
            return;

        // Quest and ActiveQuest are OR conditions — each gets its own unlock group.
        // Item-based unlocks are skipped (can't be reliably checked from quest state).

        if (listener.Quest != null && !string.IsNullOrEmpty(listener.Quest.DBName))
        {
            var groupId = _nextGroupId++;
            var quests = new[] { listener.Quest.DBName };
            ProcessTargets(listener.EnableOnQuestComplete, groupId, quests);
        }

        if (listener.ActiveQuest != null && !string.IsNullOrEmpty(listener.ActiveQuest.DBName))
        {
            var groupId = _nextGroupId++;
            var quests = new[] { listener.ActiveQuest.DBName };
            ProcessTargets(listener.EnableOnQuestComplete, groupId, quests);
        }
    }

    private void ProcessMultiQuestListener(MultiQuestListener listener)
    {
        if (listener.EnableOnQuestComplete == null || listener.EnableOnQuestComplete.Count == 0)
            return;

        // Quest AND Quest2 — both in a single unlock group.
        if (listener.Quest == null || string.IsNullOrEmpty(listener.Quest.DBName))
            return;
        if (listener.Quest2 == null || string.IsNullOrEmpty(listener.Quest2.DBName))
            return;

        var groupId = _nextGroupId++;
        var quests = new[] { listener.Quest.DBName, listener.Quest2.DBName };
        ProcessTargets(listener.EnableOnQuestComplete, groupId, quests);
    }

    private void ProcessDynamicContentManager(DynamicContentManager manager)
    {
        if (manager.ActivateWorldItems == null)
            return;

        // Each ActivateWorldItems entry has a single quest and a list of targets.
        // Each entry is its own unlock group (single quest, so group size is 1).
        foreach (var entry in manager.ActivateWorldItems)
        {
            if (entry.RefQuest == null || string.IsNullOrEmpty(entry.RefQuest.DBName))
                continue;
            if (entry.AffectedByQuest == null || entry.AffectedByQuest.Count == 0)
                continue;

            var groupId = _nextGroupId++;
            var quests = new[] { entry.RefQuest.DBName };
            ProcessTargets(entry.AffectedByQuest, groupId, quests);
        }
    }

    private void ProcessTargets(List<GameObject> targets, int groupId, string[] questDBNames)
    {
        foreach (var target in targets)
        {
            if (target == null)
                continue;

            // Zone lines: emit a record only when the zone line will actually become
            // accessible by enabling the target. A zone line with activeSelf=false
            // on its own GO will NOT be activated when its parent is enabled (Unity
            // propagates activation only to children that already have activeSelf=true).
            // Exception: if the zone line IS the direct target, it will be activated.
            foreach (var zoneLine in target.GetComponentsInChildren<Zoneline>(includeInactive: true))
            {
                if (!zoneLine.gameObject.activeSelf && zoneLine.gameObject != target)
                    continue;

                var stableKey = _zoneLineKeyResolver.GetStableKey(zoneLine);
                foreach (var questDBName in questDBNames)
                {
                    if (_seenZoneLineUnlocks.Add((stableKey, groupId, questDBName)))
                    {
                        _zoneLineRecords.Add(new ZoneLineQuestUnlockRecord
                        {
                            ZoneLineStableKey = stableKey,
                            UnlockGroup = groupId,
                            QuestDBName = questDBName,
                        });
                    }
                }
            }

            // Characters: emit records for Character components found in the hierarchy.
            foreach (var character in target.GetComponentsInChildren<Character>(includeInactive: true))
            {
                var stableKey = _characterKeyResolver.GetStableKey(character);
                foreach (var questDBName in questDBNames)
                {
                    if (_seenCharacterUnlocks.Add((stableKey, groupId, questDBName)))
                    {
                        _characterRecords.Add(new CharacterQuestUnlockRecord
                        {
                            CharacterStableKey = stableKey,
                            UnlockGroup = groupId,
                            QuestDBName = questDBName,
                        });
                    }
                }
            }

            // SpawnPoints: the Character lives on prefabs in CommonSpawns/RareSpawns,
            // not in the scene hierarchy, so GetComponentsInChildren<Character> cannot
            // find it. Walk the spawn lists to emit CharacterQuestUnlockRecords.
            // Apply the same activeSelf guard as zone lines: a SpawnPoint that is
            // inactive inside the target hierarchy (not the direct target) would not
            // be activated by enabling the parent.
            foreach (var spawnPoint in target.GetComponentsInChildren<SpawnPoint>(includeInactive: true))
            {
                if (!spawnPoint.gameObject.activeSelf && spawnPoint.gameObject != target)
                    continue;

                var allSpawns =
                    (spawnPoint.CommonSpawns ?? new List<GameObject>())
                    .Concat(spawnPoint.RareSpawns ?? new List<GameObject>());
                foreach (var spawnGO in allSpawns)
                {
                    if (spawnGO == null)
                        continue;
                    var character = spawnGO.GetComponent<Character>();
                    if (character == null)
                        continue;
                    var stableKey = _characterKeyResolver.GetStableKey(character);
                    foreach (var questDBName in questDBNames)
                    {
                        if (_seenCharacterUnlocks.Add((stableKey, groupId, questDBName)))
                        {
                            _characterRecords.Add(new CharacterQuestUnlockRecord
                            {
                                CharacterStableKey = stableKey,
                                UnlockGroup = groupId,
                                QuestDBName = questDBName,
                            });
                        }
                    }
                }
            }
        }
    }
}
