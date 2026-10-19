#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class QuestListener : IAssetScanListener<Quest>
{
    private readonly SQLiteConnection _db;
    private readonly List<QuestRecord> _records = new(); // Canonical quests (one per DBName)
    private readonly List<QuestVariantRecord> _variantRecords = new(); // All quest variants
    private readonly List<QuestRequiredItemRecord> _questRequiredItemRecords = new();
    private readonly List<QuestFactionAffectRecord> _questFactionAffectRecords = new();
    private readonly List<QuestCompleteOtherQuestRecord> _questCompleteOtherQuestRecords = new();
    private readonly HashSet<string> _seenDBNames = new(); // Track which DBNames we've seen

    public QuestListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        // Insert canonical quests (one per DBName)
        _db.CreateTable<QuestRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<QuestRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();

        // Insert all quest variants
        _db.CreateTable<QuestVariantRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<QuestVariantRecord>();
            _db.InsertAll(_variantRecords);
        });
        _variantRecords.Clear();

        // Create and insert junction table records after parent records are inserted
        _db.CreateTable<QuestRequiredItemRecord>();
        _db.CreateTable<QuestFactionAffectRecord>();
        _db.CreateTable<QuestCompleteOtherQuestRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<QuestRequiredItemRecord>();
            _db.DeleteAll<QuestFactionAffectRecord>();
            _db.DeleteAll<QuestCompleteOtherQuestRecord>();
            _db.InsertAll(_questRequiredItemRecords);
            _db.InsertAll(_questFactionAffectRecords);
            _db.InsertAll(_questCompleteOtherQuestRecords);
        });
        _questRequiredItemRecords.Clear();
        _questFactionAffectRecords.Clear();
        _questCompleteOtherQuestRecords.Clear();
    }

    public void OnAssetFound(Quest asset)
    {
        var questStableKey = StableKeyGenerator.ForQuest(asset);

        // Add canonical quest record (one per DBName) - only on first encounter
        if (!_seenDBNames.Contains(asset.DBName))
        {
            _seenDBNames.Add(asset.DBName);
            _records.Add(new QuestRecord { StableKey = questStableKey, DBName = asset.DBName });
        }

        // Add variant record (one per Quest ScriptableObject) - always
        _variantRecords.Add(CreateVariantRecord(asset, _variantRecords.Count, questStableKey));

        // Add junction table records (one set per variant)
        _questRequiredItemRecords.AddRange(CreateQuestRequiredItemRecords(asset));
        _questFactionAffectRecords.AddRange(CreateQuestFactionAffectRecords(asset));
        _questCompleteOtherQuestRecords.AddRange(CreateQuestCompleteOtherQuestRecords(asset));
    }

    private QuestVariantRecord CreateVariantRecord(
        Quest quest,
        int questDbIndex,
        string questStableKey
    )
    {
        return new QuestVariantRecord
        {
            // --- Core Identification ---
            ResourceName = quest.name,
            QuestStableKey = questStableKey,
            QuestDBIndex = questDbIndex,
            QuestName = quest.QuestName,
            QuestDesc = quest.QuestDesc,

            // --- Rewards & Completion ---
            XPonComplete = quest.XPonComplete,
            ItemOnCompleteStableKey =
                quest.ItemOnComplete != null
                    ? StableKeyGenerator.ForItem(quest.ItemOnComplete)
                    : null,
            GoldOnComplete = quest.GoldOnComplete,
            AssignNewQuestOnCompleteStableKey =
                quest.AssignNewQuestOnComplete != null
                    ? StableKeyGenerator.ForQuest(quest.AssignNewQuestOnComplete)
                    : null,

            // --- Dialog & Text ---
            DialogOnSuccess = quest.DialogOnSuccess,
            DialogOnPartialSuccess = quest.DialogOnPartialSuccess,
            DisableText = quest.DisableText,

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

            // --- Vendor Unlocks ---
            UnlockItemForVendorStableKey =
                quest.UnlockItemForVendor != null
                    ? StableKeyGenerator.ForItem(quest.UnlockItemForVendor)
                    : null,
        };
    }

    private List<QuestRequiredItemRecord> CreateQuestRequiredItemRecords(Quest quest)
    {
        var records = new List<QuestRequiredItemRecord>();

        if (quest.RequiredItems == null || quest.RequiredItems.Count == 0)
            return records;

        for (var index = 0; index < quest.RequiredItems.Count; index++)
        {
            var item = quest.RequiredItems[index];
            if (item == null || string.IsNullOrEmpty(item.name))
                continue;
            records.Add(
                new QuestRequiredItemRecord
                {
                    QuestVariantResourceName = quest.name,
                    RequiredSlot = index + 1,
                    ItemStableKey = StableKeyGenerator.ForItem(item),
                    Quantity = 1,
                }
            );
        }

        return records;
    }

    // code-fact: faction.quest_hits_equal_lists
    // FinishQuest changes standings only when the faction and amount lists have
    // the same length, and it pairs them by slot.
    private List<QuestFactionAffectRecord> CreateQuestFactionAffectRecords(Quest quest)
    {
        var records = new List<QuestFactionAffectRecord>();
        var factions = quest.AffectFactions;
        var amounts = quest.AffectFactionAmts;
        if (
            factions == null
            || amounts == null
            || factions.Count == 0
            || factions.Count != amounts.Count
        )
            return records;

        var seenFactionStableKeys = new HashSet<string>();
        for (var slot = 0; slot < factions.Count; slot++)
        {
            var faction = factions[slot];
            var amount = amounts[slot];
            // FinishQuest reads the faction of every slot, so an empty slot throws in the game.
            if (faction == null || string.IsNullOrEmpty(faction.REFNAME))
                throw new InvalidOperationException($"{quest.name}: faction slot {slot} is empty");
            var factionStableKey = StableKeyGenerator.ForFaction(faction);
            if (!seenFactionStableKeys.Add(factionStableKey))
                throw new InvalidOperationException(
                    $"{quest.name}: lists {factionStableKey} twice"
                );
            if (amount != Mathf.Round(amount))
                throw new InvalidOperationException(
                    $"{quest.name}: faction amount {amount} is not a whole number"
                );
            records.Add(
                new QuestFactionAffectRecord
                {
                    QuestVariantResourceName = quest.name,
                    FactionStableKey = factionStableKey,
                    ModifierValue = (int)amount,
                }
            );
        }

        return records;
    }

    private List<QuestCompleteOtherQuestRecord> CreateQuestCompleteOtherQuestRecords(Quest quest)
    {
        var records = new List<QuestCompleteOtherQuestRecord>();
        var seenCompletedQuestStableKeys = new HashSet<string>();

        if (quest.CompleteOtherQuests != null && quest.CompleteOtherQuests.Count > 0)
        {
            foreach (var otherQuest in quest.CompleteOtherQuests)
            {
                if (otherQuest != null && !string.IsNullOrEmpty(otherQuest.DBName))
                {
                    var completedQuestStableKey = StableKeyGenerator.ForQuest(otherQuest);
                    if (seenCompletedQuestStableKeys.Add(completedQuestStableKey))
                    {
                        records.Add(
                            new QuestCompleteOtherQuestRecord
                            {
                                QuestVariantResourceName = quest.name,
                                CompletedQuestStableKey = completedQuestStableKey,
                            }
                        );
                    }
                }
            }
        }

        return records;
    }
}
