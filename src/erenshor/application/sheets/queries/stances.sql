SELECT
    StableKey,
    DisplayName,
    StanceDesc,
    MaxHPMod,
    DamageMod,
    SpellDamageMod,
    DamageTakenMod,
    ProcRateMod,
    AggroGenMod,
    LifestealAmount,
    ResonanceAmount,
    SelfDamagePerAttack,
    SelfDamagePerCast,
    StopRegen,
    SwitchMessage,
    ResourceName
FROM Stances
ORDER BY DisplayName;
