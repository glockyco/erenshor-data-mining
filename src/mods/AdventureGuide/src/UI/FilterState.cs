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
/// One instance lives for the lifetime of the window. Version increments
/// on any change, enabling consumers to skip re-computation.
/// </summary>
public class FilterState
{
    /// <summary>0 = Quests, 1 = Progress.</summary>
    public int SelectedTab;

    /// <summary>
    /// Monotonically increasing version. Consumers compare against a snapshot
    /// to detect whether filter state has changed since their last computation.
    /// </summary>
    public int Version { get; private set; }

    private QuestFilterMode _filterMode = QuestFilterMode.Active;
    private string _searchText = string.Empty;
    private string? _zoneFilter;
    private QuestSortMode _sortMode = QuestSortMode.Alphabetical;

    public QuestFilterMode FilterMode
    {
        get => _filterMode;
        set { if (_filterMode != value) { _filterMode = value; Version++; } }
    }

    public string SearchText
    {
        get => _searchText;
        set { if (_searchText != value) { _searchText = value; Version++; } }
    }

    /// <summary>Null means "all zones" (no filter).</summary>
    public string? ZoneFilter
    {
        get => _zoneFilter;
        set { if (_zoneFilter != value) { _zoneFilter = value; Version++; } }
    }

    public QuestSortMode SortMode
    {
        get => _sortMode;
        set { if (_sortMode != value) { _sortMode = value; Version++; } }
    }

    public bool ShowSettings;
}
