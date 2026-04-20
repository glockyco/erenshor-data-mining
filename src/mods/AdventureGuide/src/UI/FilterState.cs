using AdventureGuide.Config;

namespace AdventureGuide.UI;

/// <summary>
/// Mutable state bag for the guide window's filter/search/tab controls.
/// One instance lives for the lifetime of the window. Version increments
/// on any change, enabling consumers to skip re-computation.
///
/// FilterMode, SortMode, and ZoneFilter are persisted to BepInEx config
/// so they survive mod reloads and game restarts.
/// </summary>
public class FilterState
{
    private readonly GuideConfig _config;

    /// <summary>
    /// Monotonically increasing version. Consumers compare against a snapshot
    /// to detect whether filter state has changed since their last computation.
    /// </summary>
    public int Version { get; private set; }

    private QuestFilterMode _filterMode;
    private string _searchText = string.Empty;
    private string? _zoneFilter;
    private QuestSortMode _sortMode;

    /// <summary>
    /// Construct with a bound config. Loads persisted filter, sort, and zone
    /// filter settings immediately so the window opens with the player's saved
    /// preferences rather than the struct defaults.
    /// </summary>
    public FilterState(GuideConfig config)
    {
        _config = config;
        _filterMode = config.FilterMode.Value;
        _sortMode = config.SortMode.Value;
        var zone = config.ZoneFilter.Value;
        _zoneFilter = string.IsNullOrEmpty(zone) ? null : zone;
    }

    public QuestFilterMode FilterMode
    {
        get => _filterMode;
        set
        {
            if (_filterMode != value)
            {
                _filterMode = value;
                Version++;
                _config.FilterMode.SetSerializedValue(value.ToString());
            }
        }
    }

    public string SearchText
    {
        get => _searchText;
        set
        {
            if (_searchText != value)
            {
                _searchText = value;
                Version++;
            }
        }
    }

    /// <summary>Null means "all zones" (no filter).</summary>
    public string? ZoneFilter
    {
        get => _zoneFilter;
        set
        {
            if (_zoneFilter != value)
            {
                _zoneFilter = value;
                Version++;
                _config.ZoneFilter.SetSerializedValue(value ?? "");
            }
        }
    }

    public QuestSortMode SortMode
    {
        get => _sortMode;
        set
        {
            if (_sortMode != value)
            {
                _sortMode = value;
                Version++;
                _config.SortMode.SetSerializedValue(value.ToString());
            }
        }
    }
}
