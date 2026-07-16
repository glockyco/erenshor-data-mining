using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.Diagnostics;
using AdventureGuide.Navigation;
using AdventureGuide.Patches;
using AdventureGuide.Rendering;
using AdventureGuide.State;
using AdventureGuide.UI;
using HarmonyLib;
using UnityEngine;
using UnityEngine.SceneManagement;

// See .agent/skills/mod-development/SKILL.md for mod architecture patterns

namespace AdventureGuide;

public sealed class AdventureGuideRuntime
{
    internal static IModLogger Log { get; private set; } = NullModLogger.Instance;

    private readonly IModLogger _logger;
    private readonly IGuideConfigBackend _backend;
    private readonly string _iniPath;

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
    private GuideWindow? _window;
    private TrackerState? _trackerState;
    private TrackerWindow? _tracker;
    private ImGuiRenderer? _imgui;

    private bool _wasTextInputActive;
    private bool _gameUIVisible = true;
    private bool _inGameplay;
    private bool _discoveryDone;
    private bool _wasEditUIMode;
    private bool _wantsMouseCapture;
    private bool _wantsTextInput;
    private bool _started;
    private bool _stopped;

    public AdventureGuideRuntime(IModLogger logger, IGuideConfigBackend config, string iniPath)
    {
        _logger = logger;
        _backend = config;
        _iniPath = iniPath;
    }

    public bool Start()
    {
        if (_started)
            return true;
        if (_stopped)
            return false;

        _started = true;
        Log = _logger;
        AdventureGuideLog.Current = _logger;

        try
        {
            _config = new GuideConfig(_backend);
            _data = GuideData.Load(_logger);
            _entities = new EntityRegistry();
            _state = new QuestStateTracker(_data, _entities);
            _state.LoadFromConfig(_config);
            _trackerState = new TrackerState();
            _trackerState.LoadFromConfig(_config);

            var uiScale = _config.UiScale.Value >= 0f ? _config.UiScale.Value : 1f;
            _config.ResolvedUiScale = uiScale;
            _imgui = new ImGuiRenderer(_logger) { UiScale = uiScale, IniPath = _iniPath };
            if (!_imgui.Init())
                throw new InvalidOperationException("Adventure Guide ImGui renderer init failed.");

            _config.UiScale.SettingChanged += OnUiScaleChanged;
            _config.ResetWindowLayout.SettingChanged += OnResetWindowLayout;
            _timers = new SpawnTimerTracker();
            _miningTracker = new MiningNodeTracker();
            var bridge = new SpawnPointBridge();
            _lootScanner = new LootScanner();

            _nav = new NavigationController(
                _data,
                _entities,
                _state,
                _timers,
                _miningTracker,
                _lootScanner
            );
            _state.WorkflowChanged += OnWorkflowChanged;
            _state.WorkflowCycleReset += OnWorkflowCycleReset;
            _arrow = new ArrowRenderer(_nav) { Enabled = _config.ShowArrow.Value };
            _config.ShowArrow.SettingChanged += OnShowArrowChanged;
            _groundPath = new GroundPathRenderer(_nav) { Enabled = _config.ShowGroundPath.Value };
            _config.ShowGroundPath.SettingChanged += OnShowGroundPathChanged;
            _markers = new WorldMarkerSystem(_data, _state, bridge, _lootScanner, _config)
            {
                Enabled = _config.ShowWorldMarkers.Value,
            };
            _config.ShowWorldMarkers.SettingChanged += OnShowWorldMarkersChanged;
            _config.TrackerEnabled.SettingChanged += OnTrackerEnabledChanged;
            _config.ReplaceQuestLog.SettingChanged += OnReplaceQuestLogChanged;

            var history = new NavigationHistory(_config.HistoryMaxSize.Value);
            _config.HistoryMaxSize.SettingChanged += (_, _) =>
                history.MaxSize = _config.HistoryMaxSize.Value;
            _window = new GuideWindow(_data, _state, _nav, history, _trackerState, _config);
            _state.SetHistory(history);
            _window.Filter.LoadFrom(_config);
            _tracker = new TrackerWindow(_data, _state, _nav, _trackerState, _window, _config);
            _imgui.OnLayout = () =>
            {
                _window.Draw();
                _tracker!.Draw();
                _arrow!.Draw();
                _config.LayoutResetRequested = false;
            };

            DebugAPI.Data = _data;
            DebugAPI.State = _state;
            DebugAPI.Filter = _window.Filter;
            DebugAPI.Nav = _nav;
            DebugAPI.Entities = _entities;
            DebugAPI.GroundPath = _groundPath;

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
            ScriptedEntityStartPatch.Tracker = _state;
            ScriptedRewardConsumedPatch.Tracker = _state;
            DeathPatch.Registry = _entities;
            DeathPatch.Timers = _timers;
            DeathPatch.Markers = _markers;
            DeathPatch.Loot = _lootScanner;
            DeathPatch.Tracker = _state;
            DeathPatch.Nav = _nav;
            QuestMarkerPatch.SuppressGameMarkers = _config.ShowWorldMarkers.Value;
            PointerOverUIPatch.WantsMouse = () => _wantsMouseCapture;
            QuestLogPatch.ReplaceQuestLog = _config.ReplaceQuestLog;
            SceneManager.sceneLoaded += OnSceneLoaded;

            _harmony = new Harmony(PluginInfo.GUID);
            _harmony.PatchAll();

            _state.OnSceneChanged(SceneManager.GetActiveScene().name);
            _entities.SyncFromLiveNPCs();
            _miningTracker.Rescan();
            _lootScanner.OnSceneLoaded();
            _trackerState.OnCharacterLoaded();
            _state.OnCharacterLoaded();
            _trackerState.PruneCompleted(_state, _data);
            _nav.LoadPerCharacter(_config, SceneManager.GetActiveScene().name);
            var currentScene = SceneManager.GetActiveScene().name;
            _inGameplay = currentScene != "Menu" && currentScene != "LoadScene";

            int withSteps = 0;
            foreach (var q in _data.All)
            {
                if (q.HasSteps)
                    withSteps++;
            }

            _logger.LogInfo(
                $"{PluginInfo.Name} v{PluginInfo.Version}\n"
                    + $"  Quests: {_data.Count} in guide, {withSteps} with step data\n"
                    + $"  Controls: {_config.ToggleKey.Value} = guide, {_config.TrackerToggleKey.Value} = tracker, {_config.GroundPathToggleKey.Value} = ground path"
            );
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(
                "Adventure Guide failed to start; unwinding partial initialization.",
                ex
            );
            Stop();
            return false;
        }
    }

