#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;

public class CharacterListener : IAssetScanListener<Character>
{
    private readonly SQLiteConnection _db;
    private readonly List<CharacterDBRecord> _records = new();

    public CharacterListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<CharacterDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<CharacterDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Character asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }
    
    private CharacterDBRecord CreateRecord(Character character)
    {
        NPC npc = character.GetComponent<NPC>();
        VendorInventory vendorInventory = character.GetComponent<VendorInventory>();
        MiningNode miningNode = character.GetComponent<MiningNode>();
        SimPlayer simPlayer = character.GetComponent<SimPlayer>();
        Stats stats = character.GetComponent<Stats>();
        ModifyFaction[] modifyFactions = character.GetComponents<ModifyFaction>();
        
        string guid;
        var prefabType = PrefabUtility.GetPrefabAssetType(character.gameObject);
        if (prefabType != PrefabAssetType.NotAPrefab)
        {
            var prefabPath = AssetDatabase.GetAssetPath(character.gameObject);
            guid = AssetDatabase.AssetPathToGUID(prefabPath);
        }
        else
        {
            var sceneName = character.gameObject.scene.name;
            guid = $"scene:{sceneName}:{character.gameObject.GetInstanceID()}";
        }
        
        CharacterDBRecord record = new CharacterDBRecord
        {
            Guid = guid,
            ObjectName = character.gameObject != null ? character.gameObject.name : null,
            MyWorldFaction = character.MyWorldFaction != null ? character.MyWorldFaction.FactionName : null,
            MyFaction = character.MyFaction.ToString(),
            AggroRange = character.AggroRange,
            AttackRange = character.AttackRange,
            AggressiveTowards = character.AggressiveTowards != null ? string.Join(", ", character.AggressiveTowards) : null,
            Allies = character.Allies != null ? string.Join(", ", character.Allies) : null,
            IsNPC = npc != null,
            IsSimPlayer = simPlayer != null,
            IsVendor = vendorInventory != null,
            IsMiningNode = miningNode != null,
            HasStats = stats != null,
            HasModifyFaction = modifyFactions.Length > 0,
            Invulnerable = character.Invulnerable,
            ShoutOnDeath = character.ShoutOnDeath != null ? string.Join(", ", character.ShoutOnDeath) : null,
            QuestCompleteOnDeath = character.QuestCompleteOnDeath != null ? character.QuestCompleteOnDeath.DBName : null,
            DestroyOnDeath = character.DestroyOnDeath,
        };
        
        if (npc != null)
        {
            record.NPCName = npc.NPCName;
        }
        
        if (stats != null)
        {
            record.Level = stats.Level;
            record.BaseHP = stats.BaseHP;
            record.BaseAC = stats.BaseAC;
            record.BaseMana = stats.BaseMana;
            record.BaseStr = stats.BaseStr;
            record.BaseEnd = stats.BaseEnd;
            record.BaseDex = stats.BaseDex;
            record.BaseAgi = stats.BaseAgi;
            record.BaseInt = stats.BaseInt;
            record.BaseWis = stats.BaseWis;
            record.BaseCha = stats.BaseCha;
            record.BaseRes = stats.BaseRes;
            record.BaseMR = stats.BaseMR;
            record.BaseER = stats.BaseER;
            record.BasePR = stats.BasePR;
            record.BaseVR = stats.BaseVR;
            record.RunSpeed = stats.RunSpeed;
            record.BaseLifeSteal = stats.BaseLifesteal;
            record.BaseMHAtkDelay = stats.BaseMHAtkDelay;
            record.BaseOHAtkDelay = stats.BaseOHAtkDelay;
            record.BaseXpMin = stats.Level * 4;
            record.BaseXpMax = record.BaseXpMin + stats.Level * 5;
            record.BossXpMultiplier = character.BossXp;
        }

        List<string> factionStrings = new List<string>();
        foreach (ModifyFaction modifyFaction in modifyFactions)
        {
            if (modifyFaction != null && modifyFaction.Factions != null)
            {
                factionStrings.AddRange(modifyFaction.Factions.Select(f => $"{f.FactionName} ({modifyFaction.Modifier})"));
            }
        }
        record.ModifyFactions = string.Join(", ", factionStrings);

        if (vendorInventory != null)
        {
            record.VendorDesc = vendorInventory.VendorDesc;
            record.ItemsForSale = vendorInventory.ItemsForSale != null ? string.Join(", ", vendorInventory.ItemsForSale.Select(i => i.ItemName)) : null;
        }

        return record;
    }
}