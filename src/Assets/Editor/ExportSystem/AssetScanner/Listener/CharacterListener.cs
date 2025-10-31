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
    private readonly List<CharacterAttackSkillRecord> _characterAttackSkillRecords = new();
    private readonly List<CharacterAttackSpellRecord> _characterAttackSpellRecords = new();
    private readonly List<CharacterBuffSpellRecord> _characterBuffSpellRecords = new();
    private readonly List<CharacterHealSpellRecord> _characterHealSpellRecords = new();
    private readonly List<CharacterGroupHealSpellRecord> _characterGroupHealSpellRecords = new();
    private readonly List<CharacterCCSpellRecord> _characterCCSpellRecords = new();
    private readonly List<CharacterTauntSpellRecord> _characterTauntSpellRecords = new();
    private readonly List<CharacterVendorItemRecord> _characterVendorItemRecords = new();
    private readonly List<CharacterAggressiveFactionRecord> _characterAggressiveFactionRecords = new();
    private readonly List<CharacterAlliedFactionRecord> _characterAlliedFactionRecords = new();
    private readonly List<CharacterFactionModifierRecord> _characterFactionModifierRecords = new();
    private readonly List<CharacterDeathShoutRecord> _characterDeathShoutRecords = new();

    // Store ability ResourceNames (not NPC references) for deferred junction record creation
    private readonly List<(int characterId, List<string> attackSkillResourceNames, List<string> attackSpellResourceNames, List<string> buffSpellResourceNames, List<string> healSpellResourceNames, List<string> groupHealSpellResourceNames, List<string> ccSpellResourceNames, List<string> tauntSpellResourceNames)> _npcAbilityData = new();
    private Dictionary<string, string>? _factionNameToRefNameCache = null;
    private readonly List<string> _lookupErrors = new();

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

        // Populate FK lookup cache for factions (WorldFactionRecord table is now populated if faction entities were exported)
        _factionNameToRefNameCache = TableExists<WorldFactionRecord>()
            ? _db.Table<WorldFactionRecord>().ToDictionary(f => f.FactionName, f => f.REFNAME)
            : new Dictionary<string, string>();

        // Process saved ability data to create junction records
        foreach (var (characterId, attackSkillResourceNames, attackSpellResourceNames, buffSpellResourceNames, healSpellResourceNames, groupHealSpellResourceNames, ccSpellResourceNames, tauntSpellResourceNames) in _npcAbilityData)
        {
            _characterAttackSkillRecords.AddRange(CreateCharacterAttackSkillRecords(characterId, attackSkillResourceNames));
            _characterAttackSpellRecords.AddRange(CreateCharacterAttackSpellRecords(characterId, attackSpellResourceNames));
            _characterBuffSpellRecords.AddRange(CreateCharacterBuffSpellRecords(characterId, buffSpellResourceNames));
            _characterHealSpellRecords.AddRange(CreateCharacterHealSpellRecords(characterId, healSpellResourceNames));
            _characterGroupHealSpellRecords.AddRange(CreateCharacterGroupHealSpellRecords(characterId, groupHealSpellResourceNames));
            _characterCCSpellRecords.AddRange(CreateCharacterCCSpellRecords(characterId, ccSpellResourceNames));
            _characterTauntSpellRecords.AddRange(CreateCharacterTauntSpellRecords(characterId, tauntSpellResourceNames));
        }

        // Fail if any lookup errors occurred during junction record creation
        if (_lookupErrors.Count > 0)
        {
            string errorSummary = $"[CharacterListener] Failed to lookup {_lookupErrors.Count} spell/skill references:\n" +
                                  string.Join("\n", _lookupErrors);
            Debug.LogError(errorSummary);
            throw new System.Exception(errorSummary);
        }

        _db.CreateTable<CharacterAttackSkillRecord>();
        _db.CreateTable<CharacterAttackSpellRecord>();
        _db.CreateTable<CharacterBuffSpellRecord>();
        _db.CreateTable<CharacterHealSpellRecord>();
        _db.CreateTable<CharacterGroupHealSpellRecord>();
        _db.CreateTable<CharacterCCSpellRecord>();
        _db.CreateTable<CharacterTauntSpellRecord>();
        _db.CreateTable<CharacterVendorItemRecord>();
        _db.CreateTable<CharacterAggressiveFactionRecord>();
        _db.CreateTable<CharacterAlliedFactionRecord>();
        _db.CreateTable<CharacterFactionModifierRecord>();
        _db.CreateTable<CharacterDeathShoutRecord>();

        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<CharacterAttackSkillRecord>();
            _db.DeleteAll<CharacterAttackSpellRecord>();
            _db.DeleteAll<CharacterBuffSpellRecord>();
            _db.DeleteAll<CharacterHealSpellRecord>();
            _db.DeleteAll<CharacterGroupHealSpellRecord>();
            _db.DeleteAll<CharacterCCSpellRecord>();
            _db.DeleteAll<CharacterTauntSpellRecord>();
            _db.DeleteAll<CharacterVendorItemRecord>();
            _db.DeleteAll<CharacterAggressiveFactionRecord>();
            _db.DeleteAll<CharacterAlliedFactionRecord>();
            _db.DeleteAll<CharacterFactionModifierRecord>();
            _db.DeleteAll<CharacterDeathShoutRecord>();

            _db.InsertAll(_characterAttackSkillRecords);
            _db.InsertAll(_characterAttackSpellRecords);
            _db.InsertAll(_characterBuffSpellRecords);
            _db.InsertAll(_characterHealSpellRecords);
            _db.InsertAll(_characterGroupHealSpellRecords);
            _db.InsertAll(_characterCCSpellRecords);
            _db.InsertAll(_characterTauntSpellRecords);
            _db.InsertAll(_characterVendorItemRecords);
            _db.InsertAll(_characterAggressiveFactionRecords);
            _db.InsertAll(_characterAlliedFactionRecords);
            _db.InsertAll(_characterFactionModifierRecords);
            _db.InsertAll(_characterDeathShoutRecords);
        });

        _characterAttackSkillRecords.Clear();
        _characterAttackSpellRecords.Clear();
        _characterBuffSpellRecords.Clear();
        _characterHealSpellRecords.Clear();
        _characterGroupHealSpellRecords.Clear();
        _characterCCSpellRecords.Clear();
        _characterTauntSpellRecords.Clear();
        _characterVendorItemRecords.Clear();
        _characterAggressiveFactionRecords.Clear();
        _characterAlliedFactionRecords.Clear();
        _characterFactionModifierRecords.Clear();
        _characterDeathShoutRecords.Clear();
        _npcAbilityData.Clear();

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

        var npc = asset.GetComponent<NPC>();
        if (npc != null)
        {
            // Extract ability ResourceNames NOW (while assets are loaded) for junction record creation
            var attackSkillResourceNames = npc.MyAttackSkills?.Where(s => s != null && !string.IsNullOrEmpty(s.name)).Select(s => s.name).ToList() ?? new List<string>();
            var attackSpellResourceNames = npc.MyAttackSpells?.Where(s => s != null && !string.IsNullOrEmpty(s.name)).Select(s => s.name).ToList() ?? new List<string>();
            var buffSpellResourceNames = npc.MyBuffSpells?.Where(s => s != null && !string.IsNullOrEmpty(s.name)).Select(s => s.name).ToList() ?? new List<string>();
            var healSpellResourceNames = npc.MyHealSpells?.Where(s => s != null && !string.IsNullOrEmpty(s.name)).Select(s => s.name).ToList() ?? new List<string>();
            var groupHealSpellResourceNames = npc.GroupHeals?.Where(s => s != null && !string.IsNullOrEmpty(s.name)).Select(s => s.name).ToList() ?? new List<string>();
            var ccSpellResourceNames = npc.MyCCSpells?.Where(s => s != null && !string.IsNullOrEmpty(s.name)).Select(s => s.name).ToList() ?? new List<string>();
            var tauntSpellResourceNames = npc.MyTauntSpell?.Where(s => s != null && !string.IsNullOrEmpty(s.name)).Select(s => s.name).ToList() ?? new List<string>();

            _npcAbilityData.Add((characterRecord.Id, attackSkillResourceNames, attackSpellResourceNames, buffSpellResourceNames, healSpellResourceNames, groupHealSpellResourceNames, ccSpellResourceNames, tauntSpellResourceNames));
        }

        var vendorInventory = asset.GetComponent<VendorInventory>();
        if (vendorInventory != null)
        {
            _characterVendorItemRecords.AddRange(CreateCharacterVendorItemRecords(characterRecord.Id, vendorInventory));
        }

        // Phase 2C: Faction and Death Shout junction tables
        _characterAggressiveFactionRecords.AddRange(CreateCharacterAggressiveFactionRecords(characterRecord.Id, asset));
        _characterAlliedFactionRecords.AddRange(CreateCharacterAlliedFactionRecords(characterRecord.Id, asset));

        var modifyFactions = asset.GetComponents<ModifyFaction>();
        foreach (var modifyFaction in modifyFactions)
        {
            _characterFactionModifierRecords.AddRange(CreateCharacterFactionModifierRecords(characterRecord.Id, modifyFaction));
        }

        _characterDeathShoutRecords.AddRange(CreateCharacterDeathShoutRecords(characterRecord.Id, asset));
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
            MyWorldFaction = character.MyWorldFaction != null ? character.MyWorldFaction.REFNAME : null,
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
            
            // NPC Combat Mechanics
            record.HandSetResistances = npc.HandSetResistances;
            record.HardSetAC = npc.HardSetAC;
            record.BaseAtkDmg = npc.BaseAtkDmg;
            record.OHAtkDmg = npc.OHAtkDmg;
            record.MinAtkDmg = npc.MinAtkDmg;
            record.DamageRangeMin = npc.DamageRange.x;
            record.DamageRangeMax = npc.DamageRange.y;
            record.DamageMult = npc.DamageMult;
            record.ArmorPenMult = npc.ArmorPenMult;
            
            // Special Abilities
            record.PowerAttackBaseDmg = npc.PowerAttackBaseDmg;
            record.PowerAttackFreq = npc.PowerAttackFreq;
            record.HealTolerance = npc.HealTolerance;
            
            // AI Behavior
            record.LeashRange = npc.LeashRange;
            record.AggroRegardlessOfLevel = npc.AggroRegardlessOfLevel;
            record.Mobile = npc.Mobile;
            record.GroupEncounter = npc.GroupEncounter;
            
            // Loot/Corpse
            record.TreasureChest = npc.TreasureChest;
            record.DoNotLeaveCorpse = npc.DoNotLeaveCorpse;
            
            // Achievements
            record.SetAchievementOnDefeat = npc.SetAchievementOnDefeat ?? string.Empty;
            record.SetAchievementOnSpawn = npc.SetAchievementOnSpawn ?? string.Empty;
            
            // Flavor Text
            record.AggroMsg = npc.AggroMsg ?? string.Empty;
            record.AggroEmote = npc.AggroEmote ?? string.Empty;
            record.SpawnEmote = npc.SpawnEmote ?? string.Empty;
            record.GuildName = npc.GuildName ?? string.Empty;
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
            
            // Calculate effective stats based on game logic
            if (npc != null && simPlayer == null)
            {
                if (!npc.HandSetResistances)
                {
                    // NPCs without HandSetResistances use calculated resistance ranges
                    record.EffectiveMinMR = Mathf.RoundToInt(stats.Level * 0.5f);
                    record.EffectiveMaxMR = Mathf.RoundToInt(stats.Level * 1.2f);
                    record.EffectiveMinER = Mathf.RoundToInt(stats.Level * 0.5f);
                    record.EffectiveMaxER = Mathf.RoundToInt(stats.Level * 1.2f);
                    record.EffectiveMinPR = Mathf.RoundToInt(stats.Level * 0.5f);
                    record.EffectiveMaxPR = Mathf.RoundToInt(stats.Level * 1.2f);
                    record.EffectiveMinVR = Mathf.RoundToInt(stats.Level * 0.5f);
                    record.EffectiveMaxVR = Mathf.RoundToInt(stats.Level * 1.2f);
                }
                else
                {
                    // NPCs with HandSetResistances use fixed prefab values
                    record.EffectiveMinMR = record.EffectiveMaxMR = stats.BaseMR;
                    record.EffectiveMinER = record.EffectiveMaxER = stats.BaseER;
                    record.EffectiveMinPR = record.EffectiveMaxPR = stats.BasePR;
                    record.EffectiveMinVR = record.EffectiveMaxVR = stats.BaseVR;
                }

                // BaseAtkDmg is set to at least Level for NPCs
                record.EffectiveBaseAtkDmg = Mathf.Max(npc.BaseAtkDmg, stats.Level);

                // Calculate effective AC for NPCs
                int baseAC = npc.HardSetAC > 0 ? npc.HardSetAC : stats.Level * 15;

                // Apply CharacterClass MitigationBonus if set, otherwise use DefaultNPC (1.0)
                float mitigationBonus = 1.0f; // Default for NPCs
                if (stats.CharacterClass != null)
                {
                    mitigationBonus = stats.CharacterClass.MitigationBonus;
                }

                record.EffectiveAC = Mathf.RoundToInt(baseAC * mitigationBonus);

                // Calculate effective HP for NPCs (OverrideHPforNPC = true)
                record.EffectiveHP = stats.BaseHP;

                // Calculate effective attack ability for NPCs
                float baseAttackAbility = 100 + (stats.Level - 1) * 40;
                if (stats.Level >= 20)
                {
                    float levelProgress = Mathf.Clamp01((stats.Level - 20f) / 20f);
                    float smoothBonus = 3f * levelProgress * levelProgress - 2f * levelProgress * levelProgress * levelProgress;
                    float bonusMultiplier = 0.33f * smoothBonus;
                    baseAttackAbility += baseAttackAbility * bonusMultiplier;
                }
                record.EffectiveAttackAbility = baseAttackAbility * npc.ArmorPenMult;
            }
            else
            {
                // SimPlayers and non-NPCs use their base resistance values
                record.EffectiveMinMR = record.EffectiveMaxMR = stats.BaseMR;
                record.EffectiveMinER = record.EffectiveMaxER = stats.BaseER;
                record.EffectiveMinPR = record.EffectiveMaxPR = stats.BasePR;
                record.EffectiveMinVR = record.EffectiveMaxVR = stats.BaseVR;
                record.EffectiveBaseAtkDmg = npc?.BaseAtkDmg ?? 0;
                record.EffectiveAC = 0;
                record.EffectiveHP = 0;
                record.EffectiveAttackAbility = 0;
            }
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

    private List<CharacterAttackSkillRecord> CreateCharacterAttackSkillRecords(int characterId, List<string> skillResourceNames)
    {
        return CreateJunctionRecords(
            skillResourceNames,
            (cId, sResourceName) => new CharacterAttackSkillRecord { CharacterId = cId, SkillResourceName = sResourceName },
            characterId
        );
    }

    private List<CharacterAttackSpellRecord> CreateCharacterAttackSpellRecords(int characterId, List<string> spellResourceNames)
    {
        return CreateJunctionRecords(
            spellResourceNames,
            (cId, sResourceName) => new CharacterAttackSpellRecord { CharacterId = cId, SpellResourceName = sResourceName },
            characterId
        );
    }

    private List<CharacterBuffSpellRecord> CreateCharacterBuffSpellRecords(int characterId, List<string> spellResourceNames)
    {
        return CreateJunctionRecords(
            spellResourceNames,
            (cId, sResourceName) => new CharacterBuffSpellRecord { CharacterId = cId, SpellResourceName = sResourceName },
            characterId
        );
    }

    private List<CharacterHealSpellRecord> CreateCharacterHealSpellRecords(int characterId, List<string> spellResourceNames)
    {
        return CreateJunctionRecords(
            spellResourceNames,
            (cId, sResourceName) => new CharacterHealSpellRecord { CharacterId = cId, SpellResourceName = sResourceName },
            characterId
        );
    }

    private List<CharacterGroupHealSpellRecord> CreateCharacterGroupHealSpellRecords(int characterId, List<string> spellResourceNames)
    {
        return CreateJunctionRecords(
            spellResourceNames,
            (cId, sResourceName) => new CharacterGroupHealSpellRecord { CharacterId = cId, SpellResourceName = sResourceName },
            characterId
        );
    }

    private List<CharacterCCSpellRecord> CreateCharacterCCSpellRecords(int characterId, List<string> spellResourceNames)
    {
        return CreateJunctionRecords(
            spellResourceNames,
            (cId, sResourceName) => new CharacterCCSpellRecord { CharacterId = cId, SpellResourceName = sResourceName },
            characterId
        );
    }

    private List<CharacterTauntSpellRecord> CreateCharacterTauntSpellRecords(int characterId, List<string> spellResourceNames)
    {
        return CreateJunctionRecords(
            spellResourceNames,
            (cId, sResourceName) => new CharacterTauntSpellRecord { CharacterId = cId, SpellResourceName = sResourceName },
            characterId
        );
    }

    /// <summary>
    /// Generic helper method to create junction table records with deduplication.
    /// Deduplicates by resource name and creates records.
    /// </summary>
    /// <param name="resourceNames">List of ability resource names (spell or skill ResourceNames from Unity assets)</param>
    /// <param name="recordFactory">Function to create a junction record given characterId and abilityResourceName</param>
    /// <param name="characterId">The character's database ID</param>
    /// <returns>List of junction records with duplicate ability references removed</returns>
    private List<T> CreateJunctionRecords<T>(
        List<string> resourceNames,
        System.Func<int, string, T> recordFactory,
        int characterId)
    {
        var records = new List<T>();
        var seenResourceNames = new HashSet<string>();

        foreach (var resourceName in resourceNames)
        {
            if (seenResourceNames.Add(resourceName))
            {
                records.Add(recordFactory(characterId, resourceName));
            }
        }

        return records;
    }

    /// <summary>
    /// Checks if a database table exists for the given record type.
    /// Converts record class name to table name (e.g., "SpellRecord" -> "Spells").
    /// </summary>
    private bool TableExists<T>() where T : new()
    {
        var tableName = typeof(T).Name.Replace("Record", "s");
        var result = _db.ExecuteScalar<int>("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", tableName);
        return result > 0;
    }

    private List<CharacterVendorItemRecord> CreateCharacterVendorItemRecords(int characterId, VendorInventory vendorInventory)
    {
        var records = new List<CharacterVendorItemRecord>();
        var seenItemNames = new HashSet<string>();

        if (vendorInventory.ItemsForSale != null && vendorInventory.ItemsForSale.Count > 0)
        {
            foreach (var item in vendorInventory.ItemsForSale)
            {
                if (item != null && !string.IsNullOrEmpty(item.ItemName) && seenItemNames.Add(item.ItemName))
                {
                    records.Add(new CharacterVendorItemRecord
                    {
                        CharacterId = characterId,
                        ItemName = item.ItemName
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterAggressiveFactionRecord> CreateCharacterAggressiveFactionRecords(int characterId, Character character)
    {
        var records = new List<CharacterAggressiveFactionRecord>();
        var seenFactions = new HashSet<string>();

        if (character.AggressiveTowards != null && character.AggressiveTowards.Count > 0)
        {
            foreach (var faction in character.AggressiveTowards)
            {
                var factionName = faction.ToString();
                if (!string.IsNullOrEmpty(factionName) && seenFactions.Add(factionName))
                {
                    records.Add(new CharacterAggressiveFactionRecord
                    {
                        CharacterId = characterId,
                        FactionName = factionName
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterAlliedFactionRecord> CreateCharacterAlliedFactionRecords(int characterId, Character character)
    {
        var records = new List<CharacterAlliedFactionRecord>();
        var seenFactions = new HashSet<string>();

        if (character.Allies != null && character.Allies.Count > 0)
        {
            foreach (var faction in character.Allies)
            {
                var factionName = faction.ToString();
                if (!string.IsNullOrEmpty(factionName) && seenFactions.Add(factionName))
                {
                    records.Add(new CharacterAlliedFactionRecord
                    {
                        CharacterId = characterId,
                        FactionName = factionName
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterFactionModifierRecord> CreateCharacterFactionModifierRecords(int characterId, ModifyFaction modifyFaction)
    {
        var records = new List<CharacterFactionModifierRecord>();
        var seenRefNames = new HashSet<string>();

        if (modifyFaction != null && modifyFaction.Factions != null && modifyFaction.Factions.Count > 0)
        {
            foreach (var faction in modifyFaction.Factions)
            {
                if (faction != null && !string.IsNullOrEmpty(faction.REFNAME) && seenRefNames.Add(faction.REFNAME))
                {
                    records.Add(new CharacterFactionModifierRecord
                    {
                        CharacterId = characterId,
                        FactionREFNAME = faction.REFNAME,
                        ModifierValue = (int)modifyFaction.Modifier
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterDeathShoutRecord> CreateCharacterDeathShoutRecords(int characterId, Character character)
    {
        var records = new List<CharacterDeathShoutRecord>();

        if (character.ShoutOnDeath != null && character.ShoutOnDeath.Count > 0)
        {
            for (int i = 0; i < character.ShoutOnDeath.Count; i++)
            {
                var shout = character.ShoutOnDeath[i];
                if (!string.IsNullOrEmpty(shout))
                {
                    records.Add(new CharacterDeathShoutRecord
                    {
                        CharacterId = characterId,
                        SequenceIndex = i,
                        ShoutText = shout
                    });
                }
            }
        }

        return records;
    }
}