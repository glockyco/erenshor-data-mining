using System.Runtime.CompilerServices;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// What each NPC's GameObject was named before NPC.Start renamed it to
/// NPCName (NPC.cs:467), and where a scene-placed NPC stood then. Unity names a
/// clone "{prefab}(Clone)", and the export derives character stable keys from
/// prefab names and, for characters placed in a scene, from the scene object
/// name and position. NpcStartPatch records both first. Entries are weak, so
/// destroyed NPCs drop out once Unity releases them.
/// </summary>
internal static class NpcOrigins
{
    private const string CloneSuffix = "(Clone)";

    private sealed class Placement
    {
        internal readonly string ObjectName;
        internal readonly Vector3 Position;

        internal Placement(string objectName, Vector3 position)
        {
            ObjectName = objectName;
            Position = position;
        }
    }

    private static readonly ConditionalWeakTable<NPC, string> PrefabNames = new();
    private static readonly ConditionalWeakTable<NPC, Placement> Placements = new();

    /// <summary>Record an NPC's object name, and a placed NPC's position, while it still has them.</summary>
    internal static void Record(NPC npc)
    {
        var objectName = npc.gameObject.name;
        var prefabName = PrefabNameOf(objectName);
        if (prefabName != null)
            PrefabNames.AddOrUpdate(npc, prefabName);
        else
            Placements.AddOrUpdate(npc, new Placement(objectName, npc.transform.position));
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
        Placements.TryGetValue(npc, out var placement) ? placement.ObjectName : null;

    /// <summary>The scene object name and starting position of an NPC placed in the scene.</summary>
    internal static bool TryGetPlacement(NPC npc, out string objectName, out Vector3 position)
    {
        if (Placements.TryGetValue(npc, out var placement))
        {
            objectName = placement.ObjectName;
            position = placement.Position;
            return true;
        }
        objectName = "";
        position = default;
        return false;
    }

    /// <summary>The prefab name in a clone's object name, or null for other names.</summary>
    internal static string? PrefabNameOf(string objectName) =>
        objectName.EndsWith(CloneSuffix, System.StringComparison.Ordinal)
            ? objectName.Substring(0, objectName.Length - CloneSuffix.Length)
            : null;
}
