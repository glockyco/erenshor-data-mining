using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.UI;

public sealed class GuideWindow
{
    private const int WindowId = 94217; // unique ID for IMGUI
    private const float LeftPanelRatio = 0.32f;
    private static readonly string[] TabNames = { "Active", "Completed", "All" };

    private readonly GuideData _data;
    private readonly QuestStateTracker _state;

    private Rect _windowRect = new(100, 100, 750, 500);
    private bool _visible;
    private int _selectedTab; // 0=Active, 1=Completed, 2=All
    private Vector2 _listScroll;
    private Vector2 _detailScroll;
    private GUIStyle? _windowStyle;
    private GUIStyle? _headerStyle;
    private GUIStyle? _stepDoneStyle;
    private GUIStyle? _stepCurrentStyle;
    private GUIStyle? _stepPendingStyle;
    private GUIStyle? _listButtonStyle;
    private GUIStyle? _listButtonSelectedStyle;
    private GUIStyle? _warnStyle;
    private bool _stylesInitialized;

    public bool Visible => _visible;

    public GuideWindow(GuideData data, QuestStateTracker state)
    {
        _data = data;
        _state = state;
    }

    public void Toggle() => _visible = !_visible;
    public void Show() => _visible = true;
    public void Hide() => _visible = false;

    public void Draw()
    {
        if (!_visible) return;
        InitStyles();
        _windowRect = GUILayout.Window(WindowId, _windowRect, DrawWindow, "Adventure Guide", _windowStyle);
        ClampToScreen();
    }

    private void ClampToScreen()
    {
        _windowRect.x = Mathf.Clamp(_windowRect.x, 0, Screen.width - _windowRect.width);
        _windowRect.y = Mathf.Clamp(_windowRect.y, 0, Screen.height - _windowRect.height);
    }

    private void InitStyles()
    {
        if (_stylesInitialized) return;
        _stylesInitialized = true;

        var bgTex = new Texture2D(1, 1);
        bgTex.SetPixel(0, 0, new Color(0.1f, 0.1f, 0.12f, 0.95f));
        bgTex.Apply();

        _windowStyle = new GUIStyle(GUI.skin.window);
        _windowStyle.normal.background = bgTex;
        _windowStyle.onNormal.background = bgTex;
        _windowStyle.normal.textColor = Color.white;
        _windowStyle.fontSize = 14;
        _windowStyle.fontStyle = FontStyle.Bold;

        _headerStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = 16, fontStyle = FontStyle.Bold,
            normal = { textColor = new Color(0.9f, 0.85f, 0.6f) },
            richText = true
        };

        _stepDoneStyle = new GUIStyle(GUI.skin.label)
        {
            richText = true,
            normal = { textColor = new Color(0.4f, 0.8f, 0.4f) }
        };
        _stepCurrentStyle = new GUIStyle(GUI.skin.label)
        {
            richText = true, fontStyle = FontStyle.Bold,
            normal = { textColor = new Color(1f, 0.9f, 0.3f) }
        };
        _stepPendingStyle = new GUIStyle(GUI.skin.label)
        {
            richText = true,
            normal = { textColor = new Color(0.6f, 0.6f, 0.6f) }
        };

        _listButtonStyle = new GUIStyle(GUI.skin.button)
        {
            alignment = TextAnchor.MiddleLeft, richText = true,
            normal = { textColor = Color.white },
            fontSize = 12
        };

        _listButtonSelectedStyle = new GUIStyle(_listButtonStyle);
        var selTex = new Texture2D(1, 1);
        selTex.SetPixel(0, 0, new Color(0.2f, 0.35f, 0.55f, 1f));
        selTex.Apply();
        _listButtonSelectedStyle.normal.background = selTex;
        _listButtonSelectedStyle.normal.textColor = Color.white;
        _listButtonSelectedStyle.fontStyle = FontStyle.Bold;

