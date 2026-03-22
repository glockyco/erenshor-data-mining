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

    private static readonly string[] FilterNames = { "Active", "Available", "Completed", "All" };
    private int _filterIndex;

    public QuestListPanel(GuideData data, QuestStateTracker state, FilterState filter)
    {
        _data = data;
        _state = state;
        _filter = filter;
    }

    public void Draw(float width)
    {
        // Fixed header: filter + search (not scrollable)
        DrawFilterRow();
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

    private void DrawFilterRow()
    {
        _filterIndex = (int)_filter.FilterMode;

        ImGui.SetNextItemWidth(-1);
        if (ImGui.Combo("##Filter", ref _filterIndex, FilterNames, FilterNames.Length))
            _filter.FilterMode = (QuestFilterMode)_filterIndex;

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

    /// <summary>Draw filtered quest list. Returns count of visible quests.</summary>
    private int DrawQuestList()
    {
        int count = 0;
        var all = _data.All;

        for (int i = 0; i < all.Count; i++)
        {
            var quest = all[i];

            if (!PassesFilter(quest))
                continue;

            if (!PassesSearch(quest))
                continue;

            DrawQuestEntry(quest);
            count++;
        }

        return count;
    }

    private bool PassesFilter(QuestEntry quest)
    {
        return _filter.FilterMode switch
        {
            QuestFilterMode.Active    => _state.IsActive(quest.DBName),
            QuestFilterMode.Available => !_state.IsActive(quest.DBName) && !_state.IsCompleted(quest.DBName),
            QuestFilterMode.Completed => _state.IsCompleted(quest.DBName),
            QuestFilterMode.All       => true,
            _ => true,
        };
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
        uint textColor = GetQuestColor(quest);

        if (isSelected)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        ImGui.PushStyleColor(ImGuiCol.Text, textColor);

        if (ImGui.Selectable(quest.DisplayName + "##" + quest.DBName, isSelected))
            _state.SelectedQuestDBName = quest.DBName;

        // Tooltip on hover: zone + status
        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            if (quest.ZoneContext != null)
                ImGui.Text(quest.ZoneContext);
            string status = _state.IsCompleted(quest.DBName) ? "Completed"
                          : _state.IsActive(quest.DBName) ? "Active"
                          : "Available";
            ImGui.Text(status);
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
