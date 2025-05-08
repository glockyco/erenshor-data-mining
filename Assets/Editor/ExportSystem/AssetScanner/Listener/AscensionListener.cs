using System.Collections.Generic;
using UnityEngine;

public class AscensionListener : IAssetScanListener<Ascension>
{
    public readonly List<AscensionDBRecord> Records = new();

    public void OnAssetFound(Ascension asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset?.name} ({asset?.GetType().Name})");
        if (asset == null) return;
        var record = new AscensionDBRecord
        {
            AscensionDBIndex = Records.Count,
            Id = asset.Id,

            UsedBy = asset.UsedBy.ToString(),
            SkillName = asset.SkillName,
            SkillDesc = asset.SkillDesc,
            MaxRank = asset.MaxRank,
            SimPlayerWeight = asset.SimPlayerWeight,

            // General
            IncreaseHP = asset.IncreaseHP,
            IncreaseDEF = asset.IncreaseDEF,
            IncreaseMana = asset.IncreaseMana,
            MR = asset.MR,
            PR = asset.PR,
            ER = asset.ER,
            VR = asset.VR,
            IncreaseDodge = asset.IncreaseDodge,

            // Duelist
            IncreaseCombatRoll = asset.IncreaseCombatRoll,
            DecreaseAggroGen = asset.DecreaseAggroGen,
            ChanceForExtraAttack = asset.ChanceForExtraAttack,
            ChanceForDoubleBackstab = asset.ChanceForDoubleBackstab,
            ChanceToCritBackstab = asset.ChanceToCritBackstab,

            // Arcanist
            ResistModIncrease = asset.ResistModIncrease,
            DecreaseSpellAggroGen = asset.DecreaseSpellAggroGen,
            TripleResonateChance = asset.TripleResonateChance,
            CooldownReduction = asset.CooldownReduction,
            IntelligenceScaling = asset.IntelligenceScaling,

            // Paladin
            TripleAttackChance = asset.TripleAttackChance,
            AggroGenIncrease = asset.AggroGenIncrease,
            MitigationIncrease = asset.MitigationIncrease,
            AdvancedIncreaseHP = asset.AdvancedIncreaseHP,
            AdvancedResists = asset.AdvancedResists,

            // Druid
            HealingIncrease = asset.HealingIncrease,
            CriticalDotChance = asset.CriticalDotChance,
            CriticalHealingChance = asset.CriticalHealingChance,
            VengefulHealingPercentage = asset.VengefulHealingPercentage,
            SummonedBeastEnhancement = asset.SummonedBeastEnhancement,

            ResourceName = asset.name
        };
        Records.Add(record);
    }

    public void Reset() => Records.Clear();
}