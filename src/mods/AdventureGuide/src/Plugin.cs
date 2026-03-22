using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.ImGui;
using AdventureGuide.Patches;
using AdventureGuide.State;
using AdventureGuide.UI;
using UnityEngine;
using UnityEngine.SceneManagement;

// See .agent/skills/mod-development/SKILL.md for mod architecture patterns

namespace AdventureGuide;

[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    internal static ManualLogSource Log { get; private set; } = null!;

    private Harmony? _harmony;
    private GuideConfig? _config;
    private GuideData? _data;
    private QuestStateTracker? _state;
    private GuideWindow? _window;
    private ImGuiRenderer? _imgui;
    private bool _imguiAvailable;
    private void Awake()
    {
        Log = Logger;

        _config = new GuideConfig(Config);
        _data = GuideData.Load(Log);
        _state = new QuestStateTracker();
        _window = new GuideWindow(_data, _state);

        // Inject state tracker into patches
        QuestAssignPatch.Tracker = _state;
        QuestFinishPatch.Tracker = _state;
        InventoryPatch.Tracker = _state;
        PointerOverUIPatch.Window = _window;
        SceneManager.sceneLoaded += OnSceneLoaded;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();

        // Sync from current game state (essential for hot reload — no scene
        // load event fires, so without this the tracker starts empty)
        _state.OnSceneChanged(SceneManager.GetActiveScene().name);

        // Initialize Dear ImGui rendering (optional — falls back to IMGUI if it fails)
        _imgui = new ImGuiRenderer(Log);
        _imguiAvailable = _imgui.Init();
        if (_imguiAvailable)
        {
            _imgui.OnLayout = DrawImGui;
            Log.LogInfo("Dear ImGui initialized — press F9 for demo window");
        }
        else
        {
            Log.LogWarning("Dear ImGui init failed — using Unity IMGUI fallback");
        }

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded ({_data.Count} quests)");
    }

    private bool _showDemoWindow;

    private void DrawImGui()
    {
        if (_showDemoWindow)
            ImGuiNET.ImGui.ShowDemoWindow(ref _showDemoWindow);
    }

    private void Update()
    {
        if (_config == null || _window == null) return;
        if (GameData.PlayerTyping) return;

        if (Input.GetKeyDown(_config.ToggleKey.Value))
            _window.Toggle();

        if (_config.ReplaceQuestLog.Value && Input.GetKeyDown(KeyCode.J))
            _window.Toggle();

        // F9 toggles Dear ImGui demo window (spike test)
        if (_imguiAvailable && Input.GetKeyDown(KeyCode.F9))
            _showDemoWindow = !_showDemoWindow;
    }

    private void OnGUI()
    {
        _window?.Draw();
        if (_imguiAvailable) _imgui?.OnGUI();
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        _state?.OnSceneChanged(scene.name);
    }

    private void OnDestroy()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
        _harmony?.UnpatchSelf();
        _imgui?.Dispose();
    }
}
