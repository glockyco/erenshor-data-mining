using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Suppresses the game's built-in quest indicator markers when the
/// AdventureGuide world marker system is active. The game instantiates
/// QuestIndicator prefabs above NPCs in NPC.SpawnQuestMarker(). This
/// prefix skips that method entirely when our markers are enabled,
/// preventing double markers.
/// </summary>
[HarmonyPatch(typeof(NPC), nameof(NPC.SpawnQuestMarker))]
internal static class QuestMarkerPatch
{
    /// <summary>
    /// When true, the game's SpawnQuestMarker is skipped. Set by
    /// WorldMarkerSystem when world markers are enabled.
    /// </summary>
    internal static bool SuppressGameMarkers;

    [HarmonyPrefix]
    private static bool Prefix() => !SuppressGameMarkers;
}
