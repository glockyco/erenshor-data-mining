using System.Runtime.CompilerServices;

namespace AdventureGuide.Navigation;

/// <summary>
/// The prefab each runtime-instantiated NPC was cloned from. Unity names a
/// clone "{prefab}(Clone)", and the export derives character stable keys from
/// prefab names, but NPC.Start renames the GameObject to NPCName (NPC.cs:467).
/// NpcStartPatch records the clone name before that rename. Entries are weak,
/// so destroyed NPCs drop out once Unity releases them.
/// </summary>
internal static class NpcOrigins
{
    private const string CloneSuffix = "(Clone)";

    private static readonly ConditionalWeakTable<NPC, string> PrefabNames = new();

    /// <summary>Record the prefab of an NPC whose GameObject still has its clone name.</summary>
    internal static void Record(NPC npc)
    {
        var prefabName = PrefabNameOf(npc.gameObject.name);
        if (prefabName != null)
            PrefabNames.AddOrUpdate(npc, prefabName);
    }

    /// <summary>
    /// The prefab an instantiated NPC was cloned from, or null for NPCs placed
    /// in the scene and for NPCs that started before the patch was installed.
    /// </summary>
    internal static string? PrefabName(NPC npc) =>
        PrefabNames.TryGetValue(npc, out var prefabName)
            ? prefabName
            : PrefabNameOf(npc.gameObject.name);

    /// <summary>The prefab name in a clone's object name, or null for other names.</summary>
    internal static string? PrefabNameOf(string objectName) =>
        objectName.EndsWith(CloneSuffix, System.StringComparison.Ordinal)
            ? objectName.Substring(0, objectName.Length - CloneSuffix.Length)
            : null;
}
