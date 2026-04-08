using AdventureGuide.CompiledGuide;
using System.Diagnostics;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using AdventureGuide.Config;
using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.Position.Resolvers;
using AdventureGuide.Patches;
using AdventureGuide.Rendering;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.State.Resolvers;
using AdventureGuide.UI.Tree;
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
    private EntityGraph? _graph;
    private GraphIndexes? _graphIndexes;
    private QuestStateTracker? _questTracker;
    private GameState? _gameState;
    private UnlockEvaluator? _unlockEvaluator;
    private GuideDependencyEngine? _dependencyEngine;
    private QuestResolutionService? _resolutionService;
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
    private LiveStateTracker? _liveState;
    private MarkerSystem? _markerSystem;
    private NavigationSetPersistence? _navPersistence;
    private WaterPositionResolver? _waterResolver;
    private CompiledSourceIndex? _sourceIndex;
    private NavigationTargetSelector? _targetSelector;
    private CompiledGuide.CompiledGuide? _compiledGuide;
    private QuestPhaseTracker? _compiledQuestTracker;
    private AdventureGuide.Resolution.UnlockPredicateEvaluator? _compiledUnlocks;
    private SpecTreeProjector? _specTreeProjector;
    private int _lastCompiledQuestTrackerVersion = -1;
    private int _lastResolutionVersion = -1;
    private int _lastNavSetVersion = -1;

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
        GuideDiagnostics.LogInfo = msg => Logger.LogInfo(msg);
        GuideDiagnostics.LogWarning = msg => Logger.LogWarning(msg);
        GuideDiagnostics.LogError = msg => Logger.LogError(msg);
        var startupSw = System.Diagnostics.Stopwatch.StartNew();

        // Hide the shared BepInEx manager GameObject so the game cannot
        // find and destroy it during scene cleanup.
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        _config = new GuideConfig(Config);

        // --- Graph layer ---
        var graphSw = System.Diagnostics.Stopwatch.StartNew();
        _graph = GraphLoader.Load(Log);
        var graphLoadMs = graphSw.Elapsed.TotalMilliseconds;
        graphSw.Restart();
        _graphIndexes = new GraphIndexes(_graph);
        var graphIndexMs = graphSw.Elapsed.TotalMilliseconds;
        graphSw.Restart();
        _sourceIndex = new CompiledSourceIndex(_graph);
        var sourceIndexMs = graphSw.Elapsed.TotalMilliseconds;

        try
        {
            _compiledGuide = CompiledGuideLoader.Load(Log);
            _compiledQuestTracker = new QuestPhaseTracker(_compiledGuide);
        }
        catch (Exception ex)
        {
            Log.LogWarning($"Compiled guide unavailable for detail panel: {ex.Message}");
        }

        _dependencyEngine = new GuideDependencyEngine();
        // --- State layer ---
        _questTracker = new QuestStateTracker(_graph, _graphIndexes, _dependencyEngine);
        _gameState = new GameState(_graph);
        _unlockEvaluator = new UnlockEvaluator(_graph, _gameState, _questTracker);
        _gameState.Register(NodeType.Quest, new QuestStateResolver(_questTracker));
        _gameState.Register(NodeType.Item, new ItemStateResolver(_questTracker));
        _gameState.Register(NodeType.ZoneLine, new ZoneLineStateResolver(_unlockEvaluator));

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

        // Views layer created after navigation layer (needs ZoneRouter)

        // --- Frontier layer ---
        _navSet = new NavigationSet();
        _navPersistence = new NavigationSetPersistence(_navSet, _config);

        // --- Navigation layer ---
        _liveState = new LiveStateTracker(
            _graph, _graphIndexes, _dependencyEngine, _unlockEvaluator);
        _zoneRouter = new ZoneRouter(_graph, _unlockEvaluator);

        // Register remaining state resolvers (character, spawn, mining, bag, door)
        _gameState.Register(NodeType.Character, new CharacterStateResolver(_liveState));
        _gameState.Register(NodeType.SpawnPoint, new SpawnPointStateResolver(_liveState));
        _gameState.Register(NodeType.MiningNode, new MiningNodeStateResolver(_liveState));
        _gameState.Register(NodeType.ItemBag, new ItemBagStateResolver(_liveState));
        _gameState.Register(NodeType.Door, new DoorStateResolver(_graph, _questTracker, _liveState));

        var positionRegistry = new PositionResolverRegistry(_graph);
        DirectPositionResolver.RegisterAll(positionRegistry);
        positionRegistry.Register(NodeType.Character,
            new CharacterPositionResolver(_graph, _liveState, _dependencyEngine));
        positionRegistry.Register(NodeType.MiningNode,
            new MiningNodePositionResolver(_liveState));
        positionRegistry.Register(NodeType.ItemBag,
            new ItemBagPositionResolver(_liveState));
        positionRegistry.Register(NodeType.Zone,
            new ZonePositionResolver(_graph));
        _waterResolver = new WaterPositionResolver(_graph);
        positionRegistry.Register(NodeType.Water, _waterResolver);

        var positionCache = new SourcePositionCache(positionRegistry, _graph);
        var planBuilder = new QuestPlanBuilder(_graph, _gameState, _zoneRouter, _questTracker, _unlockEvaluator);
        _resolutionService = new QuestResolutionService(
            _graph, _questTracker, _gameState, planBuilder,
            _dependencyEngine, _sourceIndex!, positionCache, _unlockEvaluator, _zoneRouter, _liveState);

        _targetSelector = new NavigationTargetSelector(_resolutionService, _zoneRouter, _graph, _liveState);

        _navEngine = new NavigationEngine(
            _navSet, _graph, _resolutionService, _targetSelector, _zoneRouter, _liveState, _unlockEvaluator);
        _arrow = new ArrowRenderer(_navEngine);
        _arrow.Enabled = _config.ShowArrow.Value;
        _config.ShowArrow.SettingChanged += OnShowArrowChanged;

        _groundPath = new GroundPathRenderer(_navEngine);
        _groundPath.Enabled = _config.ShowGroundPath.Value;
        _config.ShowGroundPath.SettingChanged += OnShowGroundPathChanged;

        // --- Markers layer ---
        _markerPool = new MarkerPool();
        _markerComputer = new MarkerComputer(_graph, _graphIndexes, _questTracker, _resolutionService, _liveState, _navSet, _trackerState);
        _markerSystem = new MarkerSystem(_markerComputer, _markerPool, _config);
        _markerSystem.Enabled = _config.ShowWorldMarkers.Value;

        _config.ShowWorldMarkers.SettingChanged += OnShowWorldMarkersChanged;
        _config.TrackerEnabled.SettingChanged += OnTrackerEnabledChanged;
        _config.ReplaceQuestLog.SettingChanged += OnReplaceQuestLogChanged;

        // --- UI layer ---
        var history = new NavigationHistory(_config.HistoryMaxSize.Value);
        _config.HistoryMaxSize.SettingChanged += (_, _) => history.MaxSize = _config.HistoryMaxSize.Value;
        _questTracker.SetHistory(history);

        ViewRenderer viewRenderer;
        var filter = new FilterState();
        filter.LoadFrom(_config);
        var listPanel = new QuestListPanel(_graph, _questTracker, filter, _trackerState);
        if (_compiledGuide != null && _compiledQuestTracker != null)
        {
            SyncCompiledQuestTracker();
            _compiledUnlocks = new AdventureGuide.Resolution.UnlockPredicateEvaluator(_compiledGuide, _compiledQuestTracker);
            _specTreeProjector = new SpecTreeProjector(_compiledGuide, _compiledQuestTracker, _compiledUnlocks);
            viewRenderer = new ViewRenderer(_compiledGuide, _navSet, _questTracker, _trackerState, _specTreeProjector);
            _window = new GuideWindow(_questTracker, history, _config, viewRenderer, listPanel, filter, _compiledGuide);
        }
        else
        {
            viewRenderer = new ViewRenderer(_graph, _gameState, _navSet, _questTracker, _trackerState);
            _window = new GuideWindow(_questTracker, history, _config, viewRenderer, listPanel, filter, _resolutionService);
        }

        if (_compiledGuide != null && _compiledQuestTracker != null)
        {
            _trackerPanel = new TrackerPanel(
                _graph, _questTracker, _trackerState, _navSet, _window, _config, _targetSelector,
                _compiledGuide, _compiledQuestTracker, new EffectiveFrontier(_compiledGuide, _compiledQuestTracker));
        }
        else
        {
            _trackerPanel = new TrackerPanel(
                _graph, _questTracker, _trackerState, _navSet, _window, _config, _targetSelector, _resolutionService);
        }
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
        DebugAPI.GroundPath = _groundPath;
        DebugAPI.Router = _zoneRouter;
        DebugAPI.Resolution = _resolutionService;
        DebugAPI.Markers = _markerComputer;
        DebugAPI.GameStateInstance = _gameState;

        // --- Harmony patches ---
        QuestAssignPatch.Tracker = _questTracker;
        QuestAssignPatch.Markers = _markerComputer;
        QuestAssignPatch.TrackerPins = _trackerState;
        QuestFinishPatch.Tracker = _questTracker;
        QuestFinishPatch.Markers = _markerComputer;
        QuestFinishPatch.TrackerPins = _trackerState;
        InventoryPatch.Tracker = _questTracker;
        InventoryPatch.Markers = _markerComputer;
        SpawnPatch.LiveState = _liveState;
        SpawnPatch.Markers = _markerComputer;
        DeathPatch.LiveState = _liveState;
        DeathPatch.Markers = _markerComputer;
        MiningNodePatch.LiveState = _liveState;
        MiningNodePatch.Markers = _markerComputer;
        ItemBagPatch.LiveState = _liveState;
        ItemBagPatch.Markers = _markerComputer;
        CorpseChestPatch.LiveState = _liveState;
        CorpseChestPatch.Markers = _markerComputer;
        QuestMarkerPatch.SuppressGameMarkers = _config.ShowWorldMarkers.Value;
        PointerOverUIPatch.Renderer = _imgui;
        QuestLogPatch.ReplaceQuestLog = _config.ReplaceQuestLog;
        SceneManager.sceneLoaded += OnSceneLoaded;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();

        // Sync from current game state (essential for hot reload)
        var syncSw = System.Diagnostics.Stopwatch.StartNew();
        var currentScene = SceneManager.GetActiveScene().name;
        _inGameplay = currentScene != "Menu" && currentScene != "LoadScene";

        var initialChangeSet = _questTracker.OnSceneChanged(currentScene);
        _liveState.OnSceneLoaded();
        _waterResolver.OnSceneLoaded();
        if (_inGameplay)
        {
            _trackerState.OnCharacterLoaded();
            _navPersistence.OnCharacterLoaded(_graph);
        }
        _navEngine.OnSceneChanged(currentScene);
        _markerComputer.ApplyGuideChangeSet(initialChangeSet);
        var syncMs = syncSw.Elapsed.TotalMilliseconds;

        // First marker recompute — this triggers cold quest resolution for all
        // actionable quests. Timed separately because it dominates cold start.
        Log.LogInfo("Adventure Guide startup: beginning first marker recompute");
        syncSw.Restart();
        _markerComputer.Recompute();
        var firstRecomputeMs = syncSw.Elapsed.TotalMilliseconds;
        Log.LogInfo($"Adventure Guide startup: first marker recompute finished in {firstRecomputeMs:F0} ms");

        _markerSystem.OnSceneChanged(currentScene);
        startupSw.Stop();

        var questCount = _graph.NodesOfType(NodeType.Quest).Count;
        var activeCount = _questTracker.ActiveQuests.Count;
        var completedCount = _questTracker.CompletedQuests.Count;
        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version}\n"
            + $"  Graph: {_graph.NodeCount} nodes, {_graph.EdgeCount} edges, {questCount} quests\n"
            + $"  State: {activeCount} active, {completedCount} completed, zone={currentScene}\n"
            + $"  Startup: {startupSw.Elapsed.TotalMilliseconds:F0} ms total\n"
            + $"    graph load:    {graphLoadMs:F0} ms\n"
            + $"    graph indexes: {graphIndexMs:F0} ms\n"
            + $"    source index:  {sourceIndexMs:F0} ms\n"
            + $"    state sync:    {syncMs:F0} ms\n"
            + $"    first markers: {firstRecomputeMs:F0} ms\n"
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

        // Per-frame updates — each step is timed into a 512-entry ring buffer.
        // Query GuideProfiler.DumpReport() via HotRepl to read results.
        var playerPos = GameData.PlayerControl != null ? GameData.PlayerControl.transform.position : Vector3.zero;
        long pt;

        pt = Stopwatch.GetTimestamp();
        var liveChangeSet = _liveState?.UpdateFrameState() ?? GuideChangeSet.None;
        GuideProfiler.LiveState.Record(pt);

        if (liveChangeSet.HasMeaningfulChanges)
        {
            pt = Stopwatch.GetTimestamp();
            _markerComputer?.ApplyGuideChangeSet(liveChangeSet);
            GuideProfiler.MarkerApply.Record(pt);
        }

        pt = Stopwatch.GetTimestamp();
        _markerComputer?.Recompute();
        GuideProfiler.MarkerRecompute.Record(pt);

        bool forceSelector = TargetSelectorRefreshPolicy.ShouldForce(
            liveChangeSet.HasMeaningfulChanges,
            _resolutionService!.Version,
            _lastResolutionVersion,
            _navSet!.Version,
            _lastNavSetVersion);
        if (forceSelector)
        {
            _lastResolutionVersion = _resolutionService.Version;
            _lastNavSetVersion     = _navSet!.Version;
        }

        pt = Stopwatch.GetTimestamp();
        _targetSelector?.Tick(playerPos.x, playerPos.y, playerPos.z, _navEngine!.CurrentScene, AllNavigableNodeKeys(), forceSelector);
        GuideProfiler.SelectorTick.Record(pt);

        pt = Stopwatch.GetTimestamp();
        _navEngine?.Update(playerPos);
        GuideProfiler.NavUpdate.Record(pt);

        pt = Stopwatch.GetTimestamp();
        _groundPath?.Update();
        GuideProfiler.GroundPath.Record(pt);

        pt = Stopwatch.GetTimestamp();
        _markerSystem?.Update();
        GuideProfiler.MarkerSysUpdate.Record(pt);
        SyncCompiledQuestTracker();

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

    private IEnumerable<string> AllNavigableNodeKeys()
    {
        foreach (var key in _navSet!.Keys)
            yield return key;
        foreach (var db in _trackerState!.TrackedQuests)
        {
            var node = _graph!.GetQuestByDbName(db);
            if (node != null) yield return node.Key;
        }
    }

    private void SyncCompiledQuestTracker()
    {
        if (_compiledQuestTracker == null || _questTracker == null)
            return;
        if (_lastCompiledQuestTrackerVersion == _questTracker.Version)
            return;

        _compiledQuestTracker.Initialize(
            _questTracker.CompletedQuests,
            _questTracker.ActiveQuests,
            _questTracker.InventoryCounts,
            _questTracker.KeyringItems);
        _lastCompiledQuestTrackerVersion = _questTracker.Version;
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
            _trackerPanel?.Hide();
            _navPersistence?.UnloadCurrentCharacter();
        }

        _liveState?.OnSceneLoaded();
        _waterResolver?.OnSceneLoaded();
        var sceneChangeSet = _questTracker?.OnSceneChanged(scene.name) ?? GuideChangeSet.None;
        if (_inGameplay)
        {
            _trackerState?.OnCharacterLoaded();
            _navPersistence?.OnCharacterLoaded(_graph!);
        }
        _navEngine?.OnSceneChanged(scene.name);
        _markerComputer?.ApplyGuideChangeSet(sceneChangeSet);
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
        _navPersistence?.SaveCurrentSelection();
        _navPersistence?.Dispose();
        _trackerPanel?.Dispose();
        _imgui?.Dispose();
        _arrow?.Dispose();
        _groundPath?.Destroy();
        _markerComputer?.Destroy();
        _markerSystem?.Destroy();
        MarkerFonts.Destroy();
        GuideDiagnostics.LogInfo = null;
        GuideDiagnostics.LogWarning = null;
        GuideDiagnostics.LogError = null;
        DebugAPI.Graph = null;
        DebugAPI.State = null;
        DebugAPI.Filter = null;
        DebugAPI.Nav = null;
        DebugAPI.GroundPath = null;
        DebugAPI.Router = null;
        DebugAPI.Resolution = null;
        DebugAPI.Markers = null;
        DebugAPI.GameStateInstance = null;
    }

    private static float DetectUiScale()
    {
        const float referenceHeight = 1080f;
        return Mathf.Clamp(Screen.height / referenceHeight, 0.5f, 4f);
    }
}
