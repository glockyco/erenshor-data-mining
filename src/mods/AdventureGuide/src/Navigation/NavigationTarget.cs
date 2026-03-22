using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// What we're navigating to. Position is mutable to allow in-place updates
/// when a live NPC moves, avoiding per-frame heap allocation.
/// </summary>
public sealed class NavigationTarget
{
    public enum Kind { Character, ZoneLine, Position }

    /// <summary>What kind of thing we're navigating to.</summary>
    public Kind TargetKind { get; }

    /// <summary>World-space position of the target. Mutable for live tracking.</summary>
    public Vector3 Position { get; set; }

    /// <summary>Display name shown to the player (NPC name, zone name, etc.).</summary>
    public string DisplayName { get; }

    /// <summary>Scene this target is in.</summary>
    public string Scene { get; }

    /// <summary>Stable key for entity lookup (character:name format).</summary>
    public string? TargetKey { get; }

    /// <summary>Quest DB name this navigation originated from.</summary>
    public string QuestDBName { get; }

    /// <summary>Step order this navigation originated from.</summary>
    public int StepOrder { get; }

    public NavigationTarget(
        Kind targetKind,
        Vector3 position,
        string displayName,
        string scene,
        string questDBName,
        int stepOrder,
        string? targetKey = null)
    {
        TargetKind = targetKind;
        Position = position;
        DisplayName = displayName;
        Scene = scene;
        QuestDBName = questDBName;
        StepOrder = stepOrder;
        TargetKey = targetKey;
    }

    /// <summary>True when the target is in a different scene than the player.</summary>
    public bool IsCrossZone(string currentScene) =>
        !string.Equals(Scene, currentScene, System.StringComparison.OrdinalIgnoreCase);
}
