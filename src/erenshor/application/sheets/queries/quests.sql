SELECT
    qv.QuestDBIndex,
    q.StableKey,
    qv.QuestName,
    qv.QuestDesc,
    qv.XPonComplete,
    qv.ItemOnCompleteStableKey,
    qv.GoldOnComplete,
    qv.AssignNewQuestOnCompleteStableKey,
    qv.DialogOnSuccess,
    qv.DialogOnPartialSuccess,
    qv.DisableText,
    qv.AssignThisQuestOnPartialComplete,
    qv.Repeatable,
    qv.DisableQuest,
    qv.KillTurnInHolder,
    qv.DestroyTurnInHolder,
    qv.DropInvulnOnHolder,
    qv.OncePerSpawnInstance,
    qv.SetAchievementOnGet,
    qv.SetAchievementOnFinish
FROM Quests q
LEFT JOIN QuestVariants qv ON qv.QuestStableKey = q.StableKey;
