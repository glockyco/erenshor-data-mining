using AdventureGuide.Navigation;
using HarmonyLib;
using UnityEngine;

namespace AdventureGuide.Patches;

/// <summary>Keeps native indicators in sync with AG's runtime suppression.</summary>
[HarmonyPatch(typeof(NPC), nameof(NPC.SpawnQuestMarker))]
internal static class QuestMarkerPatch
{
    private static readonly System.Reflection.FieldInfo MarkerField = AccessTools.Field(
        typeof(NPC),
        "QuestMarker"
    );
    private static readonly System.Reflection.FieldInfo MarkerUpField = AccessTools.Field(
        typeof(NPC),
        "MarkerUp"
    );

    internal static bool SuppressGameMarkers;

    internal static void SetSuppression(bool suppressed)
    {
        if (SuppressGameMarkers == suppressed)
            return;
        SuppressGameMarkers = suppressed;
        foreach (var npc in UnityEngine.Object.FindObjectsOfType<NPC>())
        {
            var marker = MarkerField.GetValue(npc) as GameObject;
            var character = npc.GetChar();
            var action = GameMarkerPolicy.Decide(
                suppressed,
                GameData.UseMarkers,
                npc.SimPlayer || npc.GetComponent<SimPlayer>() != null,
                character != null && character.Alive,
                IsEligible(npc),
                marker != null
            );
            switch (action)
            {
                case GameMarkerAction.Hide:
                    marker!.SetActive(false);
                    break;
                case GameMarkerAction.Restore:
                    marker!.SetActive(true);
                    MarkerUpField.SetValue(npc, true);
                    break;
                case GameMarkerAction.Spawn:
                    npc.SpawnQuestMarker();
                    break;
            }
        }
    }

    private static bool IsEligible(NPC npc)
    {
        var quests = npc.GetComponent<QuestManager>();
        if (quests != null && quests.NPCQuests != null)
            foreach (var quest in quests.NPCQuests)
                if (IsAvailable(quest))
                    return true;
        if (npc.GetComponent<NPCDialogManager>() != null)
            foreach (var dialog in npc.GetComponents<NPCDialog>())
                if (IsAvailable(dialog.QuestToAssign))
                    return true;
        return false;
    }

    private static bool IsAvailable(Quest quest) =>
        quest != null
        && GameMarkerPolicy.IsQuestAvailable(
            GameData.HasQuest.Contains(quest.DBName),
            GameData.CompletedQuests.Contains(quest.DBName)
        );

    [HarmonyPrefix]
    private static bool Prefix(NPC __instance)
    {
        if (
            SuppressGameMarkers
            || !GameData.UseMarkers
            || __instance.SimPlayer
            || __instance.GetComponent<SimPlayer>() != null
        )
            return false;
        var marker = MarkerField.GetValue(__instance) as GameObject;
        if (marker == null)
            return true;
        // The game retains inactive indicators after accepting a quest.
        // Reuse that object even when its MarkerUp flag has been cleared.
        marker.SetActive(true);
        MarkerUpField.SetValue(__instance, true);
        return false;
    }
}
