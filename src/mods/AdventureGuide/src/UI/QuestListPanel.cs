using System.Numerics;
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

    // ImGui.InputText needs a mutable byte buffer; keep one to avoid per-frame allocation.
    private string _searchBuf = string.Empty;

    private static readonly QuestFilterMode[] FilterModes =
        [QuestFilterMode.Active, QuestFilterMode.Available, QuestFilterMode.Completed, QuestFilterMode.All];

    public QuestListPanel(GuideData data, QuestStateTracker state, FilterState filter)
    {
        _data = data;
        _state = state;
        _filter = filter;
    }

    public void Draw(float width)
    {
        DrawFilterRow();
        DrawSearchBar(width);

        ImGui.Separator();

        DrawQuestList();
    }

    // ── Filter toggles ───────────────────────────────────────────────

    private void DrawFilterRow()
    {
        var modes = FilterModes;

        for (int i = 0; i < modes.Length; i++)
        {
            if (i > 0) ImGui.SameLine();

            var mode = modes[i];
            bool selected = _filter.FilterMode == mode;

            if (selected)
                ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

            if (ImGui.Button(mode.ToString()))
                _filter.FilterMode = mode;

            if (selected)
                ImGui.PopStyleColor();
        }

        ImGui.Spacing();
    }

    // ── Search bar ───────────────────────────────────────────────────

    private void DrawSearchBar(float panelWidth)
    {
        // Sync external mutations into the local buffer.
        if (_searchBuf != _filter.SearchText)
            _searchBuf = _filter.SearchText;

        ImGui.SetNextItemWidth(panelWidth - Theme.WindowPadding * 2);

        if (ImGui.InputTextWithHint("##QuestSearch", "Search quests...", ref _searchBuf, 256))
            _filter.SearchText = _searchBuf;

        ImGui.Spacing();
    }

    // ── Quest list ───────────────────────────────────────────────────

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

        // Highlight the selected quest with an accent background.
        if (isSelected)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        ImGui.PushStyleColor(ImGuiCol.Text, textColor);

        // Full-width selectable button.
        if (ImGui.Button(quest.DisplayName + "##" + quest.DBName, new Vector2(-1, 0)))
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
