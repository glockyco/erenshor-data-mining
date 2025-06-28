#nullable enable

using System.Collections.Generic;
using SQLite;
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
            RequireBehind = skill.RequireBehind,
            Require2H = skill.Require2H,
            RequireDW = skill.RequireDW,
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

            // --- Visual/Audio ---
            SkillAnimName = skill.SkillAnimName,
            SkillIconName = skill.SkillIcon != null ? skill.SkillIcon.name : null,

            // --- Text ---
            PlayerUses = skill.PlayerUses,
            NPCUses = skill.NPCUses,

            // --- Internals ---
            ResourceName = skill.name,
        };
    }
}