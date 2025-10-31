#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

public class QuestListener : IAssetScanListener<Quest>
{
    private readonly SQLiteConnection _db;
    private readonly List<QuestRecord> _records = new();
    private readonly List<QuestRequiredItemRecord> _questRequiredItemRecords = new();
    private readonly List<QuestFactionAffectRecord> _questFactionAffectRecords = new();
    private readonly List<QuestRewardRecord> _questRewardRecords = new();
    private readonly List<QuestCompleteOtherQuestRecord> _questCompleteOtherQuestRecords = new();

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

        // Create and insert junction table records after parent records are inserted
        _db.CreateTable<QuestRequiredItemRecord>();
        _db.CreateTable<QuestFactionAffectRecord>();
        _db.CreateTable<QuestRewardRecord>();
        _db.CreateTable<QuestCompleteOtherQuestRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<QuestRequiredItemRecord>();
            _db.DeleteAll<QuestFactionAffectRecord>();
            _db.DeleteAll<QuestRewardRecord>();
            _db.DeleteAll<QuestCompleteOtherQuestRecord>();
            _db.InsertAll(_questRequiredItemRecords);
            _db.InsertAll(_questFactionAffectRecords);
            _db.InsertAll(_questRewardRecords);
            _db.InsertAll(_questCompleteOtherQuestRecords);
        });
        _questRequiredItemRecords.Clear();
        _questFactionAffectRecords.Clear();
        _questRewardRecords.Clear();
        _questCompleteOtherQuestRecords.Clear();
    }

    public void OnAssetFound(Quest asset)
    {
        var questRecord = CreateRecord(asset, _records.Count);
        _records.Add(questRecord);
        _questRequiredItemRecords.AddRange(CreateQuestRequiredItemRecords(questRecord.QuestDBIndex, asset));
        _questFactionAffectRecords.AddRange(CreateQuestFactionAffectRecords(questRecord.QuestDBIndex, asset));
        _questRewardRecords.AddRange(CreateQuestRewardRecords(questRecord.QuestDBIndex, asset));
        _questCompleteOtherQuestRecords.AddRange(CreateQuestCompleteOtherQuestRecords(questRecord.QuestDBIndex, asset));
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

    private List<QuestRequiredItemRecord> CreateQuestRequiredItemRecords(int questDbIndex, Quest quest)
    {
        var records = new List<QuestRequiredItemRecord>();
        var seenResourceNames = new HashSet<string>();

        if (quest.RequiredItems != null && quest.RequiredItems.Count > 0)
        {
            foreach (var item in quest.RequiredItems)
            {
                if (item != null && !string.IsNullOrEmpty(item.name) && seenResourceNames.Add(item.name))
                {
                    records.Add(new QuestRequiredItemRecord
                    {
                        QuestId = questDbIndex,
                        ItemResourceName = item.name
                    });
                }
            }
        }

        return records;
    }

    private List<QuestFactionAffectRecord> CreateQuestFactionAffectRecords(int questDbIndex, Quest quest)
    {
        var records = new List<QuestFactionAffectRecord>();
        var seenRefNames = new HashSet<string>();

        // Zip AffectFactions and AffectFactionAmts together
        if (quest.AffectFactions != null && quest.AffectFactionAmts != null)
        {
            var factions = quest.AffectFactions.Where(f => f != null && !string.IsNullOrEmpty(f.REFNAME)).ToList();
            var amounts = quest.AffectFactionAmts;

            // Only process up to the minimum count to avoid index errors
            int count = Mathf.Min(factions.Count, amounts.Count);

            for (int i = 0; i < count; i++)
            {
                var faction = factions[i];
                var amount = amounts[i];

                if (!string.IsNullOrEmpty(faction.REFNAME) && seenRefNames.Add(faction.REFNAME))
                {
                    records.Add(new QuestFactionAffectRecord
                    {
                        QuestId = questDbIndex,
                        FactionREFNAME = faction.REFNAME,
                        ModifierValue = (int)amount
                    });
                }
            }
        }

        return records;
    }

    private List<QuestRewardRecord> CreateQuestRewardRecords(int questDbIndex, Quest quest)
    {
        var records = new List<QuestRewardRecord>();
        var seenRewards = new HashSet<(string RewardType, string RewardValue)>();

        // XP Reward
        if (quest.XPonComplete > 0)
        {
            var reward = ("XP", quest.XPonComplete.ToString());
            if (seenRewards.Add(reward))
            {
                records.Add(new QuestRewardRecord
                {
                    QuestId = questDbIndex,
                    RewardType = "XP",
                    RewardValue = quest.XPonComplete.ToString(),
                    Quantity = quest.XPonComplete
                });
            }
        }

        // Gold Reward
        if (quest.GoldOnComplete > 0)
        {
            var reward = ("Gold", quest.GoldOnComplete.ToString());
            if (seenRewards.Add(reward))
            {
                records.Add(new QuestRewardRecord
                {
                    QuestId = questDbIndex,
                    RewardType = "Gold",
                    RewardValue = quest.GoldOnComplete.ToString(),
                    Quantity = quest.GoldOnComplete
                });
            }
        }

        // Item Reward
        if (quest.ItemOnComplete != null && !string.IsNullOrEmpty(quest.ItemOnComplete.Id))
        {
            var reward = ("Item", quest.ItemOnComplete.Id);
            if (seenRewards.Add(reward))
            {
                records.Add(new QuestRewardRecord
                {
                    QuestId = questDbIndex,
                    RewardType = "Item",
                    RewardValue = quest.ItemOnComplete.Id,
                    Quantity = 1
                });
            }
        }

        return records;
    }

    private List<QuestCompleteOtherQuestRecord> CreateQuestCompleteOtherQuestRecords(int questDbIndex, Quest quest)
    {
        var records = new List<QuestCompleteOtherQuestRecord>();
        var seenDBNames = new HashSet<string>();

        if (quest.CompleteOtherQuests != null && quest.CompleteOtherQuests.Count > 0)
        {
            foreach (var otherQuest in quest.CompleteOtherQuests)
            {
                if (otherQuest != null && !string.IsNullOrEmpty(otherQuest.DBName) && seenDBNames.Add(otherQuest.DBName))
                {
                    records.Add(new QuestCompleteOtherQuestRecord
                    {
                        QuestId = questDbIndex,
                        CompletedQuestDBName = otherQuest.DBName
                    });
                }
            }
        }

        return records;
    }
}