SELECT
    c.StableKey AS CharacterStableKey,
    c.NPCName,
    cd.DialogIndex,
    cd.DialogText,
    cd.Keywords,
    cd.GiveItemStableKey,
    cd.AssignQuestStableKey,
    cd.CompleteQuestStableKey,
    cd.RepeatingQuestDialog,
    cd.KillSelfOnSay,
    cd.RequiredQuestStableKey,
    cd.SpawnCharacterStableKey
FROM CharacterDialogs cd
JOIN Characters c ON c.StableKey = cd.CharacterStableKey
ORDER BY NPCName, CharacterStableKey, DialogIndex;
