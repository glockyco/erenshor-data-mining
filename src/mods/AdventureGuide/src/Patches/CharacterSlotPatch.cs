using AdventureGuide.Config;
using HarmonyLib;

namespace AdventureGuide.Patches;

[HarmonyPatch(typeof(CharSelectManager), nameof(CharSelectManager.SaveChar))]
internal static class CharacterCreatePatch
{
    internal static GuideConfig? Config;

    [HarmonyPrefix]
    private static void Prefix(out int? __state)
    {
        var slot = GameData.CurrentCharacterSlot;
        __state = slot != null && string.IsNullOrEmpty(slot.CharName) ? slot.index : null;
    }

    [HarmonyPostfix]
    private static void Postfix(int? __state)
    {
        var slot = GameData.CurrentCharacterSlot;
        // SaveChar returns early on invalid names or a missing class. Only reset
        // when an empty slot actually received a newly created character.
        if (
            __state.HasValue
            && slot != null
            && slot.index == __state.Value
            && !string.IsNullOrEmpty(slot.CharName)
        )
            Config?.ResetCharacterSlot(__state.Value);
    }
}

[HarmonyPatch(typeof(CharSelectManager), nameof(CharSelectManager.EraseCharacter))]
internal static class CharacterDeletePatch
{
    internal static GuideConfig? Config;

    // A prefix that throws stops the game's method, so never assume a selection.
    [HarmonyPrefix]
    private static void Prefix(out int __state) =>
        __state = GameData.CurrentCharacterSlot != null ? GameData.CurrentCharacterSlot.index : -1;

    [HarmonyPostfix]
    private static void Postfix(int __state)
    {
        if (__state >= 0)
            Config?.ResetCharacterSlot(__state);
    }
}
