#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;
using static CoordinateRecord;

public class CharacterListener : IAssetScanListener<Character>
{
    private readonly SQLiteConnection _db;
    private readonly List<CoordinateRecord> _coordinateRecords = new();
    private readonly List<CharacterRecord> _characterRecords = new();
    private readonly List<CharacterDialogRecord> _characterDialogRecords = new();

    public CharacterListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<CharacterRecord>();
        _db.CreateTable<CharacterDialogRecord>();

        _db.RunInTransaction(() =>
        {
            _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Character));
            _db.DeleteAll<CharacterRecord>();
            _db.DeleteAll<CharacterDialogRecord>();

            _db.InsertAll(_coordinateRecords);
            _db.InsertAll(_characterRecords);
            _db.InsertAll(_characterDialogRecords);
        });
        
        _coordinateRecords.Clear();
        _characterRecords.Clear();
        _characterDialogRecords.Clear();
        
        _db.Execute(@"
            UPDATE Characters
            SET IsCommon = 1
            WHERE Guid IN
            (
                SELECT DISTINCT c.Guid
                FROM Characters c
                LEFT JOIN SpawnPointCharacters spc ON spc.CharacterGuid = c.Guid
                WHERE NOT c.IsPrefab OR (spc.IsCommon AND spc.SpawnChance > 0)
            );
        ");

        _db.Execute(@"
            UPDATE Characters
            SET IsRare = 1
            WHERE Guid IN
            (
                SELECT DISTINCT c.Guid
                FROM Characters c
                JOIN SpawnPointCharacters spc ON spc.CharacterGuid = c.Guid
                WHERE spc.IsRare AND spc.SpawnChance > 0
            );
        ");

        _db.Execute(@"
            UPDATE Characters
            SET IsUnique = 1
            WHERE NPCName IN
            (
                SELECT NPCName
                FROM
                (
                    SELECT count(DISTINCT spc.SpawnPointId) AS spawnPointCount, count(DISTINCT c.Guid) AS instanceCount, *
                    FROM Characters c
                    LEFT JOIN SpawnPointCharacters spc ON spc.CharacterGuid = c.Guid
                    WHERE NOT c.IsPrefab OR (spc.SpawnChance > 0)
                    GROUP BY c.NPCName
                )
                WHERE ((IsPrefab AND spawnPointCount = 1) OR (NOT IsPrefab AND instanceCount = 1))
            );
        ");
    }

    public void OnAssetFound(Character asset)
    {
        if (asset.GetComponent<MiningNode>() != null)
        {
            return;
        }

        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var coordinateRecord = CreateCoordinateRecord(asset);
        var characterRecord = CreateCharacterRecord(asset, coordinateRecord?.Id);
        _characterRecords.Add(characterRecord);

        if (coordinateRecord != null)
        {
            coordinateRecord.CharacterId = characterRecord.Id;
            _coordinateRecords.Add(coordinateRecord);
        }

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
            _characterDialogRecords.AddRange(dialogRecords);
        }
    }

    private CoordinateRecord? CreateCoordinateRecord(Character character)
    {
        if (character.gameObject.scene.name == null)
        {
            return null;
        }
        
        return new CoordinateRecord
        {
            Scene = character.gameObject.scene.name,
            X = character.transform.position.x,
            Y = character.transform.position.y,
            Z = character.transform.position.z,
            Category = nameof(CoordinateCategory.Character)
        };
    }
    
    private CharacterRecord CreateCharacterRecord(Character character, int? coordinateId)
    {
        var npc = character.GetComponent<NPC>();
        var vendorInventory = character.GetComponent<VendorInventory>();
        var simPlayer = character.GetComponent<SimPlayer>();
        var stats = character.GetComponent<Stats>();
        var hasDialog = character.GetComponents<NPCDialog>().Any(d => !string.IsNullOrWhiteSpace(d.Dialog));
        var modifyFactions = character.GetComponents<ModifyFaction>();
        
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
        
        var record = new CharacterRecord
        {
            Id = TableIdGenerator.NextId(CharacterRecord.TableName),
            CoordinateId = coordinateId,
            Guid = guid,
            ObjectName = character.gameObject != null ? character.gameObject.name : null,
            MyWorldFaction = character.MyWorldFaction != null ? character.MyWorldFaction.FactionName : null,
            MyFaction = character.MyFaction.ToString(),
            AggroRange = character.AggroRange,
            AttackRange = character.AttackRange,
            AggressiveTowards = character.AggressiveTowards != null ? string.Join(", ", character.AggressiveTowards) : null,
            Allies = character.Allies != null ? string.Join(", ", character.Allies) : null,
            IsPrefab = prefabType != PrefabAssetType.NotAPrefab,
            IsUnique = false, // `IsUnique` is set in `OnScanFinished`.
            IsFriendly = new List<string> { "DEBUG", "GoodGuard", "GoodHuman", "OtherGood", "PC", "Player", "Villager"  }.Contains(character.MyFaction.ToString()),
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
            record.AttackSkills = npc.MyAttackSkills == null ? string.Empty : string.Join(", ", npc.MyAttackSkills.Select(skill => $"{skill.SkillName} ({skill.Id})"));
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

        var factionStrings = new List<string>();
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