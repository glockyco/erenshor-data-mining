using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.Diagnostics;
using AdventureGuide.Navigation;
using AdventureGuide.Patches;
using AdventureGuide.Rendering;
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
    private NavigationController? _nav;
    private ArrowRenderer? _arrow;
    private ImGuiRenderer? _imgui;
    private GuideWindow? _window;

    private void Awake()
    {
        Log = Logger;

        _config = new GuideConfig(Config);
        _data = GuideData.Load(Log);
        _state = new QuestStateTracker();

        _imgui = new ImGuiRenderer(Log) { UiScale = _config.UiScale.Value };
        if (!_imgui.Init())
        {
            Log.LogError("ImGui.NET init failed — mod cannot render UI");
            return;
        }

        _nav = new NavigationController(_data);
        _arrow = new ArrowRenderer(_nav);
        _arrow.Enabled = _config.ShowArrow.Value;
        _config.ShowArrow.SettingChanged += (_, _) => _arrow.Enabled = _config.ShowArrow.Value;

        _window = new GuideWindow(_data, _state, _nav);
        _imgui.OnLayout = () => { _window.Draw(); _arrow!.Draw(); };

        // Wire DebugAPI for HotRepl inspection
        DebugAPI.Data = _data;
        DebugAPI.State = _state;
        DebugAPI.Filter = _window.Filter;

        // Inject dependencies into Harmony patches
        QuestAssignPatch.Tracker = _state;
        QuestFinishPatch.Tracker = _state;
        InventoryPatch.Tracker = _state;
        PointerOverUIPatch.Renderer = _imgui;
        SceneManager.sceneLoaded += OnSceneLoaded;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();

        // Sync from current game state (essential for hot reload — no scene
        // load event fires, so without this the tracker starts empty)
        _state.OnSceneChanged(SceneManager.GetActiveScene().name);

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded ({_data.Count} quests)");
    }

    private bool _wasCapturingKeyboard;

    private void Update()
    {
        // Set game's typing flag when ImGui has keyboard focus (e.g., search
        // field). This prevents game keybinds from firing while typing. We
        // only set it to true, never force it false — other game UI (chat,
        // etc.) may also set it.
        bool imguiWantsKb = _imgui?.WantCaptureKeyboard ?? false;
        if (imguiWantsKb && !_wasCapturingKeyboard)
            GameData.PlayerTyping = true;
        else if (!imguiWantsKb && _wasCapturingKeyboard)
            GameData.PlayerTyping = false;
        _wasCapturingKeyboard = imguiWantsKb;

        // Update navigation state each frame
        _nav?.Update(_state?.CurrentZone ?? "");

        if (_config == null || _window == null) return;
        if (GameData.PlayerTyping) return;

        if (Input.GetKeyDown(_config.ToggleKey.Value))
            _window.Toggle();

        if (_config.ReplaceQuestLog.Value && Input.GetKeyDown(KeyCode.J))
            _window.Toggle();
    }

    private void OnGUI()
    {
        _imgui?.OnGUI();
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
        _arrow?.Dispose();

        DebugAPI.Data = null;
        DebugAPI.State = null;
        DebugAPI.Filter = null;
    }
}
