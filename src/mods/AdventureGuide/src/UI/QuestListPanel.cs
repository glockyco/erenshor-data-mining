using AdventureGuide.Data;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders the left panel: filter toggles, search bar, and scrollable quest list.
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
        // Fixed header: filter row + search (not scrollable)
        DrawFilterRow();
        DrawSearchBar();

        ImGui.Separator();

        // Scrollable quest list fills remaining height
        ImGui.BeginChild("##QuestScroll");
        DrawQuestList();
        ImGui.EndChild();
    }

    private void DrawFilterRow()
    {
        // Sync enum → index (in case FilterMode was changed externally)
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

        // Fill available width
        ImGui.SetNextItemWidth(-1);

        if (ImGui.InputTextWithHint("##QuestSearch", "Search quests...", ref _searchBuf, 256))
            _filter.SearchText = _searchBuf;

        ImGui.Spacing();
    }

    private void DrawQuestList()
    {
        var all = _data.All;

        for (int i = 0; i < all.Count; i++)
        {
            var quest = all[i];

            if (!PassesFilter(quest))
                continue;

            if (!PassesSearch(quest))
                continue;

            DrawQuestButton(quest);
        }
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

    private bool PassesSearch(QuestEntry quest)
    {
        if (string.IsNullOrEmpty(_filter.SearchText))
            return true;

        return quest.DisplayName.Contains(_filter.SearchText, StringComparison.OrdinalIgnoreCase);
    }

    private void DrawQuestButton(QuestEntry quest)
    {
        bool isSelected = quest.DBName == _state.SelectedQuestDBName;
        uint textColor = GetQuestColor(quest);

        if (isSelected)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        ImGui.PushStyleColor(ImGuiCol.Text, textColor);

        if (ImGui.Selectable(quest.DisplayName + "##" + quest.DBName, isSelected))
            _state.SelectedQuestDBName = quest.DBName;

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
