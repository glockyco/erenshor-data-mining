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
    private LootScanner? _lootScanner;
    private ImGuiRenderer? _imgui;
    private GuideWindow? _window;
    private TrackerState? _trackerState;
    private TrackerWindow? _tracker;

    private void Awake()
    {
        Log = Logger;

        _config = new GuideConfig(Config);
        _data = GuideData.Load(Log);
        _state = new QuestStateTracker(_data);

        _trackerState = new TrackerState();
        _trackerState.LoadFromConfig(_config);

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
        _lootScanner = new LootScanner();

        _nav = new NavigationController(_data, _entities, _state, _timers, _miningTracker, _lootScanner);
        _arrow = new ArrowRenderer(_nav);
        _arrow.Enabled = _config.ShowArrow.Value;
        _config.ShowArrow.SettingChanged += OnShowArrowChanged;

        _groundPath = new GroundPathRenderer(_nav);
        _groundPath.Enabled = _config.ShowGroundPath.Value;
        _config.ShowGroundPath.SettingChanged += OnShowGroundPathChanged;

        _markers = new WorldMarkerSystem(_data, _state, bridge, _lootScanner, _config);
        _markers.Enabled = _config.ShowWorldMarkers.Value;
        _config.ShowWorldMarkers.SettingChanged += OnShowWorldMarkersChanged;

        _config.TrackerEnabled.SettingChanged += OnTrackerEnabledChanged;
        _config.ReplaceQuestLog.SettingChanged += OnReplaceQuestLogChanged;

        var history = new NavigationHistory(_config.HistoryMaxSize.Value);
        _config.HistoryMaxSize.SettingChanged += (_, _) => history.MaxSize = _config.HistoryMaxSize.Value;
        _window = new GuideWindow(_data, _state, _nav, history, _trackerState, _config);
        _state.SetHistory(history);
        _window.Filter.LoadFrom(_config);
        _tracker = new TrackerWindow(_data, _state, _nav, _trackerState, _window, _config);
        _imgui.OnLayout = () => { _window.Draw(); _tracker!.Draw(); _arrow!.Draw(); };

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
        QuestAssignPatch.Loot = _lootScanner;
        QuestAssignPatch.TrackerPins = _trackerState;
        QuestFinishPatch.Tracker = _state;
        QuestFinishPatch.Nav = _nav;
        QuestFinishPatch.Loot = _lootScanner;
        QuestFinishPatch.TrackerPins = _trackerState;
        InventoryPatch.Tracker = _state;
        InventoryPatch.Nav = _nav;
        InventoryPatch.Loot = _lootScanner;
        SpawnPatch.Registry = _entities;
        SpawnPatch.Timers = _timers;
        SpawnPatch.Markers = _markers;
        SpawnPatch.Loot = _lootScanner;
        DeathPatch.Registry = _entities;
        DeathPatch.Timers = _timers;
        DeathPatch.Markers = _markers;
        DeathPatch.Loot = _lootScanner;
        QuestMarkerPatch.SuppressGameMarkers = _config.ShowWorldMarkers.Value;
        PointerOverUIPatch.Renderer = _imgui;
        QuestLogPatch.ReplaceQuestLog = _config.ReplaceQuestLog;
        SceneManager.sceneLoaded += OnSceneLoaded;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();


        // Sync from current game state (essential for hot reload — no scene
        // load event fires, so without this the tracker starts empty)
        _state.OnSceneChanged(SceneManager.GetActiveScene().name);
        _entities.SyncFromLiveNPCs();
        _miningTracker.Rescan();
        _lootScanner.OnSceneLoaded();
        _trackerState.OnCharacterLoaded();
        _nav.LoadPerCharacter(_config, SceneManager.GetActiveScene().name);
        var currentScene = SceneManager.GetActiveScene().name;
        _inGameplay = currentScene != "Menu" && currentScene != "LoadScene";

        int withSteps = 0;
        foreach (var q in _data.All) { if (q.HasSteps) withSteps++; }

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version}\n"
            + $"  Quests: {_data.Count} in guide, {withSteps} with step data\n"
            + $"  Controls: {_config.ToggleKey.Value} = guide, {_config.TrackerToggleKey.Value} = tracker\n"
            + $"  Config: BepInEx/config/{PluginInfo.GUID}.cfg\n"
            + $"  Tip: Install BepInEx ConfigurationManager for in-game settings (F1)");
    }

    private void TryMergeUnknownQuests()
    {
        if (_discoveryDone || _data == null) return;
        int result = _data.MergeUnknownQuests();
        if (result < 0) return;  // QuestDB not ready yet
        _discoveryDone = true;
    }

    private bool _wasTextInputActive;
    private bool _gameUIVisible = true;
    private bool _inGameplay;
    private bool _discoveryDone;

    private void Update()
    {
        // Respect the game's F7 UI hide toggle. When the game HUD Canvas
        // is disabled, suppress all mod visuals. Navigation state still
        // updates so the UI is current when restored.
        bool gameUIVisible = GameUIVisibility.IsVisible;
        if (gameUIVisible != _gameUIVisible)
        {
            _gameUIVisible = gameUIVisible;
            SyncVisibility();

            // Clear ImGui capture state and game typing flag so mouse
            // input and movement aren't blocked while the UI is hidden.
            // Without this, WantCaptureMouse retains its last value from
            // when OnGUI was called, and PointerOverUIPatch keeps forcing
            // IsPointerOverGameObject to true.
            if (!gameUIVisible)
            {
                _imgui?.ClearCaptureState();
                if (_wasTextInputActive)
                {
                    GameData.PlayerTyping = false;
                    _wasTextInputActive = false;
                }
            }
        }

        // Set game's typing flag only when an ImGui text widget is actively
        // being edited (e.g., search field). WantTextInput is narrower than
        // WantCaptureKeyboard — the latter fires when any window has focus,
        // which would block movement (CanMove) on every window click.
        if (_gameUIVisible)
        {
            bool textActive = _imgui?.WantTextInput ?? false;
            if (textActive && !_wasTextInputActive)
                GameData.PlayerTyping = true;
            else if (!textActive && _wasTextInputActive)
                GameData.PlayerTyping = false;
            _wasTextInputActive = textActive;
        }

        // Retry quest discovery until QuestDB becomes available.
        // QuestDB.Start() runs after OnSceneLoaded, so the first
        // successful attempt is typically the frame after scene load.
        if (!_discoveryDone) TryMergeUnknownQuests();

        // Update shared systems before renderers. LootScanner runs here
        // (not inside WorldMarkerSystem) so nav gets fresh corpse/chest
        // data even when markers are disabled.
        var currentZone = _state?.CurrentZone ?? "";
        _lootScanner?.Update(_data!, _state!);
        _nav?.Update(currentZone);

        // Ground path and markers respect Enabled — when SyncVisibility
        // sets them to false, their Update methods early-return.
        _groundPath?.Update(currentZone);
        _markers?.Update(currentZone);

        if (_config == null || _window == null) return;
        if (!_inGameplay) return;
        if (GameData.PlayerTyping) return;

        if (Input.GetKeyDown(_config.ToggleKey.Value))
            _window.Toggle();

        if (_config.ReplaceQuestLog.Value && Input.GetKeyDown(InputManager.Journal))
            _window.Toggle();

        if (_config.TrackerEnabled.Value && Input.GetKeyDown(_config.TrackerToggleKey.Value))
            _tracker?.Toggle();
    }

    private void OnGUI()
    {
        if (!_gameUIVisible) return;
        _imgui?.OnGUI();
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        CameraCache.Invalidate();


        // Track whether we're in a gameplay scene
        _inGameplay = scene.name != "Menu" && scene.name != "LoadScene";
        if (!_inGameplay)
        {
            _window?.Hide();
            _tracker?.Hide();
            _nav?.Clear();
        }
        _markers?.OnSceneLoaded();  // deactivate markers before camera goes stale
        _entities?.Clear();
        _timers?.Clear();
        _miningTracker?.Rescan();
        _lootScanner?.OnSceneLoaded();
        _state?.OnSceneChanged(scene.name);
        // Load per-character state (tracked quests, navigation target).
        // These use slot-guarded binding: first call reads from config,
        // subsequent calls for the same character are no-ops.
        _trackerState?.OnCharacterLoaded();
        _trackerState?.PruneCompleted(_state!);
        _nav?.LoadPerCharacter(_config!, scene.name);
        // Rebuild ZoneGraph and auto-advance navigation if the restored
        // target's step is behind the player's current progress.
        _nav?.OnGameStateChanged(scene.name);
    }

    private void OnShowArrowChanged(object sender, System.EventArgs e) => SyncVisibility();

    private void OnShowGroundPathChanged(object sender, System.EventArgs e) => SyncVisibility();

    private void OnShowWorldMarkersChanged(object sender, System.EventArgs e)
    {
        SyncVisibility();
        QuestMarkerPatch.SuppressGameMarkers = _config!.ShowWorldMarkers.Value;
    }

    private void OnTrackerEnabledChanged(object sender, System.EventArgs e)
    {
        _trackerState!.Enabled = _config!.TrackerEnabled.Value;
    }

    private void OnReplaceQuestLogChanged(object sender, System.EventArgs e)
    {
        if (!_config!.ReplaceQuestLog.Value) return;

        // Close the native journal if it's open and show the guide instead
        var ql = GameData.QuestLog;
        if (ql != null && ql.QuestWindow != null && ql.QuestWindow.activeSelf)
        {
            ql.QuestWindow.SetActive(false);
            _window?.Show();
        }
    }

    /// <summary>
    /// Applies effective visibility = config setting AND game UI visible.
    /// Called on config changes and on game UI visibility transitions.
    /// </summary>
    private void SyncVisibility()
    {
        bool ui = _gameUIVisible;
        _arrow!.Enabled = ui && _config!.ShowArrow.Value;
        _groundPath!.Enabled = ui && _config!.ShowGroundPath.Value;
        _markers!.Enabled = ui && _config!.ShowWorldMarkers.Value;
    }

    private void OnDestroy()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
        if (_config != null)
        {
            _config.ShowArrow.SettingChanged -= OnShowArrowChanged;
            _config.ShowGroundPath.SettingChanged -= OnShowGroundPathChanged;
            _config.ShowWorldMarkers.SettingChanged -= OnShowWorldMarkersChanged;
            _config.TrackerEnabled.SettingChanged -= OnTrackerEnabledChanged;
            _config.ReplaceQuestLog.SettingChanged -= OnReplaceQuestLogChanged;
            QuestMarkerPatch.SuppressGameMarkers = false;
        }
        _harmony?.UnpatchSelf();
        _tracker?.Dispose();

        // Window geometry is saved each frame inside Draw (requires active
        // ImGui window context). TrackerState and NavigationController
        // persist per-character state to config.
        _trackerState?.SaveToConfig();
        _nav?.SavePerCharacter();
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