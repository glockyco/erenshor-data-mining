using AdventureGuide.Navigation;

namespace AdventureGuide.Markers;

/// <summary>
/// Data for a single world marker. Produced by <see cref="MarkerComputer"/>,
/// consumed by the marker rendering system to place billboards in the world.
/// Uses <see cref="MarkerType"/> from the existing MarkerPool for visual styling.
/// </summary>
public sealed class MarkerEntry
{
    // Position
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
    public string Scene { get; set; } = "";

    // Display
    public MarkerType Type { get; set; }
    public string DisplayName { get; set; } = "";
    public string SubText { get; set; } = "";

    // Graph context
    public string NodeKey { get; set; } = "";
    public string QuestKey { get; set; } = "";
}