    public void Tick()
    {
        if (!_started || _stopped)
            return;
        _tracker?.Update();

        bool gameUIVisible = GameUIVisibility.IsVisible;
        if (gameUIVisible != _gameUIVisible)
        {
            _gameUIVisible = gameUIVisible;
            SyncVisibility();
            if (!gameUIVisible)
            {
                ClearImGuiCaptureState();
                if (_wasTextInputActive)
                {
                    GameData.PlayerTyping = false;
                    _wasTextInputActive = false;
                }
            }
        }

        bool editMode = GameData.EditUIMode;
        if (_wasEditUIMode && !editMode)
            GameWindowOverlap.InvalidateRects();
        _wasEditUIMode = editMode;
        if (_gameUIVisible)
            CaptureImGuiState();

        if (_gameUIVisible)
        {
            bool textActive = _wantsTextInput;
            if (textActive && !_wasTextInputActive)
                GameData.PlayerTyping = true;
            else if (!textActive && _wasTextInputActive)
                GameData.PlayerTyping = false;
            _wasTextInputActive = textActive;
        }

        if (!_discoveryDone)
            TryMergeUnknownQuests();

        var currentZone = _state?.CurrentZone ?? "";
        _state?.Update(Time.deltaTime);
        if (_data != null && _state != null)
            _lootScanner?.Update(_data, _state);
        _nav?.Update(currentZone);
        _groundPath?.Update(currentZone);
        _markers?.Update(currentZone);

        if (_config == null || _window == null || !_inGameplay)
            return;
        if (!GameData.PlayerTyping && !_wantsTextInput)
            HandleKeyboardShortcuts();
        if (_wantsMouseCapture || GameData.PlayerTyping)
            return;
    }

    public void Draw()
    {
        if (!_started || _stopped || !_gameUIVisible)
            return;
        _imgui?.OnGUI();
    }

    public void Stop()
    {
        if (_stopped)
            return;
        _stopped = true;
        _started = false;

        SceneManager.sceneLoaded -= OnSceneLoaded;
        if (_wasTextInputActive)
            GameData.PlayerTyping = false;
        ClearImGuiCaptureState();

        if (_config != null)
        {
            _config.ShowArrow.SettingChanged -= OnShowArrowChanged;
            _config.ShowGroundPath.SettingChanged -= OnShowGroundPathChanged;
            _config.ShowWorldMarkers.SettingChanged -= OnShowWorldMarkersChanged;
            _config.TrackerEnabled.SettingChanged -= OnTrackerEnabledChanged;
            _config.ReplaceQuestLog.SettingChanged -= OnReplaceQuestLogChanged;
            _config.UiScale.SettingChanged -= OnUiScaleChanged;
            _config.ResetWindowLayout.SettingChanged -= OnResetWindowLayout;
        }
        if (_state != null)
        {
            _state.WorkflowChanged -= OnWorkflowChanged;
            _state.WorkflowCycleReset -= OnWorkflowCycleReset;
        }

        _harmony?.UnpatchSelf();
        _harmony = null;
        _tracker?.Dispose();
        _trackerState?.SaveToConfig();
        _state?.SaveToConfig();
        _nav?.SavePerCharacter();
        _imgui?.Dispose();
        _imgui = null;
        _arrow?.Dispose();
        _groundPath?.Destroy();
        _markers?.Destroy();
        _timers?.Clear();
        _entities?.Clear();
        _miningTracker?.Clear();
        MarkerFonts.Destroy();
        CameraCache.Invalidate();
        GameWindowOverlap.Reset();

        _config?.Dispose();
        _config = null;
        ClearPatchStatics();
        ClearDebugApi();
        _backend.Dispose();
        AdventureGuideLog.Reset();
        Log = NullModLogger.Instance;
    }

    private void TryMergeUnknownQuests()
    {
        if (_discoveryDone || _data == null)
            return;
        int result = _data.MergeUnknownQuests();
        if (result < 0)
            return;
        _discoveryDone = true;
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        if (_config!.UiScale.Value < 0f && scene.name != "Menu" && scene.name != "LoadScene")
            _config.UiScale.Value = DetectUiScale();
        CameraCache.Invalidate();
        GameWindowOverlap.Reset();
        _inGameplay = scene.name != "Menu" && scene.name != "LoadScene";
        if (!_inGameplay)
        {
            _window?.Hide();
            _tracker?.Hide();
            _nav?.Clear();
            ClearImGuiCaptureState();
        }
        _markers?.OnSceneLoaded();
        _entities?.Clear();
        _timers?.Clear();
        _miningTracker?.Rescan();
        _lootScanner?.OnSceneLoaded();
        _state?.OnSceneChanged(scene.name);
        _trackerState?.OnCharacterLoaded();
        _state?.OnCharacterLoaded();
        if (_trackerState != null && _state != null && _data != null)
            _trackerState.PruneCompleted(_state, _data);
        _nav?.LoadPerCharacter(_config!, scene.name);
        _nav?.OnGameStateChanged(scene.name);
    }

    private void OnShowArrowChanged(object sender, EventArgs e) => SyncVisibility();

    private void OnShowGroundPathChanged(object sender, EventArgs e) => SyncVisibility();

    private void OnUiScaleChanged(object sender, EventArgs e)
    {
        var scale = _config!.UiScale.Value;
        if (scale < 0f)
            scale = DetectUiScale();
        _config.ResolvedUiScale = scale;
        _config.LayoutResetRequested = true;
        _imgui?.SetScale(scale);
    }

    private void OnResetWindowLayout(object sender, EventArgs e)
    {
        if (!_config!.ResetWindowLayout.Value)
            return;
        _config.LayoutResetRequested = true;
        _imgui?.ClearWindowState();
        _config.ResetWindowLayout.Value = false;
    }

    private void OnShowWorldMarkersChanged(object sender, EventArgs e)
    {
        SyncVisibility();
        QuestMarkerPatch.SuppressGameMarkers = _config!.ShowWorldMarkers.Value;
    }

    private void OnTrackerEnabledChanged(object sender, EventArgs e) =>
        _trackerState!.Enabled = _config!.TrackerEnabled.Value;

    private void OnReplaceQuestLogChanged(object sender, EventArgs e)
    {
        if (!_config!.ReplaceQuestLog.Value)
            return;
        var ql = GameData.QuestLog;
        if (ql != null && ql.QuestWindow != null && ql.QuestWindow.activeSelf)
        {
            ql.QuestWindow.SetActive(false);
            _window?.Show();
        }
    }

    private void OnWorkflowChanged(QuestEntry quest)
    {
        _nav?.OnGameStateChanged(_state?.CurrentZone ?? "");
        _lootScanner?.MarkDirty();
    }

    private void OnWorkflowCycleReset(QuestEntry quest) =>
        _trackerState?.OnQuestCompleted(quest.RuntimeKey);

    private void SyncVisibility()
    {
        bool ui = _gameUIVisible;
        if (_arrow != null && _config != null)
            _arrow.Enabled = ui && _config.ShowArrow.Value;
        if (_groundPath != null && _config != null)
            _groundPath.Enabled = ui && _config.ShowGroundPath.Value;
        if (_markers != null && _config != null)
            _markers.Enabled = ui && _config.ShowWorldMarkers.Value;
    }

    private void HandleKeyboardShortcuts()
    {
        if (_config == null || _window == null)
            return;
        if (Input.GetKeyDown(_config.ToggleKey.Value))
            _window.Toggle();
        if (_config.ReplaceQuestLog.Value && Input.GetKeyDown(InputManager.Journal))
            _window.Toggle();
        if (_config.TrackerEnabled.Value && Input.GetKeyDown(_config.TrackerToggleKey.Value))
            _tracker?.Toggle();
        if (Input.GetKeyDown(_config.GroundPathToggleKey.Value))
            _config.ShowGroundPath.Value = !_config.ShowGroundPath.Value;
    }

    private void CaptureImGuiState()
    {
        _wantsMouseCapture = _imgui?.WantCaptureMouse ?? false;
        _wantsTextInput = _imgui?.WantTextInput ?? false;
    }

    private void ClearImGuiCaptureState()
    {
        _wantsMouseCapture = false;
        _wantsTextInput = false;
    }

    private static void ClearPatchStatics()
    {
        QuestAssignPatch.Tracker = null;
        QuestAssignPatch.Nav = null;
        QuestAssignPatch.Loot = null;
        QuestAssignPatch.TrackerPins = null;
        QuestFinishPatch.Tracker = null;
        QuestFinishPatch.Nav = null;
        QuestFinishPatch.Loot = null;
        QuestFinishPatch.TrackerPins = null;
        InventoryPatch.Tracker = null;
        InventoryPatch.Nav = null;
        InventoryPatch.Loot = null;
        SpawnPatch.Registry = null;
        SpawnPatch.Timers = null;
        SpawnPatch.Markers = null;
        SpawnPatch.Loot = null;
        ScriptedEntityStartPatch.Tracker = null;
        ScriptedRewardConsumedPatch.Tracker = null;
        DeathPatch.Registry = null;
        DeathPatch.Timers = null;
        DeathPatch.Markers = null;
        DeathPatch.Loot = null;
        DeathPatch.Tracker = null;
        DeathPatch.Nav = null;
        QuestMarkerPatch.SuppressGameMarkers = false;
        PointerOverUIPatch.WantsMouse = null;
        QuestLogPatch.ReplaceQuestLog = null;
    }

    private static void ClearDebugApi()
    {
        DebugAPI.Data = null;
        DebugAPI.State = null;
        DebugAPI.Filter = null;
        DebugAPI.Nav = null;
        DebugAPI.Entities = null;
        DebugAPI.GroundPath = null;
    }

    private static float DetectUiScale()
    {
        const float referenceHeight = 1080f;
        return Mathf.Clamp(Screen.height / referenceHeight, 0.5f, 4f);
    }
}
