#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class NpcDialogListener : IAssetScanListener<NPCDialog>
{
    private readonly SQLiteConnection _db;
    private readonly List<NPCDialogDBRecord> _records = new();
    private readonly Dictionary<string, int> _dialogCounts = new();

    public NpcDialogListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<NPCDialogDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<NPCDialogDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
        _dialogCounts.Clear();
    }

    public void OnAssetFound(NPCDialog asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private NPCDialogDBRecord CreateRecord(NPCDialog dialog)
    {
        NPC npc = dialog.gameObject.GetComponent<NPC>();
        var keywords = dialog.KeywordToActivate ?? new List<string>();

        int dialogIndex = _dialogCounts.GetValueOrDefault(npc.NPCName, 0);
        _dialogCounts[npc.NPCName] = dialogIndex + 1;

        return new NPCDialogDBRecord
        {
            NPCName = npc.NPCName,
            DialogIndex = dialogIndex,
            DialogText = dialog.Dialog,
            Keywords = string.Join(", ", keywords),
            GiveItemName = dialog.GiveItem?.ItemName,
            AssignQuestDBName = dialog.QuestToAssign?.DBName,
            CompleteQuestDBName = dialog.QuestToComplete?.DBName,
            RepeatingQuestDialog = dialog.RepeatingQuestDialog,
            KillSelfOnSay = dialog.KillMeOnSay,
            RequiredQuestDBName = dialog.RequireQuestComplete?.DBName,
            SpawnName = dialog.Spawn != null ? dialog.Spawn.name : null,
        };
    }
}