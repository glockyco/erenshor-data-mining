#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Exports both directions of the three quest listeners, including held-item
/// alternatives. Scene subjects keep their own keys, so activating one spawn
/// point does not gate every placement of its possible characters.
/// </summary>
public sealed class QuestActivationListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly ActivationTargetResolver _targets;
    private readonly Dictionary<string, QuestActivationEffectRecord> _records = new();

    public QuestActivationListener(SQLiteConnection db, ActivationTargetResolver targets)
    {
        _db = db;
        _targets = targets;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<QuestActivationEffectRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<QuestActivationEffectRecord>();
            _db.InsertAll(_records.Values);
        });
        Debug.Log($"[{GetType().Name}] Exported {_records.Count} quest activation effect atoms");
        _records.Clear();
    }

    public void OnAssetFound(GameObject go)
    {
        if (!go.scene.IsValid() || string.IsNullOrEmpty(go.scene.name))
            return;

        // code-fact: guide.gates.quest_activation
        // code-fact: ui.planning_access_quest
        // code-fact: ui.planning_access_alternative_quest
        // code-fact: ui.planning_access_item
        var singles = go.GetComponents<QuestSpawnListener>();
        for (int index = 0; index < singles.Length; index++)
        {
            var listener = singles[index];
            var groups = new List<(string kind, string key)[]>();
            if (listener.Quest != null)
                groups.Add(new[] { ("quest_done", StableKeyGenerator.ForQuest(listener.Quest)) });
            // Despite its name, ActiveQuest is also checked with IsQuestDone.
            if (listener.ActiveQuest != null)
                groups.Add(
                    new[] { ("quest_done", StableKeyGenerator.ForQuest(listener.ActiveQuest)) }
                );
            if (
                listener.item != null
                && !string.Equals(listener.item.name, "Empty", StringComparison.OrdinalIgnoreCase)
            )
                groups.Add(new[] { ("item_held", StableKeyGenerator.ForItem(listener.item)) });
            WriteEffects(listener, index, listener.EnableOnQuestComplete, true, groups);
            WriteEffects(listener, index, listener.DestroyOnQuestComplete, false, groups);
        }

        var multis = go.GetComponents<MultiQuestListener>();
        for (int index = 0; index < multis.Length; index++)
        {
            var listener = multis[index];
            if (listener.Quest == null || listener.Quest2 == null)
                throw new InvalidOperationException(
                    $"{ActivationTargetResolver.ObjectKey(go)} has a multi-quest listener without both quests"
                );
            var groups = new List<(string kind, string key)[]>
            {
                new[]
                {
                    ("quest_done", StableKeyGenerator.ForQuest(listener.Quest)),
                    ("quest_done", StableKeyGenerator.ForQuest(listener.Quest2)),
                },
            };
            WriteEffects(listener, index, listener.EnableOnQuestComplete, true, groups);
            WriteEffects(listener, index, listener.DestroyOnQuestComplete, false, groups);
        }

        var managers = go.GetComponents<DynamicContentManager>();
        for (int index = 0; index < managers.Length; index++)
        {
            var manager = managers[index];
            WriteDynamicEffects(manager, index, manager.ActivateWorldItems, true);
            WriteDynamicEffects(manager, index, manager.DisableWorldItems, false);
        }
    }

    private void WriteDynamicEffects(
        DynamicContentManager manager,
        int componentIndex,
        List<DynamicContent>? entries,
        bool enabling
    )
    {
        if (entries == null)
            return;
        for (int index = 0; index < entries.Count; index++)
        {
            var entry = entries[index];
            if (entry.RefQuest == null)
                throw new InvalidOperationException(
                    $"{ActivationTargetResolver.ObjectKey(manager.gameObject)} has a dynamic-content entry without a quest"
                );
            var groups = new List<(string kind, string key)[]>
            {
                new[] { ("quest_done", StableKeyGenerator.ForQuest(entry.RefQuest)) },
            };
            WriteEffects(manager, componentIndex, entry.AffectedByQuest, enabling, groups, index);
        }
    }

    private void WriteEffects(
        MonoBehaviour listener,
        int componentIndex,
        List<GameObject>? objects,
        bool enabling,
        List<(string kind, string key)[]> groups,
        int groupOffset = 0
    )
    {
        if (objects == null)
            return;
        string script = listener.GetType().Name;
        string listenerKey =
            ActivationTargetResolver.ObjectKey(listener.gameObject)
            + ":script:"
            + script
            + ":"
            + componentIndex;
        string effect = enabling ? "enable" : "disable";
        foreach (var target in objects)
        {
            if (target == null)
                continue;
            string objectKey = ActivationTargetResolver.ObjectKey(target);
            foreach (var subject in _targets.Resolve(target, enabling))
            {
                for (int groupIndex = 0; groupIndex < groups.Count; groupIndex++)
                {
                    foreach (var atom in groups[groupIndex])
                    {
                        int group = groupOffset + groupIndex;
                        string recordKey = string.Join(
                            "|",
                            new[]
                            {
                                listenerKey,
                                objectKey,
                                effect,
                                subject.Kind,
                                subject.Key,
                                group.ToString(System.Globalization.CultureInfo.InvariantCulture),
                                atom.kind,
                                atom.key,
                            }
                        );
                        _records[recordKey] = new QuestActivationEffectRecord
                        {
                            RecordKey = recordKey,
                            ListenerKey = listenerKey,
                            ListenerObjectKey = _targets.Hierarchy.Capture(listener.gameObject),
                            ListenerComponentIsEnabled = listener.enabled,
                            Script = script,
                            Scene = subject.Scene,
                            ListenerIsEnabled = listener.isActiveAndEnabled,
                            TargetObjectKey = objectKey,
                            TargetObjectName = target.name,
                            TargetKind = subject.Kind,
                            TargetStableKey = subject.Key,
                            TargetIsEnabled = subject.IsEnabled,
                            Effect = effect,
                            GroupIndex = group,
                            AtomKind = atom.kind,
                            AtomStableKey = atom.key,
                        };
                    }
                }
            }
        }
    }
}