        _warnStyle = new GUIStyle(GUI.skin.label)
        {
            richText = true,
            normal = { textColor = new Color(1f, 0.5f, 0.3f) }
        };
    }

    private void DrawWindow(int id)
    {
        // Zone indicator
        if (!string.IsNullOrEmpty(_state.CurrentZone))
        {
            var zoneRect = new Rect(_windowRect.width - 200, 2, 195, 20);
            GUI.Label(zoneRect, $"<color=#88bbee><size=11>Zone: {_state.CurrentZone}</size></color>",
                new GUIStyle(GUI.skin.label) { richText = true, alignment = TextAnchor.MiddleRight });
        }

        // Tabs
        _selectedTab = GUILayout.Toolbar(_selectedTab, TabNames);
        GUILayout.Space(4);

        GUILayout.BeginHorizontal();

        // Left panel: quest list
        GUILayout.BeginVertical(GUILayout.Width(_windowRect.width * LeftPanelRatio));
        DrawQuestList();
        GUILayout.EndVertical();

        // Right panel: quest detail
        GUILayout.BeginVertical();
        DrawQuestDetail();
        GUILayout.EndVertical();

        GUILayout.EndHorizontal();

        GUI.DragWindow();
    }

    private void DrawQuestList()
    {
        _listScroll = GUILayout.BeginScrollView(_listScroll);

        foreach (var quest in _data.All)
        {
            bool show = _selectedTab switch
            {
                0 => _state.IsActive(quest.DBName),
                1 => _state.IsCompleted(quest.DBName),
                _ => true
            };
            if (!show) continue;

            bool isSelected = quest.DBName == _state.SelectedQuestDBName;
            var style = isSelected ? _listButtonSelectedStyle : _listButtonStyle;

            string label = quest.DisplayName;
            if (_state.IsCompleted(quest.DBName))
                label = $"<color=#66aa66>{label}</color>";

            if (GUILayout.Button(label, style))
            {
                _state.SelectedQuestDBName = quest.DBName;
            }
        }

        GUILayout.EndScrollView();
    }

    private void DrawQuestDetail()
    {
        if (_state.SelectedQuestDBName == null)
        {
            GUILayout.Label("Select a quest from the list.", _stepPendingStyle);
            return;
        }

        var quest = _data.GetByDBName(_state.SelectedQuestDBName);
        if (quest == null)
        {
            GUILayout.Label("Quest not found in guide data.", _warnStyle);
            return;
        }

        _detailScroll = GUILayout.BeginScrollView(_detailScroll);

        // Header
        GUILayout.Label(quest.DisplayName, _headerStyle);

        // Giver + Zone
        var giver = quest.Acquisition?.Find(a => a.Method == "dialog");
        if (giver?.SourceName != null)
            GUILayout.Label($"Given by: {giver.SourceName}");
        if (quest.ZoneContext != null)
            GUILayout.Label($"Zone: {quest.ZoneContext}");

        GUILayout.Space(4);

        // Description
        if (quest.Description != null)
        {
            GUILayout.Label(quest.Description, new GUIStyle(GUI.skin.label) { wordWrap = true, richText = true });
            GUILayout.Space(6);
        }

        // Steps
        if (quest.Steps != null && quest.Steps.Count > 0)
        {
            GUILayout.Label("<b>Objectives:</b>", new GUIStyle(GUI.skin.label) { richText = true });
            DrawSteps(quest);
            GUILayout.Space(6);
        }

        // Required Items
        if (quest.RequiredItems != null && quest.RequiredItems.Count > 0)
        {
            DrawRequiredItems(quest);
            GUILayout.Space(6);
        }

        // Rewards
        DrawRewards(quest);

        // Chain
        DrawChain(quest);

        // Flags/Warnings
        DrawFlags(quest);

        GUILayout.EndScrollView();
    }

    private void DrawSteps(QuestEntry quest)
    {
        int currentStepIndex = DetermineCurrentStep(quest);

        for (int i = 0; i < quest.Steps!.Count; i++)
        {
            var step = quest.Steps[i];
            GUIStyle style;
            string prefix;

            if (i < currentStepIndex)
            {
                style = _stepDoneStyle!;
                prefix = "[done]";
            }
            else if (i == currentStepIndex)
            {
                style = _stepCurrentStyle!;
                prefix = "[>>]  ";
            }
            else
            {
                style = _stepPendingStyle!;
                prefix = "[ ]   ";
            }

            string text = $"{prefix} {step.Order}. {step.Description}";

            // Show item count for collect steps
            if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
            {
                int have = _state.CountItemInInventory(step.TargetName);
                text += $" ({have}/{step.Quantity})";
            }

            GUILayout.Label(text, style);
        }
    }

    private int DetermineCurrentStep(QuestEntry quest)
    {
        if (_state.IsCompleted(quest.DBName))
            return quest.Steps!.Count; // all done

        if (!_state.IsActive(quest.DBName))
            return 0; // not started

        // Walk steps, find first incomplete
        for (int i = 0; i < quest.Steps!.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
            {
                int have = _state.CountItemInInventory(step.TargetName);
                if (have < step.Quantity.Value)
                    return i;
            }
            else if (step.Action == "travel" && step.ZoneName != null)
            {
                // Can't easily match scene name to zone display name without a lookup.
                // For now, this step is considered incomplete (conservative).
                // The step will auto-complete when the next step becomes current.
            }
            // talk, kill, shout, turn_in -- can't detect, assume prior steps done
        }

        // If all detectable steps are done, point to the last step
        return quest.Steps.Count - 1;
    }

    private void DrawRequiredItems(QuestEntry quest)
    {
        GUILayout.Label("<b>Required Items:</b>", new GUIStyle(GUI.skin.label) { richText = true });
        foreach (var item in quest.RequiredItems!)
        {
            int have = _state.CountItemInInventory(item.ItemName);
            var color = have >= item.Quantity ? "#66aa66" : "#dddddd";
            string text = $"  <color={color}>{have}/{item.Quantity} {item.ItemName}</color>";
            GUILayout.Label(text, new GUIStyle(GUI.skin.label) { richText = true });

            // Show drop sources
            if (item.DropSources != null)
            {
                foreach (var ds in item.DropSources)
                {
                    var zone = ds.ZoneName != null ? $" ({ds.ZoneName})" : "";
                    GUILayout.Label($"    Drops from: {ds.CharacterName}{zone}",
                        _stepPendingStyle);
                }
            }
        }
    }

    private void DrawRewards(QuestEntry quest)
    {
        var r = quest.Rewards;
        if (r == null) return;
        if (r.XP == 0 && r.Gold == 0 && r.ItemName == null) return;

        GUILayout.Label("<b>Rewards:</b>", new GUIStyle(GUI.skin.label) { richText = true });
        var parts = new List<string>();
        if (r.XP > 0) parts.Add($"{r.XP} XP");
        if (r.Gold > 0) parts.Add($"{r.Gold} Gold");
        if (parts.Count > 0)
            GUILayout.Label($"  {string.Join(" / ", parts)}");
        if (r.ItemName != null)
            GUILayout.Label($"  {r.ItemName}");
        if (r.FactionEffects != null)
        {
            foreach (var fe in r.FactionEffects)
            {
                var sign = fe.Amount >= 0 ? "+" : "";
                GUILayout.Label($"  {fe.FactionName}: {sign}{fe.Amount}");
            }
        }
        GUILayout.Space(4);
    }

    private void DrawChain(QuestEntry quest)
    {
        if (quest.Chain == null || quest.Chain.Count == 0) return;

        GUILayout.Label("<b>Quest Chain:</b>", new GUIStyle(GUI.skin.label) { richText = true });
        foreach (var link in quest.Chain)
        {
            string arrow = link.Relationship switch
            {
                "previous" => "<< ",
                "next" => ">> ",
                "completed_by" => "<= ",
                _ => "   "
            };
            bool isCompleted = _state.IsCompleted(link.QuestStableKey.Replace("quest:", ""));
            // Try matching by iterating -- stable key doesn't directly map to DBName
            // For chain navigation, make the label clickable
            var color = isCompleted ? "#66aa66" : "#dddddd";
            if (GUILayout.Button($"{arrow}<color={color}>{link.QuestName}</color>",
                new GUIStyle(GUI.skin.label) { richText = true }))
            {
                // Navigate to linked quest
                var linkedQuest = _data.GetByStableKey(link.QuestStableKey);
                if (linkedQuest != null)
                    _state.SelectedQuestDBName = linkedQuest.DBName;
            }
        }
        GUILayout.Space(4);
    }

    private void DrawFlags(QuestEntry quest)
    {
        var f = quest.Flags;
        if (f == null) return;

        if (f.KillTurnInHolder)
            GUILayout.Label("<color=#ff6644>Warning: Turning in this quest kills the NPC!</color>", _warnStyle);
        if (f.DestroyTurnInHolder)
            GUILayout.Label("<color=#ff6644>Warning: Turning in this quest destroys the NPC!</color>", _warnStyle);
        if (f.OncePerSpawnInstance)
            GUILayout.Label("<color=#ffaa44>Note: Can only be turned in once per NPC spawn cycle.</color>", _warnStyle);
        if (f.Repeatable)
            GUILayout.Label("<color=#88bbee>Repeatable quest.</color>",
                new GUIStyle(GUI.skin.label) { richText = true });
    }
}
