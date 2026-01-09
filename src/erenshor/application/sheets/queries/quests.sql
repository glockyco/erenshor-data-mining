-- Consolidated quest information
SELECT
    qv.QuestDBIndex,
    q.StableKey,
    qv.QuestName,
    qv.QuestDesc,
    COALESCE(
        (SELECT GROUP_CONCAT(DISTINCT Method) FROM QuestCompletionSources WHERE QuestStableKey = q.StableKey),
        'unknown'
    ) AS CompletionMethods,

    -- Rewards
    qv.XPonComplete,
    qv.GoldOnComplete,
    reward_item.ItemName AS RewardItem,
    next_quest_variant.QuestName AS NextQuest,
    unlock_item.ItemName AS UnlockItemForVendor,

    -- NPC Relationships (aggregated)
    (SELECT GROUP_CONCAT(DISTINCT c.NPCName)
     FROM QuestCharacterRoles qcr
     JOIN Characters c ON c.StableKey = qcr.CharacterStableKey
     WHERE qcr.QuestStableKey = q.StableKey AND qcr.Role = 'giver'
    ) AS GiverNPCs,
    (SELECT GROUP_CONCAT(DISTINCT c.NPCName)
     FROM QuestCharacterRoles qcr
     JOIN Characters c ON c.StableKey = qcr.CharacterStableKey
     WHERE qcr.QuestStableKey = q.StableKey AND qcr.Role = 'completer'
    ) AS CompleterNPCs,
    (SELECT GROUP_CONCAT(DISTINCT c.NPCName)
     FROM QuestCharacterRoles qcr
     JOIN Characters c ON c.StableKey = qcr.CharacterStableKey
     WHERE qcr.QuestStableKey = q.StableKey AND qcr.Role = 'item_turnin'
    ) AS ItemTurninNPCs,

    -- Required Items (aggregated)
    (SELECT GROUP_CONCAT(DISTINCT i.ItemName)
     FROM QuestRequiredItems qri
     JOIN Items i ON i.StableKey = qri.ItemStableKey
     WHERE qri.QuestVariantResourceName = qv.ResourceName
    ) AS RequiredItems,

    -- Faction Impacts (aggregated with modifier)
    (SELECT GROUP_CONCAT(DISTINCT f.FactionName || ' (' || qfa.ModifierValue || ')')
     FROM QuestFactionAffects qfa
     JOIN Factions f ON f.StableKey = qfa.FactionStableKey
     WHERE qfa.QuestVariantResourceName = qv.ResourceName
    ) AS FactionAffects,

    -- Quest Chains - this quest completes other quests
    (SELECT GROUP_CONCAT(DISTINCT completed_qv.QuestName)
     FROM QuestCompleteOtherQuests qcoq
     JOIN QuestVariants completed_qv ON completed_qv.QuestStableKey = qcoq.CompletedQuestStableKey
     WHERE qcoq.QuestVariantResourceName = qv.ResourceName
    ) AS CompletesQuests,

    -- Quest Chains - quests that complete this quest
    (SELECT GROUP_CONCAT(DISTINCT completing_qv.QuestName)
     FROM QuestCompleteOtherQuests qcoq
     JOIN QuestVariants completing_qv ON completing_qv.ResourceName = qcoq.QuestVariantResourceName
     WHERE qcoq.CompletedQuestStableKey = q.StableKey
    ) AS CompletedByQuests,

    -- Flags
    qv.Repeatable,
    qv.DisableQuest,
    qv.KillTurnInHolder,
    qv.DestroyTurnInHolder,
    qv.DropInvulnOnHolder,
    qv.OncePerSpawnInstance,
    qv.AssignThisQuestOnPartialComplete,

    -- Achievements
    qv.SetAchievementOnGet,
    qv.SetAchievementOnFinish,

    -- Dialog
    qv.DialogOnSuccess,
    qv.DialogOnPartialSuccess,
    qv.DisableText

FROM Quests q
LEFT JOIN QuestVariants qv ON qv.QuestStableKey = q.StableKey
LEFT JOIN Items reward_item ON reward_item.StableKey = qv.ItemOnCompleteStableKey
LEFT JOIN Items unlock_item ON unlock_item.StableKey = qv.UnlockItemForVendorStableKey
LEFT JOIN QuestVariants next_quest_variant ON next_quest_variant.QuestStableKey = qv.AssignNewQuestOnCompleteStableKey
ORDER BY qv.QuestDBIndex;
