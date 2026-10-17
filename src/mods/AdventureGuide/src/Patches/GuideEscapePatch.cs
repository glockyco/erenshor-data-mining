using HarmonyLib;
using UnityEngine;

namespace AdventureGuide.Patches;

[HarmonyPatch(typeof(GameManager), "Update")]
internal static class GuideEscapePatch
{
    internal static Func<bool>? ConsumeEscape;

    // Keep the rest of GameManager.Update running, including non-Escape input.
    [HarmonyTranspiler]
    private static IEnumerable<CodeInstruction> Transpiler(
        IEnumerable<CodeInstruction> instructions
    )
    {
        var getKeyDown = AccessTools.Method(
            typeof(Input),
            nameof(Input.GetKeyDown),
            new[] { typeof(KeyCode) }
        );
        var replacement = AccessTools.Method(typeof(GuideEscapePatch), nameof(EscapePressed));
        CodeInstruction? previous = null;
        int replaced = 0;
        foreach (var instruction in instructions)
        {
            if (
                previous != null
                && previous.LoadsConstant((int)KeyCode.Escape)
                && instruction.Calls(getKeyDown)
            )
            {
                instruction.operand = replacement;
                replaced++;
            }
            yield return instruction;
            previous = instruction;
        }
        if (replaced != 1)
            throw new InvalidOperationException(
                $"Expected one GameManager Escape input check, found {replaced}."
            );
    }

    private static bool EscapePressed(KeyCode key) =>
        ConsumeEscape?.Invoke() != true && Input.GetKeyDown(key);
}
