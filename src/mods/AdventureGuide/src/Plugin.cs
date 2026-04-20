using System.Diagnostics;
using AdventureGuide.CompiledGuide;
using AdventureGuide.Config;
using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Incremental;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Markers.Queries;
using AdventureGuide.Navigation;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.Patches;
using AdventureGuide.Position;
using AdventureGuide.Position.Resolvers;
using AdventureGuide.Rendering;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using AdventureGuide.State.Resolvers;
using AdventureGuide.UI;
using AdventureGuide.UI.Tree;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;
using UnityEngine.SceneManagement;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

// See .agent/skills/mod-development/SKILL.md for mod architecture patterns

namespace AdventureGuide;

[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    internal static ManualLogSource Log { get; private set; } = null!;

    private const int DiagnosticsBufferCapacity = 512;
    private const int DiagnosticsIncidentCapacity = 12;
    private const int DiagnosticsRebuildStormCount = 5;
    private const int DiagnosticsResolutionExplosionTargetCount = 200;
    private const int DiagnosticsFrameHitchThresholdMs = 100;
    private const int DiagnosticsFrameStallThresholdMs = 250;
    private static readonly long DiagnosticsFrameHitchThresholdTicks =
        Stopwatch.Frequency * DiagnosticsFrameHitchThresholdMs / 1000;
    private static readonly long DiagnosticsFrameStallThresholdTicks =
        Stopwatch.Frequency * DiagnosticsFrameStallThresholdMs / 1000;
    private static readonly long DiagnosticsRebuildStormWindowTicks = Stopwatch.Frequency * 2;

    private Harmony? _harmony;
    private GuideConfig? _config;
    private QuestStateTracker? _questTracker;
    private GameState? _gameState;
    private UnlockEvaluator? _unlockEvaluator;
    private Engine<FactKey>? _engine;
    private GuideReader? _reader;
    private NavigationSet? _navSet;
    private NavigationEngine? _navEngine;
    private MarkerProjector? _markerProjector;

    private MarkerPool? _markerPool;
    private ZoneRouter? _zoneRouter;
    private ArrowRenderer? _arrow;
    private GroundPathRenderer? _groundPath;
    private ImGuiRenderer? _imgui;
    private GuideWindow? _window;
    private TrackerState? _trackerState;
    private TrackerPanel? _trackerPanel;
    private DiagnosticOverlay? _diagnosticOverlay;
    private IncidentPanel? _incidentPanel;
    private LiveStateTracker? _liveState;
    private MarkerRenderer? _markerRenderer;

    private NavigationSetPersistence? _navPersistence;
    private WaterPositionResolver? _waterResolver;
    private NavigationTargetSelector? _targetSelector;
    private CompiledGuideModel? _compiledGuide;
    private QuestPhaseTracker? _compiledQuestTracker;
    private AdventureGuide.Resolution.UnlockPredicateEvaluator? _compiledUnlocks;
    private SpecTreeProjector? _specTreeProjector;
    private EffectiveFrontier? _compiledFrontier;
    private SourceResolver? _compiledSourceResolver;

    private NavigationTargetResolver? _navigationTargetResolver;
    private CompiledTargetsQuery? _compiledTargetsQuery;
    private BlockingZonesQuery? _blockingZonesQuery;
    private NavigableQuestsQuery? _navigableQuestsQuery;
    private QuestResolutionQuery? _questResolutionQuery;
    private MarkerCandidatesQuery? _markerCandidatesQuery;
    private DiagnosticsCore? _diagnostics;


    private int _lastObservedQuestTrackerVersion = -1;

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

        // --- Data layer ---
        var graphSw = System.Diagnostics.Stopwatch.StartNew();
        _compiledGuide = CompiledGuideLoader.Load(Log);
        var graphLoadMs = graphSw.Elapsed.TotalMilliseconds;
        _engine = new Engine<FactKey>();

        _diagnostics = new DiagnosticsCore(

            eventCapacity: DiagnosticsBufferCapacity,
            spanCapacity: DiagnosticsBufferCapacity,
            incidentCapacity: DiagnosticsIncidentCapacity,
            incidentThresholds: new IncidentThresholds(
                frameHitchTicks: DiagnosticsFrameHitchThresholdTicks,
                frameStallTicks: DiagnosticsFrameStallThresholdTicks,
                rebuildStormCount: DiagnosticsRebuildStormCount,
                rebuildStormWindowTicks: DiagnosticsRebuildStormWindowTicks,
                resolutionExplosionTargetCount: DiagnosticsResolutionExplosionTargetCount
            )
        );

        // --- State layer ---
        _questTracker = new QuestStateTracker(_compiledGuide);

        _compiledQuestTracker = new QuestPhaseTracker(_compiledGuide, _questTracker);
        _gameState = new GameState(_compiledGuide);
        _unlockEvaluator = new UnlockEvaluator(_compiledGuide, _gameState, _questTracker);
        _gameState.Register(NodeType.Quest, NodeStateResolvers.Quest(_questTracker));
        _gameState.Register(NodeType.Item, NodeStateResolvers.Item(_questTracker));
        _gameState.Register(NodeType.ZoneLine, NodeStateResolvers.ZoneLine(_unlockEvaluator));

        _trackerState = new TrackerState();
        _trackerState.LoadFromConfig(_config);

        // --- ImGui ---
        var uiScale = _config.UiScale.Value >= 0f ? _config.UiScale.Value : 1f;
        _config.ResolvedUiScale = uiScale;
        var iniPath = System.IO.Path.Combine(
            BepInEx.Paths.ConfigPath,
            "wow-much.adventure-guide.imgui.ini"
        );
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
        _liveState = new LiveStateTracker(_compiledGuide, _unlockEvaluator);
        _zoneRouter = new ZoneRouter(_compiledGuide, _unlockEvaluator) { Diagnostics = _diagnostics };

        _gameState.Register(NodeType.Character, NodeStateResolvers.Character(_liveState));
        _gameState.Register(NodeType.SpawnPoint, NodeStateResolvers.SpawnPoint(_liveState));
        _gameState.Register(NodeType.MiningNode, NodeStateResolvers.MiningNode(_liveState));
        _gameState.Register(NodeType.ItemBag, NodeStateResolvers.ItemBag(_liveState));
        _gameState.Register(
            NodeType.Door,
            NodeStateResolvers.Door(_compiledGuide, _questTracker, _liveState)
        );

        var positionRegistry = new PositionResolverRegistry(_compiledGuide);
        DirectPositionResolver.RegisterAll(positionRegistry);
        positionRegistry.Register(
            NodeType.Character,
            new CharacterPositionResolver(_compiledGuide, _liveState)
        );

        positionRegistry.Register(NodeType.MiningNode, LiveStateBackedPositionResolver.MiningNode(_liveState));
        positionRegistry.Register(NodeType.ItemBag, LiveStateBackedPositionResolver.ItemBag(_liveState));
        positionRegistry.Register(NodeType.Zone, new ZonePositionResolver(_compiledGuide));
        _waterResolver = new WaterPositionResolver(_compiledGuide);
        positionRegistry.Register(NodeType.Water, _waterResolver);

        _compiledUnlocks = new AdventureGuide.Resolution.UnlockPredicateEvaluator(
            _compiledGuide,
            _compiledQuestTracker
        );
        _compiledFrontier = new EffectiveFrontier(_compiledGuide, _compiledQuestTracker);
        _compiledSourceResolver = new SourceResolver(
            _compiledGuide,
            _compiledQuestTracker,
            _compiledUnlocks,
            new CompiledGuideLivePositionProvider(_compiledGuide, _liveState),
            positionRegistry,
            _zoneRouter
        );

        var projector = new QuestTargetProjector(_compiledGuide, _zoneRouter);
        _reader = new GuideReader(
            _engine,
            inventory: _questTracker,
            questState: _questTracker,
            trackerState: _trackerState,
            navSet: _navSet,
            sourceState: _liveState);
        _compiledTargetsQuery = new CompiledTargetsQuery(
            _engine,
            _compiledGuide,
            _compiledFrontier,
            new QuestTargetResolver(_compiledGuide, _compiledFrontier, _compiledSourceResolver, _zoneRouter),
            _reader);
        _blockingZonesQuery = new BlockingZonesQuery(_engine, _compiledGuide, _zoneRouter);
        _navigableQuestsQuery = new NavigableQuestsQuery(_engine, _compiledGuide, _reader);
        _questResolutionQuery = new QuestResolutionQuery(
            _engine,
            _compiledTargetsQuery,
            _blockingZonesQuery,
            projector);
        _reader.SetQuestResolutionQuery(_questResolutionQuery);
        _reader.SetNavigableQuestsQuery(_navigableQuestsQuery);
        _markerCandidatesQuery = new MarkerCandidatesQuery(
            _engine,
            _compiledGuide,
            _reader,
            _navigableQuestsQuery,
            _questResolutionQuery);
        _reader.SetMarkerCandidatesQuery(_markerCandidatesQuery);
        _navigationTargetResolver = new NavigationTargetResolver(

            _compiledGuide,
            _reader,
            _zoneRouter,
            positionRegistry,
            projector,
            _diagnostics
        );



        _targetSelector = new NavigationTargetSelector(
            _navigationTargetResolver,
            _zoneRouter,
            _compiledGuide,
            _liveState,
            _diagnostics
        );

        _navEngine = new NavigationEngine(
            _navSet,
            _compiledGuide,
            _targetSelector,
            _zoneRouter,
            _liveState,
            _unlockEvaluator,
            _diagnostics
        );

        _arrow = new ArrowRenderer(_navEngine);
        _arrow.Enabled = _config.ShowArrow.Value;
        _config.ShowArrow.SettingChanged += OnShowArrowChanged;

        _groundPath = new GroundPathRenderer(_navEngine, _diagnostics);
        _groundPath.Enabled = _config.ShowGroundPath.Value;
        _config.ShowGroundPath.SettingChanged += OnShowGroundPathChanged;

        // --- Markers layer ---
        _markerPool = new MarkerPool();
        _markerProjector = new MarkerProjector(_reader, _liveState, _compiledGuide, _diagnostics);
        _markerRenderer = new MarkerRenderer(_markerProjector, _markerPool, _config, _diagnostics);
        _markerRenderer.Enabled = _config.ShowWorldMarkers.Value;


        _config.ShowWorldMarkers.SettingChanged += OnShowWorldMarkersChanged;
        _config.TrackerEnabled.SettingChanged += OnTrackerEnabledChanged;
        _config.ReplaceQuestLog.SettingChanged += OnReplaceQuestLogChanged;

        // --- UI layer ---
        var history = new NavigationHistory(_config.HistoryMaxSize.Value);
        _config.HistoryMaxSize.SettingChanged += (_, _) =>
            history.MaxSize = _config.HistoryMaxSize.Value;
        _questTracker.SetHistory(history);

        ViewRenderer viewRenderer;
        var filter = new FilterState(_config);
        var listPanel = new QuestListPanel(_compiledGuide, _questTracker, filter, _trackerState);
        _specTreeProjector = new SpecTreeProjector(
            _compiledGuide,
            _reader,
            _compiledQuestTracker,
            _questTracker,
            currentSceneProvider: () => _navEngine?.CurrentScene ?? string.Empty,
            diagnostics: _diagnostics
        );

        viewRenderer = new ViewRenderer(
            _compiledGuide,
            _gameState,
            _navSet,
            _questTracker,
            _trackerState,
            _specTreeProjector
        );
        _window = new GuideWindow(
            _questTracker,
            history,
            _config,
            viewRenderer,
            listPanel,
            filter,
            _compiledGuide
        );

        var trackerSummaryResolver = new TrackerSummaryResolver(
            _compiledGuide,
            _compiledQuestTracker,
            _reader,
            _diagnostics
        );

        _trackerPanel = new TrackerPanel(
            _compiledGuide,
            _questTracker,
            _trackerState,
            _navSet,
            _window,
            _config,
            _targetSelector,
            trackerSummaryResolver
        );

        _diagnosticOverlay = new DiagnosticOverlay(
            _questTracker,
            _markerProjector,

            _navSet,
            _config,
            _compiledGuide,
            _diagnostics!
        );
        _incidentPanel = new IncidentPanel(_config, _diagnostics!, DebugAPI.CaptureIncidentNow);

        _imgui.OnLayout = () =>
        {
            _window.Draw();
            _trackerPanel!.Draw();
            _diagnosticOverlay?.Render();
            _incidentPanel?.Render();
            _arrow!.Draw();
            _config.LayoutResetRequested = false;
        };

        // --- Debug API ---
        DebugAPI.Guide = _compiledGuide;
        DebugAPI.State = _questTracker;
        DebugAPI.Filter = _window.Filter;
        DebugAPI.Nav = _navEngine;
        DebugAPI.TargetSelector = _targetSelector;
        DebugAPI.GroundPath = _groundPath;

        DebugAPI.Router = _zoneRouter;
        DebugAPI.Unlocks = _unlockEvaluator;
        DebugAPI.Markers = _markerProjector;

        DebugAPI.GameStateInstance = _gameState;

        DebugAPI.Reader = _reader;

        DebugAPI.Resolver = _navigationTargetResolver;
        DebugAPI.Diagnostics = _diagnostics;
        DebugAPI.MarkerSnapshot = _markerProjector.ExportDiagnosticsSnapshot;

        DebugAPI.NavSnapshot = _targetSelector!.ExportDiagnosticsSnapshot;
        DebugAPI.TrackerSnapshot = trackerSummaryResolver.ExportDiagnosticsSnapshot;
        DebugAPI.TreeSnapshot = _specTreeProjector.ExportDiagnosticsSnapshot;

        // --- Harmony patches ---
        QuestAssignPatch.Tracker = _questTracker;

        QuestAssignPatch.TrackerPins = _trackerState;
        QuestFinishPatch.Tracker = _questTracker;

        QuestFinishPatch.TrackerPins = _trackerState;
        InventoryPatch.Tracker = _questTracker;

        SpawnPatch.LiveState = _liveState;

        DeathPatch.LiveState = _liveState;

        MiningNodePatch.LiveState = _liveState;

        ItemBagPatch.LiveState = _liveState;

        CorpseChestPatch.LiveState = _liveState;
        LootWindowCloseWindowPatch.LiveState = _liveState;
        LootWindowCloseWindowPatch.Engine = _engine;
        LootWindowCloseWindowPatch.ZoneRouter = _zoneRouter;
        LootWindowCloseWindowPatch.Selector = _targetSelector;

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
        // Fact publication is deferred below so NavSet/TrackerSet mutations from
        // OnCharacterLoaded are combined with the quest-tracker scene change in one
        // invalidation batch.

        _liveState.OnSceneLoaded();
        _waterResolver.OnSceneLoaded();
        if (_inGameplay)
        {
            _trackerState.OnCharacterLoaded();
            _navPersistence.OnCharacterLoaded(_compiledGuide);
        }
        _navEngine.OnSceneChanged(currentScene);

        var initialFacts = initialChangeSet.ChangedFacts

            .Concat(_navSet.DrainPendingFacts())
            .Concat(_trackerState.DrainPendingFacts());
        _engine?.InvalidateFacts(initialFacts);

        var syncMs = syncSw.Elapsed.TotalMilliseconds;

        syncSw.Restart();
        _reader.ReadMarkerCandidates(currentScene);


        // Capture the tracker version now so the first Update() tick does not
        // re-replay Awake's scene-change event, wipe the warm resolution cache,
        // and pay the full ~5 s marker batch cost a second time.
        _lastObservedQuestTrackerVersion = _questTracker.Version;

        var firstProjectionMs = syncSw.Elapsed.TotalMilliseconds;
        Log.LogInfo($"Adventure Guide startup: first projection: {firstProjectionMs:F0} ms");

        _markerRenderer.OnSceneChanged(currentScene);

        startupSw.Stop();

        var questCount = _compiledGuide.NodesOfType(NodeType.Quest).Count;
        var activeCount = _questTracker.ActiveQuests.Count;
        var completedCount = _questTracker.CompletedQuests.Count;
        Log.LogInfo(
            $"{PluginInfo.Name} v{PluginInfo.Version}\n"
                + $"  Graph: {_compiledGuide.NodeCount} nodes, {_compiledGuide.EdgeCount} edges, {questCount} quests\n"
                + $"  State: {activeCount} active, {completedCount} completed, zone={currentScene}\n"
                + $"  Startup: {startupSw.Elapsed.TotalMilliseconds:F0} ms total\n"
                + $"    data load:     {graphLoadMs:F0} ms\n"
                + $"    state sync:    {syncMs:F0} ms\n"
                + $"    first markers: {firstProjectionMs:F0} ms\n"

                + $"  Controls: {_config.ToggleKey.Value} = guide, {_config.TrackerToggleKey.Value} = tracker, {_config.GroundPathToggleKey.Value} = ground path\n"
                + $"  Config: BepInEx/config/{PluginInfo.GUID}.cfg\n"
                + $"  Tip: Install BepInEx ConfigurationManager for in-game settings (F1)"
        );
    }

    private bool _wasTextInputActive;
    private bool _gameUIVisible = true;
    private bool _inGameplay;
    private bool _wasEditUIMode;

    private void Update()
    {
        UpdateGameUiVisibility();
        UpdateEditUiMode();
        UpdatePlayerTyping();

        var (change, liveWorldChanged) = CapturePhase();
        PublishPhase(change);
        InvalidatePhase(change);
        ConsumePhase(liveWorldChanged);
        RenderPhase();
    }

    private void UpdateGameUiVisibility()
    {
        bool gameUIVisible = GameUIVisibility.IsVisible;
        if (gameUIVisible == _gameUIVisible)
            return;

        _gameUIVisible = gameUIVisible;
        SyncVisibility();
        if (gameUIVisible)
            return;

        _imgui?.ClearCaptureState();
        if (_wasTextInputActive)
        {
            GameData.PlayerTyping = false;
            _wasTextInputActive = false;
        }
    }

    private void UpdateEditUiMode()
    {
        bool editMode = GameData.EditUIMode;
        if (_wasEditUIMode && !editMode)
            GameWindowOverlap.InvalidateRects();
        _wasEditUIMode = editMode;
    }

    private void UpdatePlayerTyping()
    {
        if (!_gameUIVisible)
            return;

        bool textActive = _imgui?.WantTextInput ?? false;
        if (textActive && !_wasTextInputActive)
            GameData.PlayerTyping = true;
        else if (!textActive && _wasTextInputActive)
            GameData.PlayerTyping = false;
        _wasTextInputActive = textActive;
    }

    /// <summary>
    /// Observe frame-scoped state: live world, quest-tracker delta, and
    /// pending nav/tracker set facts. Returns the merged change set plus
    /// whether the live world moved this frame (used by the target selector
    /// to force an immediate re-score).
    /// </summary>
    private (ChangeSet Change, bool LiveWorldChanged) CapturePhase()
    {
        using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhaseCapture);

        var liveStateToken = _diagnostics?.BeginSpan(
            DiagnosticSpanKind.LiveStateUpdateFrame,
            DiagnosticsContext.Root(DiagnosticTrigger.LiveWorldChanged),
            primaryKey: _navEngine?.CurrentScene ?? string.Empty
        );
        long liveStateStart = Stopwatch.GetTimestamp();
        var liveChange = _liveState?.UpdateFrameState() ?? ChangeSet.None;
        if (liveStateToken != null)
        {
            _diagnostics!.EndSpan(
                liveStateToken.Value,
                Stopwatch.GetTimestamp() - liveStateStart,
                value0: liveChange.HasMeaningfulChanges ? 1 : 0,
                value1: 0
            );
        }

        ChangeSet stateChange = ChangeSet.None;
        if (_questTracker != null && _lastObservedQuestTrackerVersion != _questTracker.Version)
        {
            stateChange = _questTracker.LastChangeSet;
            _lastObservedQuestTrackerVersion = _questTracker.Version;
        }

        var navFacts = _navSet?.DrainPendingFacts() ?? Array.Empty<FactKey>();
        var trackerFacts = _trackerState?.DrainPendingFacts() ?? Array.Empty<FactKey>();
        var combined = stateChange.Merge(liveChange);
        if (navFacts.Count > 0 || trackerFacts.Count > 0)
        {
            combined = combined.Merge(new ChangeSet(
                inventoryChanged: false,
                questLogChanged: false,
                sceneChanged: false,
                liveWorldChanged: false,
                changedItemKeys: Array.Empty<string>(),
                changedQuestDbNames: Array.Empty<string>(),
                affectedQuestKeys: Array.Empty<string>(),
                changedFacts: navFacts.Concat(trackerFacts)
            ));
        }

        return (combined, liveChange.HasMeaningfulChanges);
    }

    /// <summary>
    /// Publish the captured change set: feed facts to the engine for
    /// invalidation, let the zone router observe fact flips that may
    /// affect route connectivity, and rebuild the router on scene change.
    /// </summary>
    private void PublishPhase(ChangeSet change)
    {
        using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhasePublish);
        if (!change.HasMeaningfulChanges)
            return;
        _targetSelector?.ObserveInvalidation(change);
        _engine?.InvalidateFacts(change.ChangedFacts);
        _zoneRouter?.ObserveInvalidation(change.ChangedFacts);
        if (change.SceneChanged)
            _zoneRouter?.Rebuild();
    }

    /// <summary>
    /// Reserved phase for signals the trackers do not express as facts.
    /// Empty in Plan B. The span still fires so frame-budget telemetry has
    /// a stable slot for Group 2+ work.
    /// </summary>
    private void InvalidatePhase(ChangeSet change)
    {
        using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhaseInvalidate);
        _ = change;
    }

    /// <summary>
    /// Read the post-invalidation maintained views and advance per-frame
    /// consumers: target selector, navigation engine, ground path,
    /// marker projector, and marker renderer.
    /// </summary>
    private void ConsumePhase(bool liveWorldChanged)
    {
        using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhaseConsume);
        var playerPos = GameData.PlayerControl != null
            ? GameData.PlayerControl.transform.position
            : Vector3.zero;
        var navigable = _reader!.ReadNavigableQuests();
        _targetSelector?.Tick(
            playerPos.x,
            playerPos.y,
            playerPos.z,
            _navEngine!.CurrentScene,
            navigable,
            liveWorldChanged
        );
        _navEngine?.Update(playerPos);
        _groundPath?.Update();
        _markerProjector?.Project();
        _markerRenderer?.Render();
    }

    /// <summary>
    /// Handle keybind input that affects next-frame rendering state.
    /// Gated on gameplay visibility and player-typing; does nothing when
    /// config or window are not yet initialised.
    /// </summary>
    private void RenderPhase()
    {
        using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhaseRender);
        if (_config == null || _window == null)
            return;
        if (!_inGameplay)
            return;
        if (GameData.PlayerTyping)
            return;

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
        if (!_gameUIVisible)
            return;
        _imgui?.OnGUI();
    }

    /// <summary>
    /// Out-of-band fact publication for scene load. Mirrors
    /// <see cref="CapturePhase"/> / <see cref="PublishPhase"/> without phase
    /// spans: scene change facts must reach the engine before the next
    /// <c>Update</c> tick so marker/selector reads observe the new scene.
    /// </summary>

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
        var sceneChangeSet = _questTracker?.OnSceneChanged(scene.name) ?? ChangeSet.None;
        _engine?.InvalidateFacts(sceneChangeSet.ChangedFacts);
        _markerProjector?.InvalidateProjection();

        if (_inGameplay)
        {
            _trackerState?.OnCharacterLoaded();
            _navPersistence?.OnCharacterLoaded(_compiledGuide!);
        }
        _navEngine?.OnSceneChanged(scene.name);
        _markerRenderer?.OnSceneChanged(scene.name);

    }

    private void OnShowArrowChanged(object sender, System.EventArgs e) => SyncVisibility();

    private void OnShowGroundPathChanged(object sender, System.EventArgs e) => SyncVisibility();

    private void OnUiScaleChanged(object sender, System.EventArgs e)
    {
        var scale = _config!.UiScale.Value;
        if (scale < 0f)
            scale = DetectUiScale();
        _config.ResolvedUiScale = scale;
        _config.LayoutResetRequested = true;
        _imgui?.SetScale(scale);
    }

    private void OnResetWindowLayout(object sender, System.EventArgs e)
    {
        if (!_config!.ResetWindowLayout.Value)
            return;
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
        if (!_config!.ReplaceQuestLog.Value)
            return;
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
        if (_markerRenderer != null)
            _markerRenderer.Enabled = ui && _config!.ShowWorldMarkers.Value;
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
        _compiledQuestTracker?.Dispose();
        _imgui?.Dispose();
        _arrow?.Dispose();
        _groundPath?.Destroy();
        _markerRenderer?.Destroy();
        MarkerFonts.Destroy();
        GuideDiagnostics.LogInfo = null;
        GuideDiagnostics.LogWarning = null;
        GuideDiagnostics.LogError = null;
        DebugAPI.Guide = null;
        DebugAPI.State = null;
        DebugAPI.Filter = null;
        DebugAPI.Nav = null;
        DebugAPI.TargetSelector = null;
        DebugAPI.GroundPath = null;
        DebugAPI.Router = null;
        DebugAPI.Unlocks = null;
        DebugAPI.Markers = null;
        DebugAPI.GameStateInstance = null;
        DebugAPI.Reader = null;
        DebugAPI.Resolver = null;
        DebugAPI.Diagnostics = null;
        DebugAPI.MarkerSnapshot = null;
        DebugAPI.NavSnapshot = null;
        DebugAPI.TrackerSnapshot = null;
        DebugAPI.TreeSnapshot = null;
    }

    private static float DetectUiScale()
    {
        const float referenceHeight = 1080f;
        return Mathf.Clamp(Screen.height / referenceHeight, 0.5f, 4f);
    }
}
