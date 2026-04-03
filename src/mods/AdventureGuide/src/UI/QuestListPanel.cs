using AdventureGuide.Graph;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders the left panel: filter dropdown, search bar, and scrollable quest list.
/// </summary>
public sealed class QuestListPanel
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _state;
    private readonly FilterState _filter;
    private readonly TrackerState _tracker;

    private string _searchBuf = string.Empty;
    private readonly List<Node> _sorted = new();

    // Dirty-checking: skip re-filter/sort when nothing changed
    private int _lastFilterVersion = -1;
    private int _lastStateVersion = -1;

    private static readonly string[] FilterNames = { "Active", "Available", "Completed", "All" };
    private int _filterIndex;

    // Zone filter: index 0 = "All Zones", 1 = "Current Zone", 2+ = sorted zone names
    private const string CurrentZoneSentinel = "\x01current";
    private readonly string[] _zoneNames;
    private int _zoneIndex;

    // Scene → zone display name lookup, built once from graph zone nodes
    private readonly Dictionary<string, string> _sceneToZone;

    public QuestListPanel(EntityGraph graph, QuestStateTracker state, FilterState filter, TrackerState tracker)
    {
        _graph = graph;
        _state = state;
        _filter = filter;
        _tracker = tracker;

        // Build scene → zone display name map from zone nodes
        _sceneToZone = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var zone in graph.NodesOfType(NodeType.Zone))
        {
            if (zone.Scene != null)
                _sceneToZone[zone.Scene] = zone.DisplayName;
        }

        // Build sorted zone list from quest nodes' Zone field
        var zones = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var quest in graph.NodesOfType(NodeType.Quest))
            if (quest.Zone != null)
                zones.Add(quest.Zone);
        _zoneNames = new string[zones.Count + 2];
        _zoneNames[0] = "All Zones";
        _zoneNames[1] = "Current Zone";
        int idx = 2;
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
            if (_graph.NodesOfType(NodeType.Quest).Count == 0)
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
        {
            if (_filter.ZoneFilter == CurrentZoneSentinel)
            {
                _zoneIndex = 1;
            }
            else
            {
                for (int i = 2; i < _zoneNames.Length; i++)
                    if (string.Equals(_zoneNames[i], _filter.ZoneFilter, StringComparison.OrdinalIgnoreCase))
                    {
                        _zoneIndex = i;
                        break;
                    }
            }
        }

        ImGui.SetNextItemWidth(-1);
        if (ImGui.Combo("##Zone", ref _zoneIndex, _zoneNames, _zoneNames.Length))
        {
            _filter.ZoneFilter = _zoneIndex switch
            {
                0 => null,
                1 => CurrentZoneSentinel,
                _ => _zoneNames[_zoneIndex],
            };
        }

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
        bool stateChanged = _state.Version != _lastStateVersion;
        if (filterChanged || stateChanged)
        {
            _lastFilterVersion = _filter.Version;
            _lastStateVersion = _state.Version;

            _sorted.Clear();
            var all = _graph.NodesOfType(NodeType.Quest);
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

    private int CompareQuests(Node a, Node b)
    {
        return _filter.SortMode switch
        {
            QuestSortMode.ByLevel => CompareLevels(a, b),
            QuestSortMode.ByZone  => CompareZones(a, b),
            _                     => string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase),
        };
    }

    private static int CompareLevels(Node a, Node b)
    {
        int? la = a.Level;
        int? lb = b.Level;
        if (la == null && lb == null)
            return string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
        if (la == null) return 1;  // null sorts to end
        if (lb == null) return -1;
        int cmp = la.Value.CompareTo(lb.Value);
        return cmp != 0 ? cmp : string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
    }

    private static int CompareZones(Node a, Node b)
    {
        if (a.Zone == null && b.Zone == null)
            return string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
        if (a.Zone == null) return 1;  // null sorts to end
        if (b.Zone == null) return -1;
        int cmp = string.Compare(a.Zone, b.Zone, StringComparison.OrdinalIgnoreCase);
        return cmp != 0 ? cmp : string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
    }

    private bool PassesFilter(Node quest)
    {
        bool statusOk = _filter.FilterMode switch
        {
            QuestFilterMode.Active    => _state.IsActive(quest.DbName!),
            QuestFilterMode.Available => !_state.IsActive(quest.DbName!) && !_state.IsCompleted(quest.DbName!),
            QuestFilterMode.Completed => _state.IsCompleted(quest.DbName!),
            QuestFilterMode.All       => true,
            _ => true,
        };
        if (!statusOk) return false;

        // Zone filter
        if (_filter.ZoneFilter != null)
        {
            string? targetZone = _filter.ZoneFilter == CurrentZoneSentinel
                ? ResolveZoneDisplayName(_state.CurrentZone)
                : _filter.ZoneFilter;
            if (targetZone == null) return true; // current zone not resolvable
            return string.Equals(quest.Zone, targetZone, StringComparison.OrdinalIgnoreCase);
        }

        return true;
    }

    /// <summary>
    /// Search matches against quest name, zone, assigned-by NPCs, required items, and step targets.
    /// </summary>
    private bool PassesSearch(Node quest)
    {
        if (string.IsNullOrEmpty(_filter.SearchText))
            return true;

        var term = _filter.SearchText;

        if (quest.DisplayName.Contains(term, StringComparison.OrdinalIgnoreCase))
            return true;

        if (quest.Zone != null &&
            quest.Zone.Contains(term, StringComparison.OrdinalIgnoreCase))
            return true;

        // AssignedBy edges → NPC display names
        foreach (var edge in _graph.OutEdges(quest.Key, EdgeType.AssignedBy))
        {
            var target = _graph.GetNode(edge.Target);
            if (target != null && target.DisplayName.Contains(term, StringComparison.OrdinalIgnoreCase))
                return true;
        }

        // RequiresItem edges → item display names
        foreach (var edge in _graph.OutEdges(quest.Key, EdgeType.RequiresItem))
        {
            var target = _graph.GetNode(edge.Target);
            if (target != null && target.DisplayName.Contains(term, StringComparison.OrdinalIgnoreCase))
                return true;
        }

        // Step edges → target display names
        if (SearchStepEdges(quest.Key, EdgeType.StepTalk, term)) return true;
        if (SearchStepEdges(quest.Key, EdgeType.StepKill, term)) return true;
        if (SearchStepEdges(quest.Key, EdgeType.StepTravel, term)) return true;
        if (SearchStepEdges(quest.Key, EdgeType.StepShout, term)) return true;
        if (SearchStepEdges(quest.Key, EdgeType.StepRead, term)) return true;

        return false;
    }

    private bool SearchStepEdges(string questKey, EdgeType stepType, string term)
    {
        foreach (var edge in _graph.OutEdges(questKey, stepType))
        {
            var target = _graph.GetNode(edge.Target);
            if (target != null && target.DisplayName.Contains(term, StringComparison.OrdinalIgnoreCase))
                return true;
        }
        return false;
    }

    private void DrawQuestEntry(Node quest)
    {
        bool isSelected = quest.DbName == _state.SelectedQuestDBName;
        uint statusColor = Theme.GetQuestColor(_state, quest.DbName!);

        if (isSelected)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        // Level prefix in Selectable label. DrawList.AddText crashes after
        // ILRepack merges System.Numerics.Vectors (same class of P/Invoke
        // issue as Vector4 colors), so we use a single-color label instead.
        bool isTracked = _tracker.Enabled && _tracker.IsTracked(quest.DbName!);
        string prefix = isTracked ? "\u2022" : " ";
        string suffix = quest.Repeatable ? " [R]" : "";
        string label = quest.Level is int lvl
            ? $"{prefix}{lvl,2}  {quest.DisplayName}{suffix}"
            : $"{prefix}    {quest.DisplayName}{suffix}";

        ImGui.PushStyleColor(ImGuiCol.Text, statusColor);

        if (ImGui.Selectable(label + "##" + quest.DbName, isSelected))
            _state.SelectQuest(quest.DbName!);

        // Tooltip on hover: zone + status + level
        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            if (quest.Zone != null)
                ImGui.Text(quest.Zone);
            string status = _state.IsCompleted(quest.DbName!) ? "Completed"
                          : _state.IsImplicitlyAvailable(quest.DbName!) ? "Completable here"
                          : _state.IsActive(quest.DbName!) ? "Active"
                          : "Available";
            ImGui.Text(status);
            if (quest.Level is int tipLvl)
                ImGui.Text($"Level {tipLvl}");
            ImGui.EndTooltip();
        }

        ImGui.PopStyleColor(isSelected ? 2 : 1);
    }

    /// <summary>
    /// Resolves a scene name to its zone display name via graph zone nodes.
    /// </summary>
    private string? ResolveZoneDisplayName(string? sceneName)
    {
        if (sceneName == null) return null;
        return _sceneToZone.TryGetValue(sceneName, out var name) ? name : null;
    }
}
