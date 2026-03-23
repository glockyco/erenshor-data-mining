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
    private EntityRegistry? _entities;
    private NavigationController? _nav;
    private ArrowRenderer? _arrow;
    private GroundPathRenderer? _groundPath;
    private WorldMarkerSystem? _markers;
    private SpawnTimerTracker? _timers;
    private MiningNodeTracker? _miningTracker;
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

        _entities = new EntityRegistry();
        _timers = new SpawnTimerTracker();
        _miningTracker = new MiningNodeTracker();
        var bridge = new SpawnPointBridge();

        _nav = new NavigationController(_data, _entities, _state, _timers, _miningTracker);
        _arrow = new ArrowRenderer(_nav);
        _arrow.Enabled = _config.ShowArrow.Value;
        _config.ShowArrow.SettingChanged += OnShowArrowChanged;

        _groundPath = new GroundPathRenderer(_nav);
        _groundPath.Enabled = _config.ShowGroundPath.Value;
        _config.ShowGroundPath.SettingChanged += OnShowGroundPathChanged;

        _markers = new WorldMarkerSystem(_data, _state, _entities, bridge, _miningTracker, _config);
        _markers.Enabled = _config.ShowWorldMarkers.Value;
        _config.ShowWorldMarkers.SettingChanged += OnShowWorldMarkersChanged;

        var history = new NavigationHistory(_config.HistoryMaxSize.Value);
        _config.HistoryMaxSize.SettingChanged += (_, _) => history.MaxSize = _config.HistoryMaxSize.Value;
        _window = new GuideWindow(_data, _state, _nav, history);
        _state.SetHistory(history);
        _window.Filter.LoadFrom(_config);
        _imgui.OnLayout = () => { _window.Draw(); _arrow!.Draw(); };

        // Wire DebugAPI for HotRepl inspection
        DebugAPI.Data = _data;
        DebugAPI.State = _state;
        DebugAPI.Filter = _window.Filter;
        DebugAPI.Nav = _nav;
        DebugAPI.Entities = _entities;
        DebugAPI.GroundPath = _groundPath;

        // Inject dependencies into Harmony patches
        QuestAssignPatch.Tracker = _state;
        QuestAssignPatch.Nav = _nav;
        QuestFinishPatch.Tracker = _state;
        QuestFinishPatch.Nav = _nav;
        InventoryPatch.Tracker = _state;
        InventoryPatch.Nav = _nav;
        SpawnPatch.Registry = _entities;
        SpawnPatch.Timers = _timers;
        DeathPatch.Registry = _entities;
        DeathPatch.Timers = _timers;
        QuestMarkerPatch.SuppressGameMarkers = _config.ShowWorldMarkers.Value;
        PointerOverUIPatch.Renderer = _imgui;
        SceneManager.sceneLoaded += OnSceneLoaded;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();

        // Sync from current game state (essential for hot reload — no scene
        // load event fires, so without this the tracker starts empty)
        _state.OnSceneChanged(SceneManager.GetActiveScene().name);
        _entities.SyncFromLiveNPCs();
        _miningTracker.Rescan();

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded ({_data.Count} quests)");
    }

    private bool _wasTextInputActive;

    private void Update()
    {
        // Set game's typing flag only when an ImGui text widget is actively
        // being edited (e.g., search field). WantTextInput is narrower than
        // WantCaptureKeyboard — the latter fires when any window has focus,
        // which would block movement (CanMove) on every window click.
        bool textActive = _imgui?.WantTextInput ?? false;
        if (textActive && !_wasTextInputActive)
            GameData.PlayerTyping = true;
        else if (!textActive && _wasTextInputActive)
            GameData.PlayerTyping = false;
        _wasTextInputActive = textActive;

        // Update navigation state each frame
        var currentZone = _state?.CurrentZone ?? "";
        _nav?.Update(currentZone);
        _groundPath?.Update(currentZone);
        _markers?.Update(currentZone);

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
        CameraCache.Invalidate();
        _entities?.Clear();
        _timers?.Clear();
        _miningTracker?.Rescan();
        _state?.OnSceneChanged(scene.name);
    }

    private void OnShowArrowChanged(object sender, System.EventArgs e) =>
        _arrow!.Enabled = _config!.ShowArrow.Value;

    private void OnShowGroundPathChanged(object sender, System.EventArgs e) =>
        _groundPath!.Enabled = _config!.ShowGroundPath.Value;

    private void OnShowWorldMarkersChanged(object sender, System.EventArgs e)
    {
        bool enabled = _config!.ShowWorldMarkers.Value;
        _markers!.Enabled = enabled;
        QuestMarkerPatch.SuppressGameMarkers = enabled;
        // When disabling, restore game markers on next NPC spawn
        // When enabling, game markers are suppressed via the prefix patch
    }

    private void OnDestroy()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
        if (_config != null)
        {
            _config.ShowArrow.SettingChanged -= OnShowArrowChanged;
            _config.ShowGroundPath.SettingChanged -= OnShowGroundPathChanged;
            _config.ShowWorldMarkers.SettingChanged -= OnShowWorldMarkersChanged;
            QuestMarkerPatch.SuppressGameMarkers = false;
        }
        _harmony?.UnpatchSelf();
        _imgui?.Dispose();
        _arrow?.Dispose();
        _groundPath?.Destroy();
        _markers?.Destroy();
        _timers?.Clear();
        _entities?.Clear();
        _miningTracker?.Clear();
        MarkerFonts.Destroy();

        DebugAPI.Data = null;
        DebugAPI.State = null;
        DebugAPI.Filter = null;
        DebugAPI.Nav = null;
        DebugAPI.Entities = null;
        DebugAPI.GroundPath = null;
    }
}
