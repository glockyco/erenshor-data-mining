#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

public class QuestListener : IAssetScanListener<Quest>
{
    private readonly SQLiteConnection _db;
    private readonly List<QuestRecord> _records = new();

    public QuestListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<QuestRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<QuestRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Quest asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset, _records.Count));
    }

    private QuestRecord CreateRecord(Quest quest, int questDbIndex)
    {
        string requiredItems = quest.RequiredItems != null
            ? string.Join(", ", quest.RequiredItems.Where(item => item != null && !string.IsNullOrEmpty(item.Id)).Select(item => $"{item.ItemName} ({item.Id})"))
            : "";

        string affectedFactions = quest.AffectFactions != null
            ? string.Join(", ", quest.AffectFactions.Where(f => f != null && !string.IsNullOrEmpty(f.REFNAME)).Select(f => f.REFNAME))
            : "";

        string affectedFactionAmounts = quest.AffectFactionAmts != null
            ? string.Join(", ", quest.AffectFactionAmts)
            : "";

        string completeQuests = quest.CompleteOtherQuests != null
            ? string.Join(", ", quest.CompleteOtherQuests.Where(q => q != null && !string.IsNullOrEmpty(q.DBName)).Select(q => $"{q.QuestName} ({q.DBName})"))
            : "";

        return new QuestRecord
        {
            // --- Core Identification ---
            QuestDBIndex = questDbIndex,
            QuestName = quest.QuestName,
            QuestDesc = quest.QuestDesc,

            // --- Requirements ---
            RequiredItemIds = requiredItems,

            // --- Rewards & Completion ---
            XPonComplete = quest.XPonComplete,
            ItemOnCompleteId = quest.ItemOnComplete != null ? $"{quest.ItemOnComplete.ItemName} ({quest.ItemOnComplete.Id})" : "",
            GoldOnComplete = quest.GoldOnComplete,
            AssignNewQuestOnCompleteDBName = quest.AssignNewQuestOnComplete != null ? $"{quest.AssignNewQuestOnComplete.QuestName} ({quest.AssignNewQuestOnComplete.DBName})" : "",
            CompleteOtherQuestDBNames = completeQuests,

            // --- Dialog & Text ---
            DialogOnSuccess = quest.DialogOnSuccess,
            DialogOnPartialSuccess = quest.DialogOnPartialSuccess,
            DisableText = quest.DisableText,

            // --- Faction Adjustments ---
            AffectedFactions = affectedFactions,
            AffectedFactionAmounts = affectedFactionAmounts,

            // --- Flags & Behavior ---
            AssignThisQuestOnPartialComplete = quest.AssignThisQuestOnPartialComplete,
            Repeatable = quest.repeatable,
            DisableQuest = quest.DisableQuest,
            KillTurnInHolder = quest.KillTurnInHolder,
            DestroyTurnInHolder = quest.DestroyTurnInHolder,
            DropInvulnOnHolder = quest.DropInvulnOnHolder,
            OncePerSpawnInstance = quest.OncePerSpawnInstance,

            // --- Achievements ---
            SetAchievementOnGet = quest.SetAchievementOnGet,
            SetAchievementOnFinish = quest.SetAchievementOnFinish,

            // --- Internals / Metadata ---
            DBName = quest.DBName,
            ResourceName = quest.name,
        };
    }
}