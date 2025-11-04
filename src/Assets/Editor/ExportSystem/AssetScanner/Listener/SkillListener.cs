#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEditor;
using UnityEngine;

public class SkillListener : IAssetScanListener<Skill>
{
    private readonly SQLiteConnection _db;
    private readonly List<SkillRecord> _records = new();

    public SkillListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<SkillRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SkillRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(Skill asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset, _records.Count));
    }
    
    private SkillRecord CreateRecord(Skill skill, int skillDbIndex)
    {
        string? skillIconName = null;
        if (skill.SkillIcon != null)
        {
            var path = AssetDatabase.GetAssetPath(skill.SkillIcon);
            skillIconName = System.IO.Path.GetFileNameWithoutExtension(path);
        }
        
        return new SkillRecord
        {
            // --- Core Identification ---
            SkillDBIndex = skillDbIndex,
            Id = skill.Id,
            SkillName = skill.SkillName,
            SkillDesc = skill.SkillDesc,
            TypeOfSkill = skill.TypeOfSkill.ToString(),

            // --- Requirements ---
            DuelistRequiredLevel = skill.DuelistRequiredLevel,
            PaladinRequiredLevel = skill.PaladinRequiredLevel,
            ArcanistRequiredLevel = skill.ArcanistRequiredLevel,
            DruidRequiredLevel = skill.DruidRequiredLevel,
            StormcallerRequiredLevel = skill.StormcallerRequiredLevel,
            RequireBehind = skill.RequireBehind,
            Require2H = skill.Require2H,
            RequireDW = skill.RequireDW,
            RequireBow = skill.RequireBow,
            RequireShield = skill.RequireShield,

            // --- Simulation ---
            SimPlayersAutolearn = skill.SimPlayersAutolearn,

            // --- Timing & Cost ---
            Cooldown = skill.Cooldown,

            // --- Effects & Mechanics ---
            AESkill = skill.AESkill,
            Interrupt = skill.Interrupt,
            SpawnOnUseResourceName = skill.SpawnOnUse != null ? skill.SpawnOnUse.name : null,
            EffectToApplyId = skill.EffectToApply != null ? skill.EffectToApply.Id : null,
            AffectPlayer = skill.AffectPlayer,
            AffectTarget = skill.AffectTarget,
            SkillRange = skill.SkillRange,
            SkillPower = skill.SkillPower,
            PercentDmg = skill.PercentDmg,
            DamageType = skill.DmgType.ToString(),
            ScaleOffWeapon = skill.ScaleOffWeapon,
            ProcWeap = skill.ProcWeap,
            ProcShield = skill.ProcShield,
            GuaranteeProc = skill.GuaranteeProc,
            AutomateAttack = skill.AutomateAttack,
            CastOnTargetId = skill.CastOnTarget?.name ?? string.Empty,

            // --- Visual/Audio ---
            SkillAnimName = skill.SkillAnimName,
            SkillIconName = skillIconName,

            // --- Text ---
            PlayerUses = skill.PlayerUses,
            NPCUses = skill.NPCUses,

            // --- Internals ---
            ResourceName = skill.name,
        };
    }
}