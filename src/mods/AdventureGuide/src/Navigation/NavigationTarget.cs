using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// What we're navigating to. Position is mutable to allow in-place updates
/// when a live NPC moves, avoiding per-frame heap allocation.
/// </summary>
public sealed class NavigationTarget
{
    public enum Kind { Character, ZoneLine, Zone, Position }

    /// <summary>What kind of thing we're navigating to.</summary>
    public Kind TargetKind { get; }

    /// <summary>World-space position of the target. Mutable for live tracking.</summary>
    public Vector3 Position { get; set; }

    /// <summary>Display name shown to the player (NPC name, zone name, etc.). Mutable for multi-source switching.</summary>
    public string DisplayName { get; set; }

    /// <summary>Scene this target is in.</summary>
    public string Scene { get; set; }

    /// <summary>
    /// Identifies which source is currently being navigated to. Mutable
    /// so multi-source resolution can update it when the closest source changes.
    /// Matches ItemSource.SourceKey for entity sources (e.g. "character:stoneman"),
    /// or a synthetic key for zone-only sources (e.g. "fishing:Stowaway").
    /// Used by the UI to highlight the specific source being navigated to.
    /// </summary>
    public string? SourceId { get; set; }

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
        string? sourceId = null)
    {
        TargetKind = targetKind;
        Position = position;
        DisplayName = displayName;
        Scene = scene;
        QuestDBName = questDBName;
        StepOrder = stepOrder;
        SourceId = sourceId;
    }

    /// <summary>True when the target is in a different scene than the player.</summary>
    public bool IsCrossZone(string currentScene) =>
        !string.Equals(Scene, currentScene, System.StringComparison.OrdinalIgnoreCase);
}
