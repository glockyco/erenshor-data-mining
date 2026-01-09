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
    private readonly Dictionary<string, int> _stableKeyCounters = new(); // Track occurrence count for each base stable key
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
    private readonly List<CharacterVendorQuestUnlockRecord> _characterVendorQuestUnlockRecords = new();

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

        // All junction records have been created during ProcessCharacter() while Unity assets were available

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
        _db.CreateTable<CharacterVendorQuestUnlockRecord>();

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
            _db.DeleteAll<CharacterVendorQuestUnlockRecord>();

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
            _db.InsertAll(_characterVendorQuestUnlockRecords);
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
        _characterVendorQuestUnlockRecords.Clear();

        _db.Execute(@"
            UPDATE Characters
            SET IsCommon = 1
            WHERE Guid IN
            (
                SELECT DISTINCT c.Guid
                FROM Characters c
                LEFT JOIN SpawnPointCharacters spc ON spc.CharacterStableKey = c.StableKey
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
                JOIN SpawnPointCharacters spc ON spc.CharacterStableKey = c.StableKey
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
                    LEFT JOIN SpawnPointCharacters spc ON spc.CharacterStableKey = c.StableKey
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

        // Generate base stable key and check for duplicates
        var baseStableKey = StableKeyGenerator.ForCharacter(asset);
        int variantIndex = 0;

        if (_stableKeyCounters.ContainsKey(baseStableKey))
        {
            _stableKeyCounters[baseStableKey]++;
            variantIndex = _stableKeyCounters[baseStableKey];
            UnityEngine.Debug.LogWarning($"[CharacterListener] Duplicate character StableKey: '{baseStableKey}'. GameObject: '{asset.gameObject.name}'. Assigning variant index |{variantIndex}.");
        }
        else
        {
            _stableKeyCounters[baseStableKey] = 0;
        }

        var characterRecord = CreateCharacterRecord(asset, coordinateRecord, variantIndex);
        _characterRecords.Add(characterRecord);

        if (coordinateRecord != null)
        {
            coordinateRecord.CharacterStableKey = characterRecord.StableKey;
            _coordinateRecords.Add(coordinateRecord);
        }

        var dialogs = asset.GetComponents<NPCDialog>().Where(d => !string.IsNullOrWhiteSpace(d.Dialog)).ToList();
        if (dialogs.Count > 0)
        {
            var i = 0;
            var dialogRecords = new List<CharacterDialogRecord>();
            foreach (var dialog in dialogs)
            {
                dialogRecords.Add(CreateDialogRecord(characterRecord.StableKey, i, dialog));
                i++;
            }
            _characterDialogRecords.AddRange(dialogRecords);
        }

        var npc = asset.GetComponent<NPC>();
        if (npc != null)
        {
            // Create ability junction records NOW (while Unity assets are loaded)
            _characterAttackSkillRecords.AddRange(CreateCharacterAttackSkillRecords(characterRecord.StableKey, npc.MyAttackSkills ?? new List<Skill>()));
            _characterAttackSpellRecords.AddRange(CreateCharacterAttackSpellRecords(characterRecord.StableKey, npc.MyAttackSpells ?? new List<Spell>()));
            _characterBuffSpellRecords.AddRange(CreateCharacterBuffSpellRecords(characterRecord.StableKey, npc.MyBuffSpells ?? new List<Spell>()));
            _characterHealSpellRecords.AddRange(CreateCharacterHealSpellRecords(characterRecord.StableKey, npc.MyHealSpells ?? new List<Spell>()));
            _characterGroupHealSpellRecords.AddRange(CreateCharacterGroupHealSpellRecords(characterRecord.StableKey, npc.GroupHeals ?? new List<Spell>()));
            _characterCCSpellRecords.AddRange(CreateCharacterCCSpellRecords(characterRecord.StableKey, npc.MyCCSpells ?? new List<Spell>()));
            _characterTauntSpellRecords.AddRange(CreateCharacterTauntSpellRecords(characterRecord.StableKey, npc.MyTauntSpell ?? new List<Spell>()));
        }

        var vendorInventory = asset.GetComponent<VendorInventory>();
        if (vendorInventory != null)
        {
            _characterVendorItemRecords.AddRange(CreateCharacterVendorItemRecords(characterRecord.StableKey, vendorInventory));
            _characterVendorQuestUnlockRecords.AddRange(CreateCharacterVendorQuestUnlockRecords(characterRecord.StableKey, vendorInventory));
        }

        // Faction and Death Shout junction tables
        _characterAggressiveFactionRecords.AddRange(CreateCharacterAggressiveFactionRecords(characterRecord.StableKey, asset));
        _characterAlliedFactionRecords.AddRange(CreateCharacterAlliedFactionRecords(characterRecord.StableKey, asset));

        var modifyFactions = asset.GetComponents<ModifyFaction>();
        foreach (var modifyFaction in modifyFactions)
        {
            _characterFactionModifierRecords.AddRange(CreateCharacterFactionModifierRecords(characterRecord.StableKey, modifyFaction));
        }

        _characterDeathShoutRecords.AddRange(CreateCharacterDeathShoutRecords(characterRecord.StableKey, asset));
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
    
    private CharacterRecord CreateCharacterRecord(Character character, CoordinateRecord? coordinate, int variantIndex = 0)
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
            StableKey = StableKeyGenerator.ForCharacter(character, variantIndex),
            CoordinateId = coordinate?.Id,
            Guid = guid,
            ObjectName = character.gameObject != null ? character.gameObject.name : null,
            MyWorldFactionStableKey = character.MyWorldFaction != null ? StableKeyGenerator.ForFaction(character.MyWorldFaction) : null,
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
            // Spells and skills are stored in junction tables, not in denormalized fields
            record.PetSpellStableKey = npc.MyPetSpell != null
                ? StableKeyGenerator.ForSpell(npc.MyPetSpell)
                : null;
            record.ProcOnHitStableKey = npc.NPCProcOnHit != null
                ? StableKeyGenerator.ForSpell(npc.NPCProcOnHit)
                : null;
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
    
    private CharacterDialogRecord CreateDialogRecord(string characterStableKey, int dialogIndex, NPCDialog dialog)
    {
        var keywords = dialog.KeywordToActivate == null || dialog.KeywordToActivate.Count == 0 ? null : string.Join(", ", dialog.KeywordToActivate);
        var repeatingQuestDialog = dialog.RepeatingQuestDialog == "" ? null : dialog.RepeatingQuestDialog.Trim();

        return new CharacterDialogRecord
        {
            CharacterStableKey = characterStableKey,
            DialogIndex = dialogIndex,
            DialogText = dialog.Dialog.Trim(),
            Keywords = keywords,
            GiveItemStableKey = dialog.GiveItem != null ? StableKeyGenerator.ForItem(dialog.GiveItem) : null,
            AssignQuestStableKey = dialog.QuestToAssign != null ? StableKeyGenerator.ForQuest(dialog.QuestToAssign) : null,
            CompleteQuestStableKey = dialog.QuestToComplete != null ? StableKeyGenerator.ForQuest(dialog.QuestToComplete) : null,
            RepeatingQuestDialog = repeatingQuestDialog,
            KillSelfOnSay = dialog.KillMeOnSay,
            RequiredQuestStableKey = dialog.RequireQuestComplete != null ? StableKeyGenerator.ForQuest(dialog.RequireQuestComplete) : null,
            SpawnCharacterStableKey = dialog.Spawn != null ? StableKeyGenerator.ForCharacter(dialog.Spawn.GetComponent<Character>()) : null,
        };
    }

    private List<CharacterAttackSkillRecord> CreateCharacterAttackSkillRecords(string characterStableKey, List<Skill> skills)
    {
        var records = new List<CharacterAttackSkillRecord>();
        var seenSkillStableKeys = new HashSet<string>();

        foreach (var skill in skills)
        {
            if (skill != null && !string.IsNullOrEmpty(skill.name))
            {
                var skillStableKey = StableKeyGenerator.ForSkill(skill);
                if (seenSkillStableKeys.Add(skillStableKey))
                {
                    records.Add(new CharacterAttackSkillRecord
                    {
                        CharacterStableKey = characterStableKey,
                        SkillStableKey = skillStableKey
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterAttackSpellRecord> CreateCharacterAttackSpellRecords(string characterStableKey, List<Spell> spells)
    {
        var records = new List<CharacterAttackSpellRecord>();
        var seenSpellStableKeys = new HashSet<string>();

        foreach (var spell in spells)
        {
            if (spell != null && !string.IsNullOrEmpty(spell.name))
            {
                var spellStableKey = StableKeyGenerator.ForSpell(spell);
                if (seenSpellStableKeys.Add(spellStableKey))
                {
                    records.Add(new CharacterAttackSpellRecord
                    {
                        CharacterStableKey = characterStableKey,
                        SpellStableKey = spellStableKey
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterBuffSpellRecord> CreateCharacterBuffSpellRecords(string characterStableKey, List<Spell> spells)
    {
        var records = new List<CharacterBuffSpellRecord>();
        var seenSpellStableKeys = new HashSet<string>();

        foreach (var spell in spells)
        {
            if (spell != null && !string.IsNullOrEmpty(spell.name))
            {
                var spellStableKey = StableKeyGenerator.ForSpell(spell);
                if (seenSpellStableKeys.Add(spellStableKey))
                {
                    records.Add(new CharacterBuffSpellRecord
                    {
                        CharacterStableKey = characterStableKey,
                        SpellStableKey = spellStableKey
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterHealSpellRecord> CreateCharacterHealSpellRecords(string characterStableKey, List<Spell> spells)
    {
        var records = new List<CharacterHealSpellRecord>();
        var seenSpellStableKeys = new HashSet<string>();

        foreach (var spell in spells)
        {
            if (spell != null && !string.IsNullOrEmpty(spell.name))
            {
                var spellStableKey = StableKeyGenerator.ForSpell(spell);
                if (seenSpellStableKeys.Add(spellStableKey))
                {
                    records.Add(new CharacterHealSpellRecord
                    {
                        CharacterStableKey = characterStableKey,
                        SpellStableKey = spellStableKey
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterGroupHealSpellRecord> CreateCharacterGroupHealSpellRecords(string characterStableKey, List<Spell> spells)
    {
        var records = new List<CharacterGroupHealSpellRecord>();
        var seenSpellStableKeys = new HashSet<string>();

        foreach (var spell in spells)
        {
            if (spell != null && !string.IsNullOrEmpty(spell.name))
            {
                var spellStableKey = StableKeyGenerator.ForSpell(spell);
                if (seenSpellStableKeys.Add(spellStableKey))
                {
                    records.Add(new CharacterGroupHealSpellRecord
                    {
                        CharacterStableKey = characterStableKey,
                        SpellStableKey = spellStableKey
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterCCSpellRecord> CreateCharacterCCSpellRecords(string characterStableKey, List<Spell> spells)
    {
        var records = new List<CharacterCCSpellRecord>();
        var seenSpellStableKeys = new HashSet<string>();

        foreach (var spell in spells)
        {
            if (spell != null && !string.IsNullOrEmpty(spell.name))
            {
                var spellStableKey = StableKeyGenerator.ForSpell(spell);
                if (seenSpellStableKeys.Add(spellStableKey))
                {
                    records.Add(new CharacterCCSpellRecord
                    {
                        CharacterStableKey = characterStableKey,
                        SpellStableKey = spellStableKey
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterTauntSpellRecord> CreateCharacterTauntSpellRecords(string characterStableKey, List<Spell> spells)
    {
        var records = new List<CharacterTauntSpellRecord>();
        var seenSpellStableKeys = new HashSet<string>();

        foreach (var spell in spells)
        {
            if (spell != null && !string.IsNullOrEmpty(spell.name))
            {
                var spellStableKey = StableKeyGenerator.ForSpell(spell);
                if (seenSpellStableKeys.Add(spellStableKey))
                {
                    records.Add(new CharacterTauntSpellRecord
                    {
                        CharacterStableKey = characterStableKey,
                        SpellStableKey = spellStableKey
                    });
                }
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

    private List<CharacterVendorItemRecord> CreateCharacterVendorItemRecords(string characterStableKey, VendorInventory vendorInventory)
    {
        var records = new List<CharacterVendorItemRecord>();
        var seenItemStableKeys = new HashSet<string>();

        if (vendorInventory.ItemsForSale != null && vendorInventory.ItemsForSale.Count > 0)
        {
            foreach (var item in vendorInventory.ItemsForSale)
            {
                if (item != null && !string.IsNullOrEmpty(item.name))
                {
                    var itemStableKey = StableKeyGenerator.ForItem(item);
                    if (seenItemStableKeys.Add(itemStableKey))
                    {
                        records.Add(new CharacterVendorItemRecord
                        {
                            CharacterStableKey = characterStableKey,
                            ItemStableKey = itemStableKey
                        });
                    }
                }
            }
        }

        return records;
    }

    private List<CharacterVendorQuestUnlockRecord> CreateCharacterVendorQuestUnlockRecords(string characterStableKey, VendorInventory vendorInventory)
    {
        var records = new List<CharacterVendorQuestUnlockRecord>();
        var seenQuestStableKeys = new HashSet<string>();

        if (vendorInventory.QuestRewardsForSale != null && vendorInventory.QuestRewardsForSale.Count > 0)
        {
            foreach (var quest in vendorInventory.QuestRewardsForSale)
            {
                if (quest != null && !string.IsNullOrEmpty(quest.DBName))
                {
                    var questStableKey = StableKeyGenerator.ForQuest(quest);
                    if (seenQuestStableKeys.Add(questStableKey))
                    {
                        records.Add(new CharacterVendorQuestUnlockRecord
                        {
                            CharacterStableKey = characterStableKey,
                            QuestStableKey = questStableKey
                        });
                    }
                }
            }
        }

        return records;
    }

    private List<CharacterAggressiveFactionRecord> CreateCharacterAggressiveFactionRecords(string characterStableKey, Character character)
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
                        CharacterStableKey = characterStableKey,
                        FactionName = factionName
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterAlliedFactionRecord> CreateCharacterAlliedFactionRecords(string characterStableKey, Character character)
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
                        CharacterStableKey = characterStableKey,
                        FactionName = factionName
                    });
                }
            }
        }

        return records;
    }

    private List<CharacterFactionModifierRecord> CreateCharacterFactionModifierRecords(string characterStableKey, ModifyFaction modifyFaction)
    {
        var records = new List<CharacterFactionModifierRecord>();
        var seenFactionStableKeys = new HashSet<string>();

        if (modifyFaction != null && modifyFaction.Factions != null && modifyFaction.Factions.Count > 0)
        {
            foreach (var faction in modifyFaction.Factions)
            {
                if (faction != null && !string.IsNullOrEmpty(faction.REFNAME))
                {
                    var factionStableKey = StableKeyGenerator.ForFaction(faction);
                    if (seenFactionStableKeys.Add(factionStableKey))
                    {
                        records.Add(new CharacterFactionModifierRecord
                        {
                            CharacterStableKey = characterStableKey,
                            FactionStableKey = factionStableKey,
                            ModifierValue = (int)modifyFaction.Modifier
                        });
                    }
                }
            }
        }

        return records;
    }

    private List<CharacterDeathShoutRecord> CreateCharacterDeathShoutRecords(string characterStableKey, Character character)
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
                        CharacterStableKey = characterStableKey,
                        SequenceIndex = i,
                        ShoutText = shout
                    });
                }
            }
        }

        return records;
    }
}