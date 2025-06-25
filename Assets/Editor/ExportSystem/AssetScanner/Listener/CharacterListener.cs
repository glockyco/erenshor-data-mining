#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;
using static CoordinateDBRecord;

public class CharacterListener : IAssetScanListener<Character>
{
    private readonly SQLiteConnection _db;

    public CharacterListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.CreateTable<CharacterDBRecord>();
        _db.CreateTable<CharacterDialogRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Character));
        _db.DeleteAll<CharacterDBRecord>();
        _db.DeleteAll<CharacterDialogRecord>();
    }

    public void OnScanFinished()
    {
        _db.Execute(@"
            UPDATE Coordinates
            SET CharacterId = (
                SELECT Id
                FROM Characters
                WHERE Characters.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM Characters
                WHERE Characters.CoordinateId = Coordinates.Id
            );
        ");
    }

    public void OnAssetFound(Character asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        if (asset.GetComponent<MiningNode>() != null)
        {
            return;
        }

        var characterRecord = CreateCharacterRecord(asset);
        _db.Insert(characterRecord);

        var dialogs = asset.GetComponents<NPCDialog>().Where(d => !string.IsNullOrWhiteSpace(d.Dialog)).ToList();
        if (dialogs.Count > 0)
        {
            var i = 0;
            var dialogRecords = new List<CharacterDialogRecord>();
            foreach (var dialog in dialogs)
            {
                dialogRecords.Add(CreateDialogRecord(characterRecord.Id, i, dialog));
                i++;
            }
            _db.InsertAll(dialogRecords);
        }
    }
    
    private CharacterDBRecord CreateCharacterRecord(Character character)
    {
        int? coordinateId = null;
        if (character.gameObject.scene.name != null)
        {
            var coordinate = new CoordinateDBRecord
            {
                Scene = character.gameObject.scene.name,
                X = character.transform.position.x,
                Y = character.transform.position.y,
                Z = character.transform.position.z,
                Category = nameof(CoordinateCategory.Character)
            };

            _db.Insert(coordinate);
            
            coordinateId = coordinate.Id;
        }
        
        NPC npc = character.GetComponent<NPC>();
        VendorInventory vendorInventory = character.GetComponent<VendorInventory>();
        SimPlayer simPlayer = character.GetComponent<SimPlayer>();
        Stats stats = character.GetComponent<Stats>();
        bool hasDialog = character.GetComponents<NPCDialog>().Any(d => !string.IsNullOrWhiteSpace(d.Dialog));
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
            CoordinateId = coordinateId,
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
            HasStats = stats != null,
            HasDialog = hasDialog,
            HasModifyFaction = modifyFactions.Length > 0,
            IsEnabled = character.isActiveAndEnabled,
            Invulnerable = character.Invulnerable,
            ShoutOnDeath = character.ShoutOnDeath != null ? string.Join(", ", character.ShoutOnDeath) : null,
            QuestCompleteOnDeath = character.QuestCompleteOnDeath != null ? character.QuestCompleteOnDeath.DBName : null,
            DestroyOnDeath = character.DestroyOnDeath,
        };
        
        if (npc != null)
        {
            record.NPCName = npc.NPCName;
            record.AttackSkills = npc.MyAttackSkills == null ? string.Empty : string.Join(", ", npc.MyAttackSkills.Select(skill => $"{skill.SkillName} ({skill.Id})"));;
            record.AttackSpells = npc.MyAttackSpells == null ? string.Empty : string.Join(", ", npc.MyAttackSpells.Select(spell => $"{spell.SpellName} ({spell.Id})"));
            record.BuffSpells = npc.MyBuffSpells == null ? string.Empty : string.Join(", ", npc.MyBuffSpells.Select(spell => $"{spell.SpellName} ({spell.Id})"));
            record.HealSpells = npc.MyHealSpells == null ? string.Empty : string.Join(", ", npc.MyHealSpells.Select(spell => $"{spell.SpellName} ({spell.Id})"));
            record.GroupHealSpells = npc.GroupHeals == null ? string.Empty : string.Join(", ", npc.GroupHeals.Select(spell => $"{spell.SpellName} ({spell.Id})"));
            record.CCSpells = npc.MyCCSpells == null ? string.Empty : string.Join(", ", npc.MyCCSpells.Select(spell => $"{spell.SpellName} ({spell.Id})"));
            record.TauntSpells = npc.MyTauntSpell == null ? string.Empty : string.Join(", ", npc.MyTauntSpell.Select(spell => $"{spell.SpellName} ({spell.Id})"));
            record.PetSpell = npc.MyPetSpell is null ? string.Empty : $"{npc.MyPetSpell.SpellName} ({npc.MyPetSpell.Id})";
            record.ProcOnHit = npc.NPCProcOnHit is null ? string.Empty : $"{npc.NPCProcOnHit.SpellName} ({npc.NPCProcOnHit.Id})";
            record.ProcOnHitChance = npc.NPCProcOnHitChance;
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
    
    private CharacterDialogRecord CreateDialogRecord(int characterId, int dialogIndex, NPCDialog dialog)
    {
        var keywords = dialog.KeywordToActivate == null || dialog.KeywordToActivate.Count == 0 ? null : string.Join(", ", dialog.KeywordToActivate);
        var repeatingQuestDialog = dialog.RepeatingQuestDialog == "" ? null : dialog.RepeatingQuestDialog.Trim();

        return new CharacterDialogRecord
        {
            CharacterId = characterId,
            DialogIndex = dialogIndex,
            DialogText = dialog.Dialog.Trim(),
            Keywords = keywords,
            GiveItemName = dialog.GiveItem?.ItemName,
            AssignQuestDBName = dialog.QuestToAssign?.DBName,
            CompleteQuestDBName = dialog.QuestToComplete?.DBName,
            RepeatingQuestDialog = repeatingQuestDialog,
            KillSelfOnSay = dialog.KillMeOnSay,
            RequiredQuestDBName = dialog.RequireQuestComplete?.DBName,
            SpawnName = dialog.Spawn != null ? dialog.Spawn.name : null,
        };
    }
}