namespace AdventureGuide.Data;

public sealed partial class GuideData
{
    /// <summary>
    /// Scan the game's QuestDB for quests not in the guide and create
    /// stub entries with name and description. Returns the number of
    /// quests discovered.
    /// Returns the count of discovered quests, or -1 if QuestDB
    /// is not yet available (caller should retry later).
    /// </summary>
    public int MergeUnknownQuests()
    {
        var db = GameData.QuestDB;
        if (db == null || db.QuestDatabase == null)
            return -1;

        int count = 0;
        foreach (var quest in db.QuestDatabase)
        {
            if (quest == null)
                continue;
            if (string.IsNullOrEmpty(quest.DBName))
                continue;
            if (_byDBName.ContainsKey(quest.DBName))
                continue;

            var stub = new QuestEntry
            {
                DBName = quest.DBName,
                DisplayName = quest.QuestName ?? quest.DBName,
                Description = quest.QuestDesc,
            };
            _all.Add(stub);
            _byDBName[stub.DBName] = stub;
            count++;
        }
        return count;
    }
}
