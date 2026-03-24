using AdventureGuide.Data;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders the left panel: filter dropdown, search bar, and scrollable quest list.
/// </summary>
public sealed class QuestListPanel
{
    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly FilterState _filter;

    private string _searchBuf = string.Empty;
    private readonly List<QuestEntry> _sorted = new();

    // Dirty-checking: skip re-filter/sort when nothing changed
    private int _lastFilterVersion = -1;

    private static readonly string[] FilterNames = { "Active", "Available", "Completed", "All" };
    private int _filterIndex;

    // Zone filter: index 0 = "All Zones", 1+ = sorted zone names
    private readonly string[] _zoneNames;
    private int _zoneIndex;

    public QuestListPanel(GuideData data, QuestStateTracker state, FilterState filter)
    {
        _data = data;
        _state = state;
        _filter = filter;

        // Build sorted zone list from quest data
        var zones = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var quest in data.All)
            if (quest.ZoneContext != null)
                zones.Add(quest.ZoneContext);
        _zoneNames = new string[zones.Count + 1];
        _zoneNames[0] = "All Zones";
        int idx = 1;
        foreach (var z in zones)
            _zoneNames[idx++] = z;
    }

    public void Draw(float width)
    {
        // Fixed header: filter + sort + zone + search (not scrollable)
        DrawFilterRow(width);
        DrawZoneFilter();
        DrawSearchBar();

        ImGui.Separator();

        // Scrollable quest list fills remaining height
        ImGui.BeginChild("##QuestScroll");
        int count = DrawQuestList();

        // Empty state
        if (count == 0)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            if (_data.Count == 0)
                ImGui.TextWrapped("No quest data loaded.");
            else if (!string.IsNullOrEmpty(_filter.SearchText))
                ImGui.TextWrapped("No quests match your search.");
            else
                ImGui.TextWrapped("No quests in this category.");
            ImGui.PopStyleColor();
        }

        ImGui.EndChild();
    }

    private void DrawFilterRow(float width)
    {
        _filterIndex = (int)_filter.FilterMode;

        // Filter combo takes ~55% of panel width, sort buttons fill the rest
        ImGui.SetNextItemWidth(width * 0.55f);
        if (ImGui.Combo("##Filter", ref _filterIndex, FilterNames, FilterNames.Length))
            _filter.FilterMode = (QuestFilterMode)_filterIndex;

        ImGui.SameLine();
        DrawSortButton("Az", QuestSortMode.Alphabetical, "Sort alphabetically");
        ImGui.SameLine(0, 2);
        DrawSortButton("Lv", QuestSortMode.ByLevel, "Sort by level");
        ImGui.SameLine(0, 2);
        DrawSortButton("Zn", QuestSortMode.ByZone, "Sort by zone");

        ImGui.Spacing();
    }

    private void DrawSortButton(string label, QuestSortMode mode, string tooltip)
    {
        bool active = _filter.SortMode == mode;
        if (active)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton(label + "##sort"))
            _filter.SortMode = mode;

        if (active)
            ImGui.PopStyleColor();

        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            ImGui.TextUnformatted(tooltip);
            ImGui.EndTooltip();
        }
    }

    private void DrawZoneFilter()
    {
        // Sync index from filter state
        _zoneIndex = 0;
        if (_filter.ZoneFilter != null)
            for (int i = 1; i < _zoneNames.Length; i++)
                if (string.Equals(_zoneNames[i], _filter.ZoneFilter, StringComparison.OrdinalIgnoreCase))
                {
                    _zoneIndex = i;
                    break;
                }

        ImGui.SetNextItemWidth(-1);
        if (ImGui.Combo("##Zone", ref _zoneIndex, _zoneNames, _zoneNames.Length))
            _filter.ZoneFilter = _zoneIndex == 0 ? null : _zoneNames[_zoneIndex];

        ImGui.Spacing();
    }

    private void DrawSearchBar()
    {
        if (_searchBuf != _filter.SearchText)
            _searchBuf = _filter.SearchText;

        ImGui.SetNextItemWidth(-1);

        if (ImGui.InputTextWithHint("##QuestSearch", "Search quests...", ref _searchBuf, 256))
            _filter.SearchText = _searchBuf;

        ImGui.Spacing();
    }

    /// <summary>Draw filtered, sorted quest list. Returns count of visible quests.</summary>
    private int DrawQuestList()
    {
        // Rebuild only when filter state or quest state changed
        bool filterChanged = _filter.Version != _lastFilterVersion;
        bool stateChanged = _state.IsDirty;
        if (filterChanged || stateChanged)
        {
            _lastFilterVersion = _filter.Version;
            _state.IsDirty = false;

            _sorted.Clear();
            var all = _data.All;
            for (int i = 0; i < all.Count; i++)
            {
                var quest = all[i];
                if (PassesFilter(quest) && PassesSearch(quest))
                    _sorted.Add(quest);
            }
            _sorted.Sort(CompareQuests);
        }

        foreach (var quest in _sorted)
            DrawQuestEntry(quest);

        return _sorted.Count;
    }

    private int CompareQuests(QuestEntry a, QuestEntry b)
    {
        return _filter.SortMode switch
        {
            QuestSortMode.ByLevel => CompareLevels(a, b),
            QuestSortMode.ByZone  => CompareZones(a, b),
            _                     => string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase),
        };
    }

    private static int CompareLevels(QuestEntry a, QuestEntry b)
    {
        int? la = a.LevelEstimate?.Recommended;
        int? lb = b.LevelEstimate?.Recommended;
        if (la == null && lb == null)
            return string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
        if (la == null) return 1;  // null sorts to end
        if (lb == null) return -1;
        int cmp = la.Value.CompareTo(lb.Value);
        return cmp != 0 ? cmp : string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
    }

    private static int CompareZones(QuestEntry a, QuestEntry b)
    {
        if (a.ZoneContext == null && b.ZoneContext == null)
            return string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
        if (a.ZoneContext == null) return 1;  // null sorts to end
        if (b.ZoneContext == null) return -1;
        int cmp = string.Compare(a.ZoneContext, b.ZoneContext, StringComparison.OrdinalIgnoreCase);
        return cmp != 0 ? cmp : string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
    }

    private bool PassesFilter(QuestEntry quest)
    {
        bool statusOk = _filter.FilterMode switch
        {
            QuestFilterMode.Active    => _state.IsActive(quest.DBName),
            QuestFilterMode.Available => !_state.IsActive(quest.DBName) && !_state.IsCompleted(quest.DBName),
            QuestFilterMode.Completed => _state.IsCompleted(quest.DBName),
            QuestFilterMode.All       => true,
            _ => true,
        };
        if (!statusOk) return false;

        // Zone filter
        if (_filter.ZoneFilter != null)
            return string.Equals(quest.ZoneContext, _filter.ZoneFilter, StringComparison.OrdinalIgnoreCase);

        return true;
    }

    /// <summary>
    /// Search matches against quest name, zone, NPC names, and item names.
    /// </summary>
    private bool PassesSearch(QuestEntry quest)
    {
        if (string.IsNullOrEmpty(_filter.SearchText))
            return true;

        var term = _filter.SearchText;

        if (quest.DisplayName.Contains(term, StringComparison.OrdinalIgnoreCase))
            return true;

        if (quest.ZoneContext != null &&
            quest.ZoneContext.Contains(term, StringComparison.OrdinalIgnoreCase))
            return true;

        if (quest.Acquisition != null)
        {
            foreach (var acq in quest.Acquisition)
            {
                if (acq.SourceName != null &&
                    acq.SourceName.Contains(term, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
        }

        if (quest.RequiredItems != null)
        {
            foreach (var item in quest.RequiredItems)
            {
                if (item.ItemName.Contains(term, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
        }

        if (quest.Steps != null)
        {
            foreach (var step in quest.Steps)
            {
                if (step.TargetName != null &&
                    step.TargetName.Contains(term, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
        }

        return false;
    }

    private void DrawQuestEntry(QuestEntry quest)
    {
        bool isSelected = quest.DBName == _state.SelectedQuestDBName;
        uint statusColor = GetQuestColor(quest);

        if (isSelected)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        // Level prefix in Selectable label. DrawList.AddText crashes after
        // ILRepack merges System.Numerics.Vectors (same class of P/Invoke
        // issue as Vector4 colors), so we use a single-color label instead.
        string label = quest.LevelEstimate?.Recommended is int lvl
            ? $"{lvl,2}  {quest.DisplayName}"
            : $"    {quest.DisplayName}";

        ImGui.PushStyleColor(ImGuiCol.Text, statusColor);

        if (ImGui.Selectable(label + "##" + quest.DBName, isSelected))
            _state.SelectQuest(quest.DBName);

        // Tooltip on hover: zone + status + level
        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            if (quest.ZoneContext != null)
                ImGui.Text(quest.ZoneContext);
            string status = _state.IsCompleted(quest.DBName) ? "Completed"
                          : _state.IsActive(quest.DBName) ? "Active"
                          : "Available";
            ImGui.Text(status);
            if (quest.LevelEstimate?.Recommended is int tipLvl)
                ImGui.Text($"Level {tipLvl}");
            ImGui.EndTooltip();
        }

        ImGui.PopStyleColor(isSelected ? 2 : 1);
    }

    private uint GetQuestColor(QuestEntry quest)
    {
        if (_state.IsActive(quest.DBName))
            return Theme.QuestActive;

        if (_state.IsCompleted(quest.DBName))
            return Theme.QuestCompleted;

        return Theme.QuestAvailable;
    }
}
