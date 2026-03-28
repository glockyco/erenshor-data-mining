using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using AdventureGuide.Config;
using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Navigation.Resolvers;
using AdventureGuide.Patches;
using AdventureGuide.Rendering;
using AdventureGuide.State;
using AdventureGuide.State.Resolvers;
using AdventureGuide.UI;
using AdventureGuide.Views;
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
    private EntityGraph? _graph;
    private QuestStateTracker? _questTracker;
    private GameState? _gameState;
    private QuestViewBuilder? _viewBuilder;
    private NavigationSet? _navSet;
    private NavigationEngine? _navEngine;
    private MarkerComputer? _markerComputer;
    private MarkerPool? _markerPool;
    private ZoneRouter? _zoneRouter;
    private ArrowRenderer? _arrow;
    private GroundPathRenderer? _groundPath;
    private ImGuiRenderer? _imgui;
    private GuideWindow? _window;
    private TrackerState? _trackerState;
    private TrackerPanel? _trackerPanel;
    private EntityRegistry? _entities;
    private LiveStateTracker? _liveState;
    private MarkerSystem? _markerSystem;

    static Plugin()
    {
        // When installed via Thunderstore (separate DLLs, no ILRepack),
        // ImGui.NET.dll references System.Numerics.Vectors which Unity's
        // Mono doesn't ship. Intercept and redirect to System.Numerics.dll.
        AppDomain.CurrentDomain.AssemblyResolve += (_, args) =>
        {
            if (new System.Reflection.AssemblyName(args.Name).Name == "System.Numerics.Vectors")
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                    if (asm.GetName().Name == "System.Numerics")
                        return asm;
            return null;
        };
    }

    private void Awake()
    {
        Log = Logger;

        // Hide the shared BepInEx manager GameObject so the game cannot
        // find and destroy it during scene cleanup.
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        _config = new GuideConfig(Config);

        // --- Graph layer ---
        _graph = GraphLoader.Load(Log);

        // --- State layer ---
        _questTracker = new QuestStateTracker(_graph);
        _gameState = new GameState(_graph);
        _gameState.Register(NodeType.Quest, new QuestStateResolver(_questTracker));
        _gameState.Register(NodeType.Item, new ItemStateResolver(_questTracker));
        _gameState.Register(NodeType.ZoneLine, new ZoneLineStateResolver(_graph, _questTracker));

        _trackerState = new TrackerState();
        _trackerState.LoadFromConfig(_config);

        // --- ImGui ---
        var uiScale = _config.UiScale.Value >= 0f ? _config.UiScale.Value : 1f;
        _config.ResolvedUiScale = uiScale;
        var iniPath = System.IO.Path.Combine(BepInEx.Paths.ConfigPath, "wow-much.adventure-guide.imgui.ini");
        _imgui = new ImGuiRenderer(Log) { UiScale = uiScale, IniPath = iniPath };
        if (!_imgui.Init())
        {
            Log.LogError("ImGui.NET init failed — mod cannot render UI");
            return;
        }

        _config.UiScale.SettingChanged += OnUiScaleChanged;
        _config.ResetWindowLayout.SettingChanged += OnResetWindowLayout;

        // --- Views layer ---
        _viewBuilder = new QuestViewBuilder(_graph, _gameState);

        // --- Frontier layer ---
        _navSet = new NavigationSet();

        // --- Navigation layer ---
        _entities = new EntityRegistry();
        _liveState = new LiveStateTracker(_graph, _entities);
        _zoneRouter = new ZoneRouter(_graph, _gameState);

        // Register remaining state resolvers (character, spawn, mining, bag, door)
        _gameState.Register(NodeType.Character, new CharacterStateResolver(_liveState));
        _gameState.Register(NodeType.SpawnPoint, new SpawnPointStateResolver(_liveState));
        _gameState.Register(NodeType.MiningNode, new MiningNodeStateResolver(_liveState));
        _gameState.Register(NodeType.ItemBag, new ItemBagStateResolver());
        _gameState.Register(NodeType.Door, new DoorStateResolver(_questTracker));

        var positionRegistry = new PositionResolverRegistry(_graph);
        DirectPositionResolver.RegisterAll(positionRegistry);
        positionRegistry.Register(NodeType.Character,
            new CharacterPositionResolver(_entities, _graph));
        positionRegistry.Register(NodeType.Item,
            new ItemPositionResolver(_graph, positionRegistry));
        positionRegistry.Register(NodeType.Quest,
            new QuestPositionResolver(_viewBuilder, _gameState, positionRegistry));
        positionRegistry.Register(NodeType.ZoneLine,
            new ZoneLinePositionResolver());
        positionRegistry.Register(NodeType.Zone,
            new ZonePositionResolver(_graph));

        _navEngine = new NavigationEngine(
            _navSet, positionRegistry, _graph, _viewBuilder, _gameState,
            _questTracker, _zoneRouter, _entities);
        _arrow = new ArrowRenderer(_navEngine);
        _arrow.Enabled = _config.ShowArrow.Value;
        _config.ShowArrow.SettingChanged += OnShowArrowChanged;

        _groundPath = new GroundPathRenderer(_navEngine);
        _groundPath.Enabled = _config.ShowGroundPath.Value;
        _config.ShowGroundPath.SettingChanged += OnShowGroundPathChanged;

        // --- Markers layer ---
        _markerPool = new MarkerPool();
        _markerComputer = new MarkerComputer(_graph, _questTracker, _gameState, _viewBuilder, _liveState);
        _markerSystem = new MarkerSystem(_markerComputer, _markerPool, _config);
        _markerSystem.Enabled = _config.ShowWorldMarkers.Value;

        _config.ShowWorldMarkers.SettingChanged += OnShowWorldMarkersChanged;
        _config.TrackerEnabled.SettingChanged += OnTrackerEnabledChanged;
        _config.ReplaceQuestLog.SettingChanged += OnReplaceQuestLogChanged;

        // --- UI layer ---
        var history = new NavigationHistory(_config.HistoryMaxSize.Value);
        _config.HistoryMaxSize.SettingChanged += (_, _) => history.MaxSize = _config.HistoryMaxSize.Value;
        _questTracker.SetHistory(history);

        var viewRenderer = new ViewRenderer(_graph, _gameState, _navSet, _questTracker, _trackerState);
        var listPanel = new QuestListPanel(_graph, _questTracker, new FilterState(), _trackerState);
        _window = new GuideWindow(_graph, _questTracker, _viewBuilder, history, _trackerState, _config, viewRenderer, listPanel);
        _window.Filter.LoadFrom(_config);

        _trackerPanel = new TrackerPanel(_graph, _questTracker, _gameState, _trackerState, _viewBuilder, _navSet, _window, _config);
        _imgui.OnLayout = () =>
        {
            _window.Draw();
            _trackerPanel!.Draw();
            _arrow!.Draw();
            _config.LayoutResetRequested = false;
        };

        // --- Debug API ---
        DebugAPI.Graph = _graph;
        DebugAPI.State = _questTracker;
        DebugAPI.Filter = _window.Filter;
        DebugAPI.Nav = _navEngine;
        DebugAPI.Entities = _entities;
        DebugAPI.GroundPath = _groundPath;
        DebugAPI.Router = _zoneRouter;

        // --- Harmony patches ---
        QuestAssignPatch.Tracker = _questTracker;
        QuestAssignPatch.Markers = _markerComputer;
        QuestAssignPatch.TrackerPins = _trackerState;
        QuestFinishPatch.Tracker = _questTracker;
        QuestFinishPatch.Markers = _markerComputer;
        QuestFinishPatch.TrackerPins = _trackerState;
        InventoryPatch.Tracker = _questTracker;
        InventoryPatch.Markers = _markerComputer;
        SpawnPatch.Registry = _entities;
        SpawnPatch.LiveState = _liveState;
        SpawnPatch.Markers = _markerComputer;
        DeathPatch.Registry = _entities;
        DeathPatch.LiveState = _liveState;
        DeathPatch.Markers = _markerComputer;
        QuestMarkerPatch.SuppressGameMarkers = _config.ShowWorldMarkers.Value;
        PointerOverUIPatch.Renderer = _imgui;
        QuestLogPatch.ReplaceQuestLog = _config.ReplaceQuestLog;
        SceneManager.sceneLoaded += OnSceneLoaded;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();

        // Sync from current game state (essential for hot reload)
        _questTracker.OnSceneChanged(SceneManager.GetActiveScene().name);
        _entities.SyncFromLiveNPCs();
        _liveState.OnSceneLoaded();
        _trackerState.OnCharacterLoaded();
        _navEngine.OnSceneChanged(SceneManager.GetActiveScene().name);
        _markerComputer.MarkDirty();
        _markerSystem.OnSceneChanged(SceneManager.GetActiveScene().name);
        var currentScene = SceneManager.GetActiveScene().name;
        _inGameplay = currentScene != "Menu" && currentScene != "LoadScene";

        var questCount = _graph.NodesOfType(NodeType.Quest).Count;
        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version}\n"
            + $"  Graph: {_graph.NodeCount} nodes, {_graph.EdgeCount} edges, {questCount} quests\n"
            + $"  Controls: {_config.ToggleKey.Value} = guide, {_config.TrackerToggleKey.Value} = tracker, {_config.GroundPathToggleKey.Value} = ground path\n"
            + $"  Config: BepInEx/config/{PluginInfo.GUID}.cfg\n"
            + $"  Tip: Install BepInEx ConfigurationManager for in-game settings (F1)");
    }

    private bool _wasTextInputActive;
    private bool _gameUIVisible = true;
    private bool _inGameplay;
    private bool _wasEditUIMode;

    private void Update()
    {
        // Respect the game's F7 UI hide toggle
        bool gameUIVisible = GameUIVisibility.IsVisible;
        if (gameUIVisible != _gameUIVisible)
        {
            _gameUIVisible = gameUIVisible;
            SyncVisibility();
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

        bool editMode = GameData.EditUIMode;
        if (_wasEditUIMode && !editMode)
            GameWindowOverlap.InvalidateRects();
        _wasEditUIMode = editMode;

        // Text input state for game movement blocking
        if (_gameUIVisible)
        {
            bool textActive = _imgui?.WantTextInput ?? false;
            if (textActive && !_wasTextInputActive)
                GameData.PlayerTyping = true;
            else if (!textActive && _wasTextInputActive)
                GameData.PlayerTyping = false;
            _wasTextInputActive = textActive;
        }

        // Per-frame updates
        var playerPos = GameData.PlayerControl != null ? GameData.PlayerControl.transform.position : Vector3.zero;
        _markerComputer?.Recompute();
        _navEngine?.Update(playerPos);
        _groundPath?.Update();
        _markerSystem?.Update();

        if (_config == null || _window == null) return;
        if (!_inGameplay) return;
        if (GameData.PlayerTyping) return;

        if (Input.GetKeyDown(_config.ToggleKey.Value))
            _window.Toggle();

        if (_config.ReplaceQuestLog.Value && Input.GetKeyDown(InputManager.Journal))
            _window.Toggle();

        if (_config.TrackerEnabled.Value && Input.GetKeyDown(_config.TrackerToggleKey.Value))
            _trackerPanel?.Toggle();

        if (Input.GetKeyDown(_config.GroundPathToggleKey.Value))
            _config.ShowGroundPath.Value = !_config.ShowGroundPath.Value;
    }

    private void OnGUI()
    {
        if (!_gameUIVisible) return;
        _imgui?.OnGUI();
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        if (_config!.UiScale.Value < 0f && scene.name != "Menu" && scene.name != "LoadScene")
        {
            var scale = DetectUiScale();
            _config.UiScale.Value = scale;
        }
        CameraCache.Invalidate();
        GameWindowOverlap.Reset();

        _inGameplay = scene.name != "Menu" && scene.name != "LoadScene";
        if (!_inGameplay)
        {
            _window?.Hide();
        }

        _entities?.Clear();
        _liveState?.OnSceneLoaded();
        _questTracker?.OnSceneChanged(scene.name);
        _trackerState?.OnCharacterLoaded();
        _trackerState?.PruneCompleted(_questTracker!);
        _navEngine?.OnSceneChanged(scene.name);
        _markerComputer?.MarkDirty();
        _markerSystem?.OnSceneChanged(scene.name);
    }

    private void OnShowArrowChanged(object sender, System.EventArgs e) => SyncVisibility();
    private void OnShowGroundPathChanged(object sender, System.EventArgs e) => SyncVisibility();

    private void OnUiScaleChanged(object sender, System.EventArgs e)
    {
        var scale = _config!.UiScale.Value;
        if (scale < 0f) scale = DetectUiScale();
        _config.ResolvedUiScale = scale;
        _config.LayoutResetRequested = true;
        _imgui?.SetScale(scale);
    }

    private void OnResetWindowLayout(object sender, System.EventArgs e)
    {
        if (!_config!.ResetWindowLayout.Value) return;
        _imgui?.ClearWindowState();
        _config.LayoutResetRequested = true;
        _config.ResetWindowLayout.Value = false;
    }

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
        var ql = GameData.QuestLog;
        if (ql != null && ql.QuestWindow != null && ql.QuestWindow.activeSelf)
        {
            ql.QuestWindow.SetActive(false);
            _window?.Show();
        }
    }

    private void SyncVisibility()
    {
        bool ui = _gameUIVisible;
        _arrow!.Enabled = ui && _config!.ShowArrow.Value;
        _groundPath!.Enabled = ui && _config!.ShowGroundPath.Value;
        if (_markerSystem != null)
            _markerSystem.Enabled = ui && _config!.ShowWorldMarkers.Value;
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
            _config.UiScale.SettingChanged -= OnUiScaleChanged;
            _config.ResetWindowLayout.SettingChanged -= OnResetWindowLayout;
            QuestMarkerPatch.SuppressGameMarkers = false;
        }
        _harmony?.UnpatchSelf();
        _trackerState?.SaveToConfig();
        _trackerPanel?.Dispose();
        _imgui?.Dispose();
        _arrow?.Dispose();
        _groundPath?.Destroy();
        _markerSystem?.Destroy();
        _entities?.Clear();
        MarkerFonts.Destroy();
        DebugAPI.Graph = null;
        DebugAPI.State = null;
        DebugAPI.Filter = null;
        DebugAPI.Nav = null;
        DebugAPI.Entities = null;
        DebugAPI.GroundPath = null;
        DebugAPI.Router = null;
    }

    private static float DetectUiScale()
    {
        const float referenceHeight = 1080f;
        return Mathf.Clamp(Screen.height / referenceHeight, 0.5f, 4f);
    }
}
