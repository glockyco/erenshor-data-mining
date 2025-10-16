SELECT
    CharacterId,
    NPCName,
    DialogIndex,
    DialogText,
    Keywords,
    GiveItemName,
    AssignQuestDBName,
    CompleteQuestDBName,
    RepeatingQuestDialog,
    KillSelfOnSay,
    RequiredQuestDBName,
    SpawnName
FROM CharacterDialogs cd
JOIN Characters c ON c.Id = cd.CharacterId
ORDER BY NPCName, CharacterId, DialogIndex;
