namespace AdventureGuide.UI;

public enum QuestFilterMode
{
    Active,
    Available,
    Completed,
    All,
}

public enum QuestSortMode
{
    Alphabetical,
    ByZone,
    ByLevel,
}

/// <summary>
/// Mutable state bag for the guide window's filter/search/tab controls.
/// One instance lives for the lifetime of the window.
/// </summary>
public class FilterState
{
    /// <summary>0 = Quests, 1 = Progress.</summary>
    public int SelectedTab;

    public QuestFilterMode FilterMode = QuestFilterMode.Active;

    public string SearchText = string.Empty;

    /// <summary>Null means "all zones" (no filter).</summary>
    public string? ZoneFilter;

    public QuestSortMode SortMode = QuestSortMode.Alphabetical;

    public bool ShowSettings;
}
