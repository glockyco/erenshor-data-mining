using System.Runtime.CompilerServices;

namespace AdventureGuide.Navigation;

/// <summary>
/// What each NPC's GameObject was named before NPC.Start renamed it to
/// NPCName (NPC.cs:467). Unity names a clone "{prefab}(Clone)", and the export
/// derives character stable keys from prefab names and, for characters placed
/// in a scene, from the scene object name. NpcStartPatch records the name
/// first. Entries are weak, so destroyed NPCs drop out once Unity releases
/// them.
/// </summary>
internal static class NpcOrigins
{
    private const string CloneSuffix = "(Clone)";

    private static readonly ConditionalWeakTable<NPC, string> PrefabNames = new();
    private static readonly ConditionalWeakTable<NPC, string> PlacedNames = new();

    /// <summary>Record an NPC's object name while it still has it.</summary>
    internal static void Record(NPC npc)
    {
        var objectName = npc.gameObject.name;
        var prefabName = PrefabNameOf(objectName);
        if (prefabName != null)
            PrefabNames.AddOrUpdate(npc, prefabName);
        else
            PlacedNames.AddOrUpdate(npc, objectName);
    }

    /// <summary>
    /// The prefab an instantiated NPC was cloned from, or null for NPCs placed
    /// in the scene and for NPCs that started before the patch was installed.
    /// </summary>
    internal static string? PrefabName(NPC npc) =>
        PrefabNames.TryGetValue(npc, out var prefabName)
            ? prefabName
            : PrefabNameOf(npc.gameObject.name);

    /// <summary>
    /// The scene object name of an NPC placed in the scene, or null for clones
    /// and for NPCs that started before the patch was installed.
    /// </summary>
    internal static string? PlacedName(NPC npc) =>
        PlacedNames.TryGetValue(npc, out var placedName) ? placedName : null;

    /// <summary>The prefab name in a clone's object name, or null for other names.</summary>
    internal static string? PrefabNameOf(string objectName) =>
        objectName.EndsWith(CloneSuffix, System.StringComparison.Ordinal)
            ? objectName.Substring(0, objectName.Length - CloneSuffix.Length)
            : null;
}
