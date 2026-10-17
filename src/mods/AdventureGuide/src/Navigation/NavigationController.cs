using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;
using UnityEngine.AI;

namespace AdventureGuide.Navigation;

/// <summary>
/// Resolves quest steps to navigation targets and manages the active
/// navigation state. Uses EntityRegistry for O(1) live NPC lookups
/// (closest alive NPC by display name), falling back to static spawn
/// data from the guide JSON.
/// </summary>
public sealed class NavigationController
{
    private readonly GuideData _data;
    private readonly EntityRegistry _entities;
    private readonly QuestStateTracker _state;
    private readonly Func<string, int> _countItem;
    private readonly SpawnTimerTracker _timers;
    private readonly MiningNodeTracker _miningTracker;
    private readonly LootScanner _lootScanner;
    private readonly ZoneGraph _zoneGraph;
    private readonly RequirementResolver _requirements;
    private int _lastResolvedStateVersion = int.MinValue;
    private string? _lastResolvedScene;
    private readonly HashSet<string> _reportedResolutionErrors = new(
        StringComparer.OrdinalIgnoreCase
    );
    private QuestStep? _navigationOverride;
    private readonly SourceNavigationSelection _sourceSelection = new();

    private RequirementResolution? _requirementResult;
    public RequirementResolution? Requirements
    {
        get => _requirementResult;
        private set
        {
            _requirementResult = value;
            ImmediateRequirement = null;
            if (value == null)
                return;
            for (int i = value.Chain.Count - 1; i >= 0; i--)
                if (value.Chain[i].Atom is { Kind: not GateAtomKind.EncounterWon } atom)
                {
                    ImmediateRequirement =
                        atom.Kind is GateAtomKind.KeyHeld or GateAtomKind.ItemHeld
                        && _data.GateItems.TryGetValue(atom.Ref, out var item)
                            ? $"Needs {item.Name}"
                            : value.Chain[i].Label;
                    break;
                }
        }
    }
    public string? ImmediateRequirement { get; private set; }
    public string? NextActionLabel =>
        SelectedSourceSummary ?? (Target == null ? null : _resolvedStep?.Description);
    public ZoneLineEntry? ChosenEntryLine => _chosenEntryLine ?? Requirements?.EntryLine;

    public ZoneGraph.Destination? ResolveDestination(ZoneLineEntry line) =>
        _zoneGraph.ResolveDestination(line);

    public string? GetZoneLineDestinationDisplay(ZoneLineEntry line)
    {
        var destination = ResolveDestination(line);
        if (!destination.HasValue)
            return null;
        return _data.ZoneLineDestinationContexts.ContainsKey(line.StableKey)
            ? _data.GetZoneDisplayName(destination.Value.Scene)
            : line.DestinationDisplay;
    }

    private bool CanUseZoneLine(ZoneLineEntry line) =>
        ResolveDestination(line).HasValue
        && NavigationResolutionPolicy.CanUseZoneLine(line, _state.Gates);

    public ItemSource? SelectedItemSource { get; private set; }
    public ItemSource? ChosenItemSource => _sourceSelection.Source;
    public string? SelectedSourceSummary { get; private set; }
    public string? SelectedSourceLocation { get; private set; }
    public string? SelectedSourceOdds { get; private set; }
    public string? SelectedSourceTiming =>
        SelectedItemSource == null
            ? null
            : UI.SourceListText.Timing(SelectedItemSource, GameData.Time.hour);

    private void SetSelectedSource(ItemSource? source)
    {
        if (ReferenceEquals(source, SelectedItemSource))
            return;
        SelectedItemSource = source;
        SelectedSourceSummary =
            source == null
                ? null
                : "Next: "
                    + UI.SourceListText.Action(
                        source,
                        Requirements?.Step is { TargetType: "item" } step ? step.TargetName : null
                    );
        SelectedSourceLocation = source == null ? null : UI.SourceListText.Location(source);
        SelectedSourceOdds =
            source?.Type == "fishing" ? UI.SourceListText.OptionOdds(source) : null;
    }

    public string CurrentScene => _state.CurrentZone;
    public QuestEntry? OriginQuest =>
        _originQuestKey == null ? null : _data.GetByRuntimeKey(_originQuestKey);
    public QuestStep? OriginStep
    {
        get
        {
            var steps = OriginQuest?.Steps;
            if (steps != null)
                foreach (var step in steps)
                    if (step.Order == _originStepOrder)
                        return step;
            return null;
        }
    }

    // ── Cross-zone routing cache ──────────────────────────────────
    private ZoneLineEntry? _cachedZoneLine;
    private ZoneLineEntry? _pinnedZoneLine;
    private ZoneLineEntry? _chosenEntryLine;
    private Vector3 _lastCrossZoneCalcPos;
    private string? _navigationScene;
    private bool _cachedRouteLocked;
    private readonly UnroutableRoute _unroutableRoute = new();
    private const float CrossZoneRecalcDistance = 10f;
    private readonly List<ZoneLineAccess> _cachedHopAccess = new();
    private string? _cachedHopScene;
    private string? _cachedNextHopZoneKey;
    private ZoneLineEntry? _cachedEntryLine;
    private WaypointTargetState? _cachedWaypointTarget;

    private readonly struct WaypointTargetState
    {
        private readonly NavigationTarget.Kind _kind;
        private readonly Vector3 _position;
        private readonly string _scene;
        private readonly string? _source;
        private readonly string _quest;
        private readonly int _step;
        private readonly string _origin;
        private readonly int _originStep;

        public WaypointTargetState(NavigationTarget target)
        {
            _kind = target.TargetKind;
            _position = target.Position;
            _scene = target.Scene;
            _source = target.SourceId;
            _quest = target.QuestKey;
            _step = target.StepOrder;
            _origin = target.OriginQuestKey;
            _originStep = target.OriginStepOrder;
        }

        public bool Matches(NavigationTarget target) =>
            _kind == target.TargetKind
            && _position == target.Position
            && _step == target.StepOrder
            && _originStep == target.OriginStepOrder
            && string.Equals(_scene, target.Scene, StringComparison.OrdinalIgnoreCase)
            && string.Equals(_source, target.SourceId, StringComparison.OrdinalIgnoreCase)
            && string.Equals(_quest, target.QuestKey, StringComparison.OrdinalIgnoreCase)
            && string.Equals(_origin, target.OriginQuestKey, StringComparison.OrdinalIgnoreCase);
    }

    private readonly struct CrossZoneApproach
    {
        public string? NextHopZoneKey { get; }
        public ZoneLineEntry? EntryLine { get; }
        public ZoneLineEntry? FixedLine { get; }
        public bool IsLocked { get; }
        public bool PlacementUnreachable { get; }

        public CrossZoneApproach(
            string? nextHopZoneKey,
            ZoneLineEntry? entryLine,
            ZoneLineEntry? fixedLine,
            bool isLocked,
            bool placementUnreachable = false
        )
        {
            NextHopZoneKey = nextHopZoneKey;
            EntryLine = entryLine;
            FixedLine = fixedLine;
            IsLocked = isLocked;
            PlacementUnreachable = placementUnreachable;
        }
    }

    // ── Multi-source navigation state ─────────────────────────────
    // When navigating an item step, multiple sources may be active.
    // The controller picks the closest spawn among all active source
    // keys and points the arrow/path at it.

    /// <summary>All leaf sources for the current item step (for auto-mode recomputation).</summary>
    private List<Data.ItemSource> _allItemSources = new();
    private readonly Dictionary<string, PositionedSource> _positionedSources = new(
        System.StringComparer.OrdinalIgnoreCase
    );
    private readonly Dictionary<string, ItemSource> _canonicalSources = new(StringComparer.Ordinal);

    /// <summary>Source keys in the active navigation set.</summary>
    private readonly HashSet<string> _activeSourceKeys = new(
        System.StringComparer.OrdinalIgnoreCase
    );

    /// <summary>Item names the navigated quest still needs; refilled every frame.</summary>
    private readonly HashSet<string> _neededItems = new(System.StringComparer.OrdinalIgnoreCase);

    /// <summary>Which specific source key is currently closest (drives display name and live tracking).</summary>
    private string? _currentSourceKey;

    /// <summary>Origin identity for the current NavigateTo call chain.</summary>
    private string? _originQuestKey;
    private int _originStepOrder;
    private QuestStep? _resolvedStep;
    private bool _navigatingTreasure;
    private readonly TreasureHuntNavigation _treasureHunt = new();

    // ── Per-character config persistence ──────────────────────────
    private IConfigValue<string>? _navQuestEntry;
    private IConfigValue<int>? _navStepEntry;
    private int _boundSlotIndex = -1;

    /// <summary>Throttle for multi-source closest-spawn resolution.</summary>
    private float _sourceRescanTimer;
    private const float SourceRescanInterval = 0.25f;

    // Scratch path for reachability checks — avoids allocation per candidate
    private readonly NavMeshPath _scratchPath = new();

    /// <summary>Currently active navigation target, or null if not navigating.</summary>
    public NavigationTarget? Target { get; private set; }

    /// <summary>Distance from player to current target. Updated each frame via Update().</summary>
    public float Distance { get; private set; }

    /// <summary>World-space direction from player to target (normalized). Zero if no target.</summary>
    public Vector3 Direction { get; private set; }

    /// <summary>
    /// When navigating cross-zone, this holds the zone line we're routing through.
    /// Null when navigating within the current zone.
    /// </summary>
    public NavigationTarget? ZoneLineWaypoint { get; private set; }

    public NavigationController(
        GuideData data,
        EntityRegistry entities,
        QuestStateTracker state,
        SpawnTimerTracker timers,
        MiningNodeTracker miningTracker,
        LootScanner lootScanner
    )
    {
        _data = data;
        _entities = entities;
        _state = state;
        _countItem = state.CountItem;
        _timers = timers;
        _miningTracker = miningTracker;
        _lootScanner = lootScanner;
        _zoneGraph = new ZoneGraph(data, state.Gates);
        _requirements = new RequirementResolver(
            data,
            state.Gates,
            _zoneGraph,
            CurrentRequirementStep
        );
    }

    /// <summary>
    /// Start a new navigation session from a quest step. Records the
    /// quest+step as origin identity (for IsNavigating), then resolves
    /// through sub-quests and sets the navigation target.
    /// </summary>
    public bool NavigateTo(QuestStep step, QuestEntry quest, string currentScene)
    {
        _navigationOverride = null;
        _sourceSelection.Clear();
        _pinnedZoneLine = null;
        _treasureHunt.Drop();
        _originQuestKey = quest.RuntimeKey;
        _originStepOrder = step.Order;
        SavePerCharacter();
        return ResolveAndNavigate(step, quest, currentScene);
    }

    /// <summary>Choose one source without toggling the auto-selected source off.</summary>
    public bool NavigateToSource(
        ItemSource source,
        QuestStep step,
        QuestEntry quest,
        string currentScene
    )
    {
        if (!_sourceSelection.Select(source, step, quest))
            return false;
        _navigationOverride = null;
        _pinnedZoneLine = null;
        _treasureHunt.Drop();
        _originQuestKey = quest.RuntimeKey;
        _originStepOrder = step.Order;
        SavePerCharacter();
        return ResolveAndNavigate(step, quest, currentScene);
    }

    public bool NavigateToRequirementCharacter(
        string characterKey,
        string displayName,
        string currentScene
    )
    {
        var quest = OriginQuest;
        if (quest == null)
            return false;
        _navigationOverride = new QuestStep
        {
            Order = _originStepOrder,
            Action = "talk",
            Description = displayName,
            TargetType = "character",
            TargetKey = characterKey,
            TargetName = displayName,
        };
        return ResolveAndNavigate(_navigationOverride, quest, currentScene);
    }

    private QuestStep? CurrentRequirementStep(QuestEntry quest)
    {
        if (!NavigationResolutionPolicy.CanResolveQuest(_state.IsCompleted(quest)))
            return null;
        if (!_state.IsActionable(quest) && quest.Acquisition is { Count: > 0 })
        {
            if (quest.Steps != null)
                foreach (var step in quest.Steps)
                    if (StepProgress.IsAcquisitionStep(quest, step))
                        return step;
            if (_requirements.BuildAcquisitionStep(quest) is { } acquisition)
                return acquisition;
        }
        if (quest.Steps == null || quest.Steps.Count == 0)
            return null;
        int index = StepProgress.GetCurrentStepIndex(quest, _state, _data);
        return index >= 0 && index < quest.Steps.Count ? quest.Steps[index] : null;
    }

    /// <summary>
    /// Follow the live hunt for a step that lists treasure chests. Ordinary
    /// routing leads to the hunt's zone until the dig position is known.
    /// </summary>
    public bool NavigateToTreasureHunt(string questKey, int stepOrder)
    {
        if (!_state.TreasureHunt.State.Active)
            return false;
        _navigationOverride = null;
        _sourceSelection.Clear();
        _treasureHunt.Drop();
        _originQuestKey = questKey;
        _originStepOrder = stepOrder;
        SavePerCharacter();
        EngageTreasureHunt(questKey, stepOrder);
        return true;
    }

    /// <summary>Follow the live hunt; see <see cref="TreasureHuntNavigation"/>.</summary>
    internal void OnTreasureHuntChanged(TreasureHuntChange change)
    {
        string scene = _state.CurrentZone;
        switch (change)
        {
            case TreasureHuntChange.Started:
                if (_navigatingTreasure)
                {
                    RetargetTreasureHunt();
                    return;
                }
                // A step whose only sources are treasure chests leads to the hunt itself.
                if (_originQuestKey != null && ResolveOrigin(scene) && _navigatingTreasure)
                    return;
                _treasureHunt.Pause(_originQuestKey, _originStepOrder);
                _originQuestKey = null;
                _originStepOrder = 0;
                EngageTreasureHunt("", 0);
                return;
            case TreasureHuntChange.Updated:
                if (_navigatingTreasure)
                    RetargetTreasureHunt();
                return;
            case TreasureHuntChange.Ended:
                EndTreasureHunt(scene);
                return;
        }
    }

    private void EndTreasureHunt(string scene)
    {
        switch (_treasureHunt.OnEnded(_navigatingTreasure, _originQuestKey != null))
        {
            case TreasureHuntEndAction.RestorePaused:
                _treasureHunt.TryTakePaused(out var questKey, out int stepOrder);
                if (!TryNavigateToSaved(questKey, stepOrder, scene))
                    Clear();
                return;
            case TreasureHuntEndAction.ResolveSelection:
                if (!ResolveOrigin(scene))
                    ResetTargetState();
                return;
            case TreasureHuntEndAction.Clear:
                Clear();
                return;
            default:
                _treasureHunt.Drop();
                return;
        }
    }

    private void EngageTreasureHunt(string questKey, int stepOrder)
    {
        ResetTargetState();
        _navigatingTreasure = true;
        SetTreasureTarget(questKey, stepOrder);
    }

    private void RetargetTreasureHunt()
    {
        if (Target != null)
            SetTreasureTarget(Target.QuestKey, Target.StepOrder);
    }

    /// <summary>Resolve the selected step again, keeping it selected.</summary>
    private bool ResolveOrigin(string currentScene, bool preserveCrossZoneCache = false)
    {
        var quest = _originQuestKey != null ? _data.GetByRuntimeKey(_originQuestKey) : null;
        if (quest?.Steps == null)
            return false;
        if (_state.IsCompleted(quest))
        {
            Clear();
            return false;
        }
        int order = NavigationResolutionPolicy.SelectOriginStepOrder(
            quest.Steps,
            _originStepOrder,
            StepProgress.GetCurrentStepIndex(quest, _state, _data)
        );
        if (order <= 0)
        {
            Clear();
            return false;
        }
        SetOriginStepOrder(order);
        if (_navigationOverride != null)
            return ResolveAndNavigate(
                _navigationOverride,
                quest,
                currentScene,
                preserveCrossZoneCache
            );
        foreach (var step in quest.Steps)
        {
            if (step.Order == _originStepOrder)
                return ResolveAndNavigate(step, quest, currentScene, preserveCrossZoneCache);
        }
        return false;
    }

    private void SetOriginStepOrder(int order)
    {
        if (_originStepOrder == order)
            return;
        _originStepOrder = order;
        _navigationOverride = null;
        _sourceSelection.Clear();
        SavePerCharacter();
    }

    private void SetTreasureTarget(string questKey, int stepOrder)
    {
        var hunt = _state.TreasureHunt.State;
        InvalidateCrossZoneCache();
        Target = MakeTarget(
            hunt.HasLocation ? NavigationTarget.Kind.Position : NavigationTarget.Kind.Zone,
            new Vector3(hunt.X, hunt.Y, hunt.Z),
            TreasureHuntState.DisplayName,
            hunt.Scene,
            questKey,
            stepOrder,
            TreasureHuntState.SourceId
        );
    }

    internal static NavigationTarget CreateFixedPositionTarget(
        QuestStep step,
        QuestEntry quest,
        string originQuestKey,
        int originStepOrder
    )
    {
        var spec = NavigationPolicy.CreateFixedPositionTargetSpec(
            step,
            quest,
            originQuestKey,
            originStepOrder
        );
        return new NavigationTarget(
            NavigationTarget.Kind.Position,
            new Vector3(spec.X, spec.Y, spec.Z),
            spec.DisplayName,
            spec.Scene,
            spec.QuestKey,
            spec.StepOrder,
            spec.SourceId,
            spec.OriginQuestKey,
            spec.OriginStepOrder
        );
    }

    /// <summary>
    /// Resolve a step through sub-quests and set the navigation target.
    /// Does not change origin identity — used by both NavigateTo (after setting
    /// origin) and auto-advance (which preserves the existing origin).
    /// </summary>
    private bool ResolveAndNavigate(
        QuestStep step,
        QuestEntry quest,
        string currentScene,
        bool preserveCrossZoneCache = false
    )
    {
        var pinnedLine = _pinnedZoneLine;
        if (pinnedLine != null && !CanUseZoneLine(pinnedLine))
            pinnedLine = _pinnedZoneLine = null;
        _lastResolvedStateVersion = _state.Version;
        bool sameResolutionScene = string.Equals(
            _lastResolvedScene,
            currentScene,
            StringComparison.OrdinalIgnoreCase
        );
        _lastResolvedScene = currentScene;
        try
        {
            // A manual source must be resolved before automatic quest-reward unwrapping.
            var (activeStep, activeQuest) = _sourceSelection.IsFor(quest, step)
                ? (step, quest)
                : StepProgress.ResolveActiveStep(step, quest, _state, _data);
            var result = _sourceSelection.Resolve(
                _requirements,
                activeQuest ?? quest,
                activeStep ?? step,
                currentScene,
                pinnedLine
            );
            if (activeStep != null && !ReferenceEquals(activeStep, step) && result.Chain.Count > 0)
            {
                var chain = new List<RequirementLink>(result.Chain.Count + 1)
                {
                    new RequirementLink(step.TargetName ?? step.Description, Array.Empty<string>()),
                };
                chain.AddRange(result.Chain);
                result = new RequirementResolution(
                    result.Quest,
                    result.Step,
                    result.CanNavigate,
                    result.Message,
                    chain,
                    result.Advisories,
                    result.SelectedScene,
                    result.SelectedSpawn,
                    result.EntryLine,
                    result.AvailableSpawns
                );
            }
            bool sameOrigin =
                sameResolutionScene
                && Target != null
                && IsMatch(
                    Target.OriginQuestKey,
                    Target.OriginStepOrder,
                    _originQuestKey ?? quest.RuntimeKey,
                    _originStepOrder
                );
            if (
                preserveCrossZoneCache
                && NavigationResolutionPolicy.CanReuseEndpoint(
                    Requirements,
                    result,
                    sameOrigin,
                    ContainsItemUse(
                        ItemSourcePolicy.SourcesFor(activeQuest ?? quest, activeStep ?? step)
                    )
                )
            )
            {
                Requirements = result;
                _resolvedStep = result.Step;
                return true;
            }
            ResetTargetState(preserveCrossZoneCache);
            Requirements = result;
            if (!result.CanNavigate)
            {
                InvalidateCrossZoneCache();
                return false;
            }
            if (
                NavigationResolutionPolicy.SameStep(
                    result.Quest,
                    result.Step,
                    activeQuest ?? quest,
                    activeStep ?? step
                )
            )
                _pinnedZoneLine = pinnedLine;
            bool navigated = ResolveEndpoint(result.Step, result.Quest, currentScene);
            Requirements = navigated
                ? result
                : new RequirementResolution(
                    result.Quest,
                    result.Step,
                    false,
                    "No reachable navigation target for this requirement.",
                    result.Chain,
                    result.Advisories,
                    result.SelectedScene,
                    result.SelectedSpawn,
                    result.EntryLine,
                    result.AvailableSpawns
                );
            if (!navigated)
                InvalidateCrossZoneCache();
            return navigated;
        }
        catch (Exception error)
        {
            ResetTargetState();
            if (_reportedResolutionErrors.Add(quest.RuntimeKey))
                AdventureGuideLog.Current.LogError(
                    $"Cannot resolve navigation for {quest.DisplayName}",
                    error
                );
            Requirements = new RequirementResolution(
                quest,
                step,
                false,
                "Navigation requirements could not be resolved.",
                Array.Empty<RequirementLink>(),
                Array.Empty<GateAtom>()
            );
            return false;
        }
        finally
        {
            if (preserveCrossZoneCache)
                RevalidateCrossZoneCache(currentScene);
        }
    }

    private bool ResolveEndpoint(QuestStep step, QuestEntry quest, string currentScene)
    {
        if (step.Action == "complete_quest")
            return false;

        _resolvedStep = step;

        if (step.Location != null)
        {
            Target = CreateFixedPositionTarget(
                step,
                quest,
                _originQuestKey ?? quest.RuntimeKey,
                _originStepOrder
            );
            return true;
        }

        if (step.TargetKey == null)
            return false;

        if (
            step.TargetType == "character"
            && _state.Gates.IsCharacterAvailable(step.TargetKey)
            && (
                Requirements?.SelectedScene == null
                || string.Equals(
                    Requirements.SelectedScene,
                    currentScene,
                    StringComparison.OrdinalIgnoreCase
                )
            )
        )
        {
            var playerPos = GetPlayerPosition();
            if (playerPos.HasValue)
            {
                var liveNpc = _entities.FindClosest(step.TargetKey, playerPos.Value);
                if (liveNpc != null)
                {
                    Target = MakeTarget(
                        NavigationTarget.Kind.Character,
                        liveNpc.transform.position,
                        WithCharacterUnlockText(
                            step.TargetName ?? step.Description,
                            step.TargetKey
                        ),
                        currentScene,
                        quest.RuntimeKey,
                        step.Order,
                        step.TargetKey
                    );
                    return true;
                }
            }
        }

        return step.TargetType switch
        {
            "character" => ResolveCharacterTarget(step, quest, currentScene),
            "zone" => ResolveZoneTarget(step, quest, currentScene),
            "item" => ResolveItemTarget(step, quest, currentScene),
            _ => false,
        };
    }

    /// <summary>Pin a specific zone line for cross-zone routing, overriding auto-selection.</summary>
    public void PinZoneLine(ZoneLineEntry zoneLine)
    {
        if (!CanUseZoneLine(zoneLine))
            return;
        _pinnedZoneLine = zoneLine;
        InvalidateCrossZoneCache();
        if (OriginQuest is { } origin)
            RefreshResolvedStep(origin, _state.CurrentZone);
        else
            InvalidateCrossZoneCache();
    }

    /// <summary>End the navigation session entirely.</summary>
    public void Clear()
    {
        _treasureHunt.Drop();
        _sourceSelection.Clear();
        ResetTargetState();
        _navigationOverride = null;
        _originQuestKey = null;
        _originStepOrder = 0;
        SavePerCharacter();
    }

    /// <summary>Hide navigation without erasing the outgoing character's save.</summary>
    public void SuspendForMenu()
    {
        SavePerCharacter();
        _treasureHunt.Drop();
        ResetTargetState();
        _navigationOverride = null;
        _originQuestKey = null;
        _originStepOrder = 0;
        _navQuestEntry = null;
        _navStepEntry = null;
        _boundSlotIndex = -1;
    }

    // ── Per-character persistence ─────────────────────────────────

    /// <summary>
    /// Bind per-character config entries and restore the saved navigation
    /// target (if any). Call after character login. On zone transitions for
    /// the same character, the in-memory state is authoritative.
    /// </summary>
    public void LoadPerCharacter(GuideConfig config, string currentScene)
    {
        if (
            !NavigationPolicy.ShouldLoadCharacter(
                currentScene,
                _boundSlotIndex,
                GameData.CurrentCharacterSlot?.index
            )
        )
            return;
        var slot = GameData.CurrentCharacterSlot;
        if (slot == null)
            return;

        // Switching characters: save outgoing state before rebinding
        SavePerCharacter();
        _treasureHunt.Drop();
        ResetTargetState();
        _originQuestKey = null;
        _originStepOrder = 0;

        _boundSlotIndex = slot.index;
        _navQuestEntry = config.BindPerCharacter(slot.index, CharacterSlotState.NavQuest);
        _navStepEntry = config.BindPerCharacter(slot.index, CharacterSlotState.NavStep);
        TryNavigateToSaved(_navQuestEntry.Value, _navStepEntry.Value, currentScene);
    }

    /// <summary>
    /// Navigate to a saved quest step. Returns false when it can no longer be
    /// followed: no step saved, or its quest is gone or completed.
    /// </summary>
    private bool TryNavigateToSaved(string? questKey, int stepOrder, string currentScene)
    {
        if (string.IsNullOrEmpty(questKey) || stepOrder <= 0)
            return false;
        var quest = _data.GetByRuntimeKey(questKey!);
        if (quest?.Steps == null || _state.IsCompleted(quest))
            return false;
        foreach (var step in quest.Steps)
        {
            if (step.Order == stepOrder)
            {
                NavigateTo(step, quest, currentScene);
                return true;
            }
        }
        return false;
    }

    /// <summary>
    /// Write the selected step to the per-character config, or the step a
    /// treasure hunt paused. Called on mod destroy and before character switch.
    /// </summary>
    public void SavePerCharacter()
    {
        if (_navQuestEntry == null)
            return;
        var (questKey, stepOrder) = _treasureHunt.Saved(_originQuestKey, _originStepOrder);
        _navQuestEntry.Value = questKey;
        _navStepEntry!.Value = stepOrder;
    }

    /// <summary>
    /// Clear target and rendering state without ending the session.
    /// Preserves origin identity so auto-advance and source changes
    /// keep the parent quest's NAV button highlighted.
    /// </summary>
    private void ResetTargetState(bool preserveCrossZoneCache = false)
    {
        Target = null;
        Requirements = null;
        SetSelectedSource(null);
        if (!preserveCrossZoneCache)
            InvalidateCrossZoneCache();
        _pinnedZoneLine = null;
        _activeSourceKeys.Clear();
        _allItemSources.Clear();
        _positionedSources.Clear();
        _canonicalSources.Clear();
        _currentSourceKey = null;
        _sourceRescanTimer = 0f;
        Distance = 0f;
        Direction = Vector3.zero;
        _navigatingTreasure = false;
    }

    private void InvalidateCrossZoneCache()
    {
        _cachedZoneLine = null;
        _chosenEntryLine = null;
        _lastCrossZoneCalcPos = Vector3.zero;
        ZoneLineWaypoint = null;
        _unroutableRoute.Clear();
        _cachedHopAccess.Clear();
        _cachedHopScene = null;
        _cachedNextHopZoneKey = null;
        _cachedEntryLine = null;
        _cachedWaypointTarget = null;
    }

    private bool ObserveScene(string currentScene)
    {
        if (!CrossZoneWaypointPolicy.SceneChanged(_navigationScene, currentScene))
            return false;
        _navigationScene = currentScene;
        _zoneGraph.Rebuild();
        InvalidateCrossZoneCache();
        ReResolveForScene(currentScene);
        return true;
    }

    private void ReResolveForScene(string currentScene)
    {
        if (OriginQuest is { } origin && !_navigatingTreasure)
            RefreshResolvedStep(origin, currentScene);
    }

    /// <summary>Whether navigation retains an explicit source choice.</summary>
    public bool IsManualSourceOverride => _sourceSelection.IsActive;

    /// <summary>
    /// Navigate to a zone by scene name. Used for sources that have a zone
    /// but no specific coordinates (e.g. fishing). When the player is already
    /// in the target zone, sets a same-zone Zone target so IsNavigating returns
    /// true (UI highlights the step) but arrow/path stay hidden.
    /// </summary>
    public bool NavigateToZone(
        string scene,
        string displayName,
        string sourceId,
        string questDBName,
        int stepOrder,
        string currentScene
    )
    {
        ResetTargetState();

        // Same zone: set a Zone target so UI shows this step as active.
        // Update() handles this by setting distance=0, direction=zero.
        if (string.Equals(scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
        {
            Target = MakeTarget(
                NavigationTarget.Kind.Zone,
                Vector3.zero,
                displayName,
                scene,
                questDBName,
                stepOrder,
                sourceId
            );
            return true;
        }

        var zoneKey = FindZoneKeyBySceneName(scene);
        if (zoneKey == null)
            return false;

        Target = MakeTarget(
            NavigationTarget.Kind.Zone,
            Vector3.zero,
            displayName,
            scene,
            questDBName,
            stepOrder,
            sourceId
        );
        return true;
    }

    /// <summary>
    /// Called when game state changes (quest assigned, quest completed,
    /// inventory changed, NPC killed). Re-evaluates whether the current
    /// nav step is still the active step and auto-advances if not.
    /// </summary>
    public void OnGameStateChanged(string currentScene)
    {
        if (ObserveScene(currentScene))
            return;
        _zoneGraph.Rebuild();
        if (_navigatingTreasure)
        {
            RevalidateCrossZoneCache(currentScene);
            return;
        }
        if (
            Requirements != null
            && (
                Requirements.Chain.Count > 1
                || !Requirements.CanNavigate
                || _navigationOverride != null
            )
        )
        {
            var original = OriginQuest;
            if (original != null && _state.IsCompleted(original))
                Clear();
            else
                ResolveOrigin(currentScene, preserveCrossZoneCache: true);
            return;
        }
        if (Target == null)
        {
            if (_originQuestKey != null)
                ResolveOrigin(currentScene, preserveCrossZoneCache: true);
            return;
        }

        var quest = _data.GetByRuntimeKey(Target.QuestKey);
        if (quest?.Steps == null)
        {
            Clear();
            return;
        }

        var origin = _originQuestKey != null ? _data.GetByRuntimeKey(_originQuestKey) : null;
        var completion = NavigationCompletionPolicy.Decide(
            origin != null && _state.IsCompleted(origin),
            _state.IsCompleted(quest),
            origin != null && origin.RuntimeKey != quest.RuntimeKey
        );
        if (completion == NavigationCompletionAction.Clear)
        {
            Clear();
            return;
        }
        if (completion == NavigationCompletionAction.ResolveOrigin)
        {
            RefreshResolvedStep(origin!, currentScene);
            return;
        }

        if (
            _resolvedStep?.TargetType == "item"
            && ContainsItemUse(ItemSourcePolicy.SourcesFor(quest, _resolvedStep))
        )
        {
            RefreshResolvedStep(quest, currentScene);
            return;
        }
        // Determine which step the player is currently on
        int currentStepIdx = StepProgress.GetCurrentStepIndex(quest, _state, _data);

        // Find the index of the step we're navigating
        int navStepIdx = -1;
        for (int i = 0; i < quest.Steps.Count; i++)
        {
            if (quest.Steps[i].Order == Target.StepOrder)
            {
                navStepIdx = i;
                break;
            }
        }

        // Nav step is still the current step or ahead of it
        if (navStepIdx < 0 || navStepIdx >= currentStepIdx)
        {
            RefreshResolvedStep(quest, currentScene);
            return;
        }

        // Nav step is behind current step — advance to the first navigable
        // step at or after the current step index
        for (int i = currentStepIdx; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.TargetKey != null)
            {
                if (
                    string.Equals(
                        quest.RuntimeKey,
                        _originQuestKey,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                    SetOriginStepOrder(step.Order);
                ResolveAndNavigate(step, quest, currentScene, preserveCrossZoneCache: true);
                return;
            }
        }

        // No more navigable steps
        Clear();
    }

    private void RefreshResolvedStep(QuestEntry quest, string currentScene)
    {
        quest = OriginQuest ?? quest;
        var step = OriginStep ?? _resolvedStep;
        if (step == null)
            return;
        if (_originQuestKey != null)
            ResolveOrigin(currentScene, preserveCrossZoneCache: true);
        else
            ResolveAndNavigate(step, quest, currentScene, preserveCrossZoneCache: true);
    }

    /// <summary>Refresh sources, target requirements, and route gates when room contents change.</summary>
    public void OnFurnishingsChanged(string currentScene)
    {
        _zoneGraph.Rebuild();
        if (!_navigatingTreasure && OriginQuest is { } origin)
            RefreshResolvedStep(origin, currentScene);
        else
            RevalidateCrossZoneCache(currentScene);
    }

    /// <summary>
    /// Call each frame. Updates distance/direction to the active target.
    /// Upgrades to live NPC position when one becomes available.
    /// Routes through zone lines for cross-zone targets.
    /// </summary>
    public void Update(string currentScene)
    {
        ObserveScene(currentScene);
        if (Target == null)
            return;

        var playerPos = GetPlayerPosition();
        if (!playerPos.HasValue)
            return;

        // Cross-zone: navigate to zone line instead of target directly
        if (Target.IsCrossZone(currentScene))
        {
            UpdateCrossZoneRouting(currentScene, playerPos.Value);
            return;
        }

        if (ZoneLineWaypoint != null || _cachedZoneLine != null)
            InvalidateCrossZoneCache();

        // Same-zone Zone target (e.g. fishing): player is already in the
        // right zone. Keep Target alive so IsNavigating returns true (UI
        // highlights), but set distance/direction to zero so arrow hides.
        if (Target.TargetKind == NavigationTarget.Kind.Zone)
        {
            Distance = 0f;
            Direction = Vector3.zero;
            return;
        }

        // Same zone: update position from closest match
        // Priority: corpse/chest with quest loot > alive NPC > shortest respawn
        if (Target.TargetKind == NavigationTarget.Kind.Character || _activeSourceKeys.Count > 0)
        {
            var neededItems = BuildNeededItems(Target.QuestKey);
            var corpse =
                neededItems.Count > 0
                    ? _lootScanner.FindClosestWithAnyItem(neededItems, playerPos.Value)
                    : null;

            if (corpse.HasValue)
            {
                Target.Position = corpse.Value.Position;
            }
            else if (_activeSourceKeys.Count > 0)
            {
                // Multi-source: periodically re-resolve closest among all
                // active sources, then track the winner's NPC each frame.
                _sourceRescanTimer += UnityEngine.Time.deltaTime;
                if (_sourceRescanTimer >= SourceRescanInterval)
                {
                    _sourceRescanTimer = 0f;
                    UpdateClosestActiveSource(currentScene);
                    if (Target == null)
                        return;
                    if (Target.IsCrossZone(currentScene))
                    {
                        UpdateCrossZoneRouting(currentScene, playerPos.Value);
                        return;
                    }
                }
                // Per-frame: track the current winner's live position
                TrackCurrentSourcePosition(playerPos.Value);
            }
            else
            {
                var liveNpc = _entities.FindClosest(Target.SourceId, playerPos.Value);
                if (liveNpc != null)
                    Target.Position = liveNpc.transform.position;
                else
                {
                    var bestRespawn = FindShortestRespawnPosition(Target.SourceId);
                    if (bestRespawn.HasValue)
                        Target.Position = bestRespawn.Value;
                }
            }
        }

        UpdateDistanceAndDirection(Target.Position, playerPos.Value);
    }

    /// <summary>
    /// Check if the given quest+step is the current navigation target.
    /// Matches against both the resolved target AND the originating quest
    /// so that parent quests and sub-quests both show as active.
    /// </summary>
    public bool IsNavigating(string questKey, int stepOrder) =>
        (
            _originQuestKey != null
            && Requirements != null
            && IsMatch(_originQuestKey, _originStepOrder, questKey, stepOrder)
        )
        || (
            Target != null
            && (
                IsMatch(Target.QuestKey, Target.StepOrder, questKey, stepOrder)
                || IsMatch(Target.OriginQuestKey, Target.OriginStepOrder, questKey, stepOrder)
            )
        );

    private static bool IsMatch(string aQuest, int aStep, string bQuest, int bStep) =>
        string.Equals(aQuest, bQuest, System.StringComparison.OrdinalIgnoreCase) && aStep == bStep;

    /// <summary>
    /// Get all zone lines from the current scene to the navigation target's zone.
    /// Returns empty if not cross-zone navigating or no zone lines found.
    /// </summary>
    public List<(
        ZoneLineEntry line,
        float distance,
        bool isActive,
        bool isAccessible
    )> GetAlternativeZoneLines(string currentScene)
    {
        var result =
            new List<(ZoneLineEntry line, float distance, bool isActive, bool isAccessible)>();
        if (Target == null || !Target.IsCrossZone(currentScene))
            return result;

        var playerPos = GetPlayerPosition() ?? Vector3.zero;
        var targetZoneKey = FindZoneKeyBySceneName(Target.Scene);
        if (targetZoneKey == null)
            return result;

        if (
            ChosenEntryLine is { } entry
            && string.Equals(entry.Scene, currentScene, StringComparison.OrdinalIgnoreCase)
        )
        {
            if (CanUseZoneLine(entry))
                result.Add(
                    (
                        entry,
                        Vector3.Distance(playerPos, new Vector3(entry.X, entry.Y, entry.Z)),
                        true,
                        IsZoneLineAccessible(entry)
                    )
                );
            return result;
        }
        foreach (var zl in _data.ZoneLines)
        {
            if (!CanUseZoneLine(zl))
                continue;
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (
                !string.Equals(
                    ResolveDestination(zl)?.ZoneKey,
                    targetZoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                continue;

            var zlPos = new Vector3(zl.X, zl.Y, zl.Z);
            float dist = Vector3.Distance(playerPos, zlPos);
            var activeZl = _pinnedZoneLine ?? _cachedZoneLine;
            bool selected =
                activeZl != null && zl.X == activeZl.X && zl.Y == activeZl.Y && zl.Z == activeZl.Z;
            bool accessible = IsZoneLineAccessible(zl);
            result.Add((zl, dist, selected, accessible));
        }

        // Accessible first, then by distance within each group
        result.Sort(
            (a, b) =>
            {
                int cmp = b.isAccessible.CompareTo(a.isAccessible);
                return cmp != 0 ? cmp : a.distance.CompareTo(b.distance);
            }
        );
        return result;
    }

    /// <summary>Re-pick live sources without rebuilding unchanged requirement guidance.</summary>
    private void UpdateClosestActiveSource(string currentScene)
    {
        if (
            NavigationResolutionPolicy.ShouldResolveRequirements(
                _state.Version,
                _lastResolvedStateVersion
            ) && OriginQuest is { } origin
        )
            RefreshResolvedStep(origin, currentScene);
        if (Target == null || _resolvedStep == null)
            return;
        var quest = _data.GetByRuntimeKey(Target.QuestKey);
        if (quest != null)
            ResolveClosestActiveSource(
                quest,
                _resolvedStep,
                currentScene,
                preferLiveCharacters: true
            );
    }

    /// <summary>
    /// Per-frame: track the current winner's live NPC position for smooth arrow movement.
    /// </summary>
    private void TrackCurrentSourcePosition(Vector3 playerPos)
    {
        if (_currentSourceKey == null || _positionedSources.ContainsKey(_currentSourceKey))
            return;

        var liveNpc = _entities.FindClosest(_currentSourceKey, playerPos);
        if (liveNpc != null)
            Target!.Position = liveNpc.transform.position;
        else
        {
            var bestRespawn = FindShortestRespawnPosition(_currentSourceKey);
            if (bestRespawn.HasValue)
                Target!.Position = bestRespawn.Value;
        }
    }

    private Vector3? FindShortestRespawnPosition(string? stableKey)
    {
        if (stableKey == null)
            return null;

        // Check dead enemy spawns
        var bestPoint = _timers.FindSoonestRespawn(_entities.RuntimeIdentity(stableKey));
        return bestPoint != null ? bestPoint.transform.position : null;
    }

    // ── Target resolution ──────────────────────────────────────────

    private bool ResolveCharacterTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        if (
            !_data.CharacterSpawns.TryGetValue(step.TargetKey!, out var spawns)
            || spawns.Count == 0
        )
            return false;

        var spawn = PickBestSpawn(spawns, currentScene);
        if (spawn == null)
            return false;
        Target = MakeTarget(
            NavigationTarget.Kind.Character,
            new Vector3(spawn.X, spawn.Y, spawn.Z),
            WithCharacterUnlockText(step.TargetName ?? step.Description, step.TargetKey),
            spawn.Scene,
            quest.RuntimeKey,
            step.Order,
            step.TargetKey
        );
        return true;
    }

    private bool ResolveZoneTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        // Resolve zone key from target_key or display name
        string? destZoneKey = step.TargetKey;
        if (
            destZoneKey != null
            && !_data.ZoneLookup.Values.Any(z =>
                string.Equals(z.StableKey, destZoneKey, System.StringComparison.OrdinalIgnoreCase)
            )
        )
        {
            destZoneKey = FindZoneKeyByDisplayName(step.TargetName);
        }

        if (destZoneKey == null)
            return false;

        // Find the scene name for this zone
        string? destScene = null;
        foreach (var kvp in _data.ZoneLookup)
        {
            if (
                string.Equals(
                    kvp.Value.StableKey,
                    destZoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                destScene = kvp.Key;
                break;
            }
        }

        if (destScene == null)
            return false;

        // The destination remains authoritative after arrival; zone lines are
        // only intermediate waypoints, including for adjacent destinations.
        Target = MakeTarget(
            NavigationTarget.Kind.Zone,
            Vector3.zero,
            step.TargetName ?? destScene,
            destScene,
            quest.RuntimeKey,
            step.Order
        );
        return true;
    }

    private bool ResolveItemTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        // For collect/read steps: build the active source set and navigate
        // to the closest spawn among all active sources.
        var sources = ItemSourcePolicy.SourcesFor(quest, step);

        if (sources == null || sources.Count == 0)
            return false;

        // Collect all leaf sources with spawn data
        _allItemSources.Clear();
        _canonicalSources.Clear();
        _positionedSources.Clear();
        CollectLeafSources(sources, _allItemSources);

        if (_allItemSources.Count == 0)
        {
            if (_state.TreasureHunt.State.Active && ContainsTreasureChest(sources))
            {
                EngageTreasureHunt(quest.RuntimeKey, step.Order);
                return true;
            }
            // No sources with spawn data — fallback to zone navigation
            return ResolveItemZoneFallback(sources, quest, step, currentScene);
        }

        ComputeAutoSourceSet(currentScene);

        // Resolve initial target from the active set
        return ResolveClosestActiveSource(quest, step, currentScene);
    }

    private static bool ContainsItemUse(List<ItemSource>? sources)
    {
        if (sources == null)
            return false;
        foreach (var source in sources)
            if (source.Type == "item_use" || ContainsItemUse(source.Children))
                return true;
        return false;
    }

    private static bool ContainsTreasureChest(List<ItemSource> sources)
    {
        foreach (var source in sources)
            if (
                source.Type == "treasure_chest"
                || (source.Children != null && ContainsTreasureChest(source.Children))
            )
                return true;
        return false;
    }

    /// <summary>
    /// Recursively collect all leaf sources that have spawn data.
    /// quest_reward sources always recurse into children (the source key
    /// points to the quest giver NPC, not the actual drop sources).
    /// </summary>
    private void CollectLeafSources(List<Data.ItemSource> sources, List<Data.ItemSource> result)
    {
        foreach (var src in sources)
        {
            if (!_state.Gates.IsSourceAvailable(src))
                continue;
            if (
                ItemSourcePolicy.IsRandomSource(src)
                || !ItemSourcePolicy.NeedsUsedItem(src, _countItem, sources)
            )
                continue;
            // quest_reward: the SourceKey is the quest giver NPC, not a
            // drop source. Always recurse into children for the actual
            // obtainable sources (e.g., Seaspice drops under Percy's Seaspice).
            if (
                !ItemSourcePolicy.IsStaticCandidate(src)
                || ItemSourcePolicy.HasPendingChildren(src, _countItem)
            )
            {
                if (src.Children != null)
                    CollectLeafSources(src.Children, result);
                continue;
            }

            if (src.AcquisitionKey != null)
            {
                var identity = src.MakeSourceId();
                if (identity != null && PositionedSource.TryCreate(src, out var canonicalPosition))
                {
                    result.Add(src);
                    _canonicalSources[identity] = src;
                    _positionedSources[identity] = canonicalPosition;
                }
                continue;
            }

            if (src.SourceKey == null)
            {
                if (src.Children != null)
                    CollectLeafSources(src.Children, result);
                continue;
            }

            if (PositionedSource.TryParse(src.SourceKey, out var positioned))
            {
                result.Add(src);
                _positionedSources[src.SourceKey] = positioned;
            }
            else if (
                _data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns)
                && spawns.Count > 0
            )
            {
                result.Add(src);
            }
            else if (src.Children != null)
            {
                CollectLeafSources(src.Children, result);
            }
        }
    }

    /// <summary>
    /// Compute the auto source set based on zone preference.
    /// In-zone sources take priority; falls back to lowest-level cross-zone source.
    /// </summary>
    private void ComputeAutoSourceSet(string currentScene)
    {
        _activeSourceKeys.Clear();

        // Find all sources with spawns/presence in the current zone
        foreach (var src in _allItemSources)
        {
            var sourceId = src.MakeSourceId();
            if (sourceId == null || !_state.Gates.IsSourceAvailable(src))
                continue;

            if (_positionedSources.TryGetValue(sourceId, out var positioned))
            {
                if (
                    string.Equals(
                        positioned.Scene,
                        currentScene,
                        System.StringComparison.OrdinalIgnoreCase
                    )
                )
                    _activeSourceKeys.Add(sourceId);
                continue;
            }

            if (
                src.SourceKey == null
                || !_data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns)
            )
                continue;
            if (
                spawns.Exists(s =>
                    string.Equals(s.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase)
                    && IsSelectedSpawnAvailable(s)
                )
            )
                _activeSourceKeys.Add(sourceId);
        }

        // If no in-zone sources, pick the lowest-level source (first in list —
        // pipeline sorts by level ascending)
        if (_activeSourceKeys.Count == 0 && _allItemSources.Count > 0)
        {
            var fallback = _allItemSources[0];
            var sourceId = fallback.MakeSourceId();
            if (sourceId != null)
                _activeSourceKeys.Add(sourceId);
        }
    }

    /// <summary>
    /// Resolve the closest spawn among all active source keys and set as Target.
    /// Used both for initial target creation and periodic re-evaluation.
    /// </summary>
    private bool ResolveClosestActiveSource(
        QuestEntry quest,
        QuestStep step,
        string currentScene,
        bool preferLiveCharacters = false
    )
    {
        var playerPos = GetPlayerPosition() ?? Vector3.zero;
        string? bestScene = null;
        Vector3 bestPosition = Vector3.zero;
        string? bestSourceKey = null;
        float bestDistance = float.MaxValue;
        float bestRespawn = float.MaxValue;
        bool bestMined = true;
        var bestKind = NavigationTarget.Kind.Character;
        string? zoneWideKey = null;

        foreach (var sourceKey in _activeSourceKeys)
        {
            if (_positionedSources.TryGetValue(sourceKey, out var positioned))
            {
                if (
                    !string.Equals(
                        positioned.Scene,
                        currentScene,
                        System.StringComparison.OrdinalIgnoreCase
                    )
                )
                    continue;
                // Fishing has no destination; it is decided after the loop.
                if (positioned.IsZoneWide)
                {
                    zoneWideKey ??= sourceKey;
                    continue;
                }
                var position = new Vector3(positioned.X, positioned.Y, positioned.Z);
                var node =
                    positioned.Kind == "mining" ? _miningTracker.FindAtPosition(position) : null;
                bool mined = node != null && MiningNodeTracker.IsMined(node);
                float respawn =
                    node != null
                        ? MiningNodeTracker.GetRemainingSeconds(node) ?? float.MaxValue
                        : float.MaxValue;
                if (node != null)
                    position = node.transform.position;
                float distance = (position - playerPos).sqrMagnitude;
                if (
                    bestScene == null
                    || SourceSelectionPolicy.IsBetter(
                        mined,
                        distance,
                        respawn,
                        bestMined,
                        bestDistance,
                        bestRespawn
                    )
                )
                {
                    bestScene = currentScene;
                    bestPosition = position;
                    bestSourceKey = sourceKey;
                    bestDistance = distance;
                    bestRespawn = respawn;
                    bestMined = mined;
                    bestKind = NavigationTarget.Kind.Position;
                }
                continue;
            }

            if (!_data.CharacterSpawns.TryGetValue(sourceKey, out var spawns))
                continue;
            var npc = preferLiveCharacters ? _entities.FindClosest(sourceKey, playerPos) : null;
            if (!SourceSelectionPolicy.ShouldConsiderCharacter(preferLiveCharacters, npc != null))
                continue;
            foreach (var spawn in spawns)
            {
                if (
                    !string.Equals(
                        spawn.Scene,
                        currentScene,
                        System.StringComparison.OrdinalIgnoreCase
                    ) || !IsSelectedSpawnAvailable(spawn)
                )
                    continue;
                var position =
                    npc != null ? npc.transform.position : new Vector3(spawn.X, spawn.Y, spawn.Z);
                float distance = (position - playerPos).sqrMagnitude;
                if (
                    bestScene == null
                    || SourceSelectionPolicy.IsBetter(
                        false,
                        distance,
                        0f,
                        bestMined,
                        bestDistance,
                        bestRespawn
                    )
                )
                {
                    bestScene = currentScene;
                    bestPosition = position;
                    bestSourceKey = sourceKey;
                    bestDistance = distance;
                    bestMined = false;
                    bestKind = NavigationTarget.Kind.Character;
                }
            }
        }

        // Fishing here wins, as the tracker ranks it ("available right
        // here"): the zone itself is the target, so the step shows as
        // navigated without an arrow.
        if (zoneWideKey != null)
        {
            bestScene = currentScene;
            bestPosition = Vector3.zero;
            bestSourceKey = zoneWideKey;
            bestKind = NavigationTarget.Kind.Zone;
        }
        // If no source is currently alive, retain the existing character
        // winner so per-frame tracking can use that character's respawn.
        else if (bestScene == null && preferLiveCharacters)
            return Target != null;

        if (bestScene == null)
        {
            // No source in this scene: pick the source in the closest
            // reachable scene, not just the first in the guide's order.
            bool bestRoutable = false,
                bestLocked = false;
            int bestHops = int.MaxValue;
            var routes = new Dictionary<string, ZoneGraph.Route?>(
                System.StringComparer.OrdinalIgnoreCase
            );

            void Consider(string scene, Vector3 position, NavigationTarget.Kind kind, string key)
            {
                if (!routes.TryGetValue(scene, out var route))
                {
                    route = _zoneGraph.FindRoute(currentScene, scene);
                    routes[scene] = route;
                }
                bool routable = route != null;
                bool locked = route != null && route.IsLocked;
                int hops = route != null ? route.Path.Count - 1 : int.MaxValue;
                if (
                    bestScene != null
                    && !SourceSelectionPolicy.IsBetterCrossZone(
                        routable,
                        locked,
                        hops,
                        bestRoutable,
                        bestLocked,
                        bestHops
                    )
                )
                    return;
                bestScene = scene;
                bestPosition = position;
                bestKind = kind;
                bestSourceKey = key;
                bestRoutable = routable;
                bestLocked = locked;
                bestHops = hops;
            }

            foreach (var sourceKey in _activeSourceKeys)
            {
                if (_positionedSources.TryGetValue(sourceKey, out var positioned))
                {
                    Consider(
                        positioned.Scene,
                        positioned.IsZoneWide
                            ? Vector3.zero
                            : new Vector3(positioned.X, positioned.Y, positioned.Z),
                        positioned.IsZoneWide
                            ? NavigationTarget.Kind.Zone
                            : NavigationTarget.Kind.Position,
                        sourceKey
                    );
                }
                else if (_data.CharacterSpawns.TryGetValue(sourceKey, out var spawns))
                {
                    foreach (var spawn in spawns)
                    {
                        if (IsSelectedSpawnAvailable(spawn))
                            Consider(
                                spawn.Scene,
                                new Vector3(spawn.X, spawn.Y, spawn.Z),
                                NavigationTarget.Kind.Character,
                                sourceKey
                            );
                    }
                }
            }
        }
        if (bestScene == null)
            return false;

        _currentSourceKey = bestSourceKey;
        string displayName = bestSourceKey ?? step.TargetName ?? step.Description;
        ItemSource? selectedSource = null;
        foreach (var source in _allItemSources)
            if (
                string.Equals(
                    source.MakeSourceId(),
                    bestSourceKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                displayName = source.Name ?? displayName;
                selectedSource = source;
                break;
            }
        SetSelectedSource(selectedSource);
        if (Target != null && Target.SourceId == bestSourceKey && Target.TargetKind == bestKind)
        {
            Target.Position = bestPosition;
            Target.Scene = bestScene;
        }
        else
        {
            displayName = WithCharacterUnlockText(displayName, bestSourceKey);
            Target = MakeTarget(
                bestKind,
                bestPosition,
                displayName,
                bestScene,
                quest.RuntimeKey,
                step.Order,
                bestSourceKey
            );
        }
        return true;
    }

    /// <summary>Zone-only fallback for items without spawn data (fishing, etc.).</summary>
    private bool ResolveItemZoneFallback(
        List<Data.ItemSource> sources,
        QuestEntry quest,
        QuestStep step,
        string currentScene
    )
    {
        var firstSource = FindFirstSourceWithScene(sources);
        var firstScene = firstSource == null ? null : ItemSourcePolicy.SceneOf(firstSource);
        string? zoneKey = firstScene != null ? FindZoneKeyBySceneName(firstScene) : null;
        if (zoneKey == null)
            return false;

        string? destScene = null;
        foreach (var kvp in _data.ZoneLookup)
        {
            if (
                string.Equals(
                    kvp.Value.StableKey,
                    zoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                destScene = kvp.Key;
                break;
            }
        }
        if (destScene == null)
            return false;

        string displayName = firstSource?.Zone ?? destScene;
        string? sourceId = firstSource?.MakeSourceId();
        bool navigated = NavigateToZone(
            destScene,
            displayName,
            sourceId!,
            quest.RuntimeKey,
            step.Order,
            currentScene
        );
        SetSelectedSource(navigated ? firstSource : null);
        return navigated;
    }

    // ── Cross-zone routing ─────────────────────────────────────────

    private CrossZoneApproach GetCrossZoneApproach(string currentScene)
    {
        if (Target == null)
            return default;
        var spawn = FindTargetPlacement();
        var placement = spawn == null ? null : _zoneGraph.GetPlacementRoute(spawn, currentScene);
        if (spawn != null && !placement.HasValue)
            return new CrossZoneApproach(null, null, null, false, placementUnreachable: true);
        var entry = placement?.EntryLine;
        if (
            entry != null
            && string.Equals(entry.Scene, currentScene, StringComparison.OrdinalIgnoreCase)
        )
            return new CrossZoneApproach(
                ResolveDestination(entry)?.ZoneKey,
                entry,
                entry,
                !IsZoneLineAccessible(entry)
            );
        if (
            _pinnedZoneLine != null
            && CanUseZoneLine(_pinnedZoneLine)
            && string.Equals(
                _pinnedZoneLine.Scene,
                currentScene,
                StringComparison.OrdinalIgnoreCase
            )
            && (
                entry == null
                || ResolveDestination(_pinnedZoneLine)?.ZoneKey == placement?.Route?.NextHopZoneKey
            )
        )
            return new CrossZoneApproach(
                ResolveDestination(_pinnedZoneLine)?.ZoneKey,
                entry,
                _pinnedZoneLine,
                !IsZoneLineAccessible(_pinnedZoneLine)
            );
        var route = placement.HasValue
            ? placement.Value.Route
            : _zoneGraph.FindRoute(currentScene, Target.Scene);
        return new CrossZoneApproach(route?.NextHopZoneKey, entry, null, route?.IsLocked ?? false);
    }

    private void CaptureCrossZoneCache(string currentScene, CrossZoneApproach approach)
    {
        _cachedWaypointTarget = Target == null ? null : new WaypointTargetState(Target);
        _cachedHopScene = currentScene;
        _cachedNextHopZoneKey = approach.NextHopZoneKey;
        _cachedEntryLine = approach.EntryLine;
        _cachedHopAccess.Clear();
        foreach (var line in _data.ZoneLines)
            if (
                string.Equals(line.Scene, currentScene, StringComparison.OrdinalIgnoreCase)
                && string.Equals(
                    ResolveDestination(line)?.ZoneKey,
                    approach.NextHopZoneKey,
                    StringComparison.OrdinalIgnoreCase
                )
            )
                _cachedHopAccess.Add(new ZoneLineAccess(line, _state.Gates));
    }

    private void RevalidateCrossZoneCache(string currentScene)
    {
        if (_cachedZoneLine == null || ZoneLineWaypoint == null)
        {
            InvalidateCrossZoneCache();
            return;
        }
        bool targetUnchanged =
            Target != null
            && Target.IsCrossZone(currentScene)
            && _cachedWaypointTarget.HasValue
            && _cachedWaypointTarget.Value.Matches(Target)
            && string.Equals(_cachedHopScene, currentScene, StringComparison.OrdinalIgnoreCase);
        if (!targetUnchanged)
        {
            InvalidateCrossZoneCache();
            return;
        }
        var approach = GetCrossZoneApproach(currentScene);
        bool nextHopUnchanged = string.Equals(
            _cachedNextHopZoneKey,
            approach.NextHopZoneKey,
            StringComparison.OrdinalIgnoreCase
        );
        if (
            !CrossZoneWaypointPolicy.ShouldKeepOnStateChange(
                _cachedZoneLine != null,
                ZoneLineWaypoint != null,
                targetUnchanged,
                nextHopUnchanged,
                ReferenceEquals(_cachedEntryLine, approach.EntryLine),
                nextHopUnchanged
                    && CrossZoneWaypointPolicy.IsAccessibleSetUnchanged(
                        _cachedHopAccess,
                        _state.Gates
                    ),
                _cachedRouteLocked == approach.IsLocked
            )
        )
            InvalidateCrossZoneCache();
    }

    private void UpdateCrossZoneRouting(string currentScene, Vector3 playerPos)
    {
        if (_unroutableRoute.Matches(currentScene, Target!.Scene))
        {
            Distance = 0f;
            Direction = Vector3.zero;
            return;
        }
        // Missing waypoints must be restored even when the cached line and
        // player position are unchanged. Failed routes are memoized above.
        bool needsRecalc = CrossZoneWaypointPolicy.ShouldRecalculate(
            _cachedZoneLine != null,
            ZoneLineWaypoint != null,
            (_lastCrossZoneCalcPos - playerPos).sqrMagnitude,
            CrossZoneRecalcDistance * CrossZoneRecalcDistance
        );

        if (needsRecalc)
        {
            _lastCrossZoneCalcPos = playerPos;

            var approach = GetCrossZoneApproach(currentScene);
            if (approach.PlacementUnreachable)
            {
                if (Requirements is { } requirements)
                    Requirements = new RequirementResolution(
                        requirements.Quest,
                        requirements.Step,
                        false,
                        "No usable entry reaches this target.",
                        requirements.Chain,
                        requirements.Advisories
                    );
                Target = null;
                Distance = 0f;
                Direction = Vector3.zero;
                return;
            }
            _chosenEntryLine = approach.EntryLine;
            if (!ReferenceEquals(_pinnedZoneLine, approach.FixedLine))
                _pinnedZoneLine = null;
            ZoneLineEntry? bestLine = approach.FixedLine;
            bool routeIsLocked = approach.IsLocked;
            if (approach.NextHopZoneKey == null)
                _unroutableRoute.Remember(currentScene, Target!.Scene);
            else if (bestLine == null)
                bestLine = routeIsLocked
                    ? FindClosestZoneLineAny(approach.NextHopZoneKey, currentScene, playerPos)
                    : FindClosestZoneLine(approach.NextHopZoneKey, currentScene, playerPos);

            if (
                CrossZoneWaypointPolicy.ShouldRebuild(
                    ZoneLineWaypoint != null,
                    bestLine != _cachedZoneLine,
                    _cachedRouteLocked,
                    routeIsLocked
                )
            )
            {
                _cachedZoneLine = bestLine;
                _cachedRouteLocked = routeIsLocked;
                if (bestLine != null)
                {
                    string displayText = ZoneLineText.Format(
                        GetZoneLineDestinationDisplay(bestLine)!,
                        routeIsLocked,
                        routeIsLocked ? GetZoneLineLockReason(bestLine) : null
                    );
                    ZoneLineWaypoint = MakeTarget(
                        NavigationTarget.Kind.ZoneLine,
                        new Vector3(bestLine.X, bestLine.Y, bestLine.Z),
                        displayText,
                        currentScene,
                        Target!.QuestKey,
                        Target.StepOrder
                    );
                }
                else
                {
                    ZoneLineWaypoint = null;
                }
            }
            if (bestLine != null)
                CaptureCrossZoneCache(currentScene, approach);
        }

        if (ZoneLineWaypoint != null)
            UpdateDistanceAndDirection(ZoneLineWaypoint.Position, playerPos);
        else
        {
            Distance = 0f;
            Direction = Vector3.zero;
        }
    }

    // ── Spawn resolution ───────────────────────────────────────────

    /// <summary>
    /// Pick the best spawn in the current scene. Prefers fully reachable
    /// spawns (PathComplete), then partially reachable (PathPartial), then
    /// the spatially closest as a last resort.
    /// </summary>
    private Data.SpawnPoint? PickBestSpawn(List<Data.SpawnPoint> spawns, string currentScene)
    {
        var playerPos = GetPlayerPosition();
        Data.SpawnPoint? bestComplete = null;
        float bestCompDist = float.MaxValue;
        Data.SpawnPoint? bestPartial = null;
        float bestPartDist = float.MaxValue;
        Data.SpawnPoint? bestFallback = null;
        float bestFallDist = float.MaxValue;

        foreach (var sp in spawns)
        {
            if (
                !string.Equals(sp.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase)
                || !IsSelectedSpawnAvailable(sp)
            )
                continue;

            if (!playerPos.HasValue)
            {
                bestComplete ??= sp;
                continue;
            }

            var spPos = new Vector3(sp.X, sp.Y, sp.Z);
            float dist = Vector3.Distance(playerPos.Value, spPos);
            var reach = GetReachability(playerPos.Value, spPos);

            if (reach == NavMeshPathStatus.PathComplete)
            {
                if (dist < bestCompDist)
                {
                    bestCompDist = dist;
                    bestComplete = sp;
                }
            }
            else if (reach == NavMeshPathStatus.PathPartial)
            {
                if (dist < bestPartDist)
                {
                    bestPartDist = dist;
                    bestPartial = sp;
                }
            }
            else
            {
                if (dist < bestFallDist)
                {
                    bestFallDist = dist;
                    bestFallback = sp;
                }
            }
        }

        return bestComplete ?? bestPartial ?? bestFallback ?? FirstPresentSpawn(spawns);
    }

    /// <summary>
    /// Return a spawn in another scene only when its condition holds.
    /// </summary>
    private Data.SpawnPoint? FirstPresentSpawn(List<Data.SpawnPoint> spawns)
    {
        foreach (var spawn in spawns)
        {
            if (IsSelectedSpawnAvailable(spawn))
                return spawn;
        }
        return null;
    }

    private bool IsSelectedSpawnAvailable(Data.SpawnPoint spawn)
    {
        if (!_state.Gates.IsSpawnAvailable(spawn))
            return false;
        if (Requirements?.AvailableSpawns is { } available)
        {
            for (int i = 0; i < available.Count; i++)
                if (ReferenceEquals(available[i], spawn))
                    return true;
            return false;
        }
        return (
                Requirements?.SelectedSpawn == null
                || (Requirements.SelectedSpawn.Entries == null && spawn.Entries == null)
                || ReferenceEquals(Requirements.SelectedSpawn, spawn)
            )
            && (
                Requirements?.SelectedScene == null
                || string.Equals(
                    Requirements.SelectedScene,
                    spawn.Scene,
                    StringComparison.OrdinalIgnoreCase
                )
            );
    }

    private Data.SpawnPoint? FindTargetPlacement()
    {
        if (
            Target?.SourceId != null
            && _canonicalSources.TryGetValue(Target.SourceId, out var source)
        )
            return source.CanonicalSpawn;
        if (
            Target?.SourceId == null
            || !_data.CharacterSpawns.TryGetValue(Target.SourceId, out var spawns)
        )
            return null;
        Data.SpawnPoint? best = null;
        float bestDistance = float.MaxValue;
        foreach (var spawn in spawns)
        {
            if (
                !string.Equals(spawn.Scene, Target.Scene, StringComparison.OrdinalIgnoreCase)
                || !IsSelectedSpawnAvailable(spawn)
            )
                continue;
            float distance = (
                new Vector3(spawn.X, spawn.Y, spawn.Z) - Target.Position
            ).sqrMagnitude;
            if (distance < bestDistance)
            {
                best = spawn;
                bestDistance = distance;
            }
        }
        return best;
    }

    // ── Zone line helpers ──────────────────────────────────────────

    /// <summary>Check the shared gate condition for a zone line.</summary>
    private bool IsZoneLineAccessible(ZoneLineEntry zl) => _state.Gates.IsAvailable(zl.Condition);

    /// <summary>Describe the requirements for the closest viable gate alternative.</summary>
    private string? GetZoneLineLockReason(ZoneLineEntry zl)
    {
        var atoms = _state.Gates.Explain(zl.Condition);
        if (atoms.Count == 0)
            return null;
        var descriptions = new string[atoms.Count];
        for (int i = 0; i < atoms.Count; i++)
            descriptions[i] = _state.Gates.Describe(atoms[i]);
        return string.Join(" and ", descriptions);
    }

    private ZoneLineEntry? FindClosestZoneLine(
        string destinationZoneKey,
        string currentScene,
        Vector3 playerPos
    )
    {
        ZoneLineEntry? bestComplete = null;
        float bestCompDist = float.MaxValue;
        ZoneLineEntry? bestPartial = null;
        float bestPartDist = float.MaxValue;
        ZoneLineEntry? bestFallback = null;
        float bestFallDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (
                !string.Equals(
                    ResolveDestination(zl)?.ZoneKey,
                    destinationZoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                continue;
            if (!IsZoneLineAccessible(zl))
                continue;

            var zlPos = new Vector3(zl.X, zl.Y, zl.Z);
            float dist = Vector3.Distance(playerPos, zlPos);
            var reach = GetReachability(playerPos, zlPos);

            if (reach == NavMeshPathStatus.PathComplete)
            {
                if (dist < bestCompDist)
                {
                    bestCompDist = dist;
                    bestComplete = zl;
                }
            }
            else if (reach == NavMeshPathStatus.PathPartial)
            {
                if (dist < bestPartDist)
                {
                    bestPartDist = dist;
                    bestPartial = zl;
                }
            }
            else
            {
                if (dist < bestFallDist)
                {
                    bestFallDist = dist;
                    bestFallback = zl;
                }
            }
        }

        return bestComplete ?? bestPartial ?? bestFallback;
    }

    /// <summary>
    /// Like FindClosestZoneLine but ignores accessibility — used to find locked
    /// zone lines when no accessible route exists, for directional guidance.
    /// </summary>
    private ZoneLineEntry? FindClosestZoneLineAny(
        string destinationZoneKey,
        string currentScene,
        Vector3 playerPos
    )
    {
        ZoneLineEntry? best = null;
        float bestDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!CanUseZoneLine(zl))
                continue;
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (
                !string.Equals(
                    ResolveDestination(zl)?.ZoneKey,
                    destinationZoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                continue;

            float dist = Vector3.Distance(playerPos, new Vector3(zl.X, zl.Y, zl.Z));
            if (dist < bestDist)
            {
                bestDist = dist;
                best = zl;
            }
        }
        return best;
    }

    private bool HasZoneLineForDestination(string? zoneKey, string currentScene)
    {
        if (zoneKey == null)
            return false;
        foreach (var zl in _data.ZoneLines)
        {
            if (
                string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase)
                && string.Equals(
                    ResolveDestination(zl)?.ZoneKey,
                    zoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
                && IsZoneLineAccessible(zl)
            )
                return true;
        }
        return false;
    }

    // ── Zone key resolution ────────────────────────────────────────

    private string? FindZoneKeyBySceneName(string sceneName)
    {
        return _data.ZoneLookup.TryGetValue(sceneName, out var info) ? info.StableKey : null;
    }

    private string? FindZoneKeyByDisplayName(string? displayName)
    {
        if (displayName == null)
            return null;
        foreach (var kvp in _data.ZoneLookup)
        {
            if (
                string.Equals(
                    kvp.Value.DisplayName,
                    displayName,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                return kvp.Value.StableKey;
        }
        return null;
    }

    private Data.ItemSource? FindFirstSourceWithScene(List<Data.ItemSource> sources)
    {
        foreach (var src in sources)
        {
            if (!_state.Gates.IsSourceAvailable(src))
                continue;
            if (
                ItemSourcePolicy.IsRandomSource(src)
                || !ItemSourcePolicy.NeedsUsedItem(src, _countItem, sources)
            )
                continue;
            if (
                ItemSourcePolicy.IsStaticCandidate(src)
                && !ItemSourcePolicy.HasPendingChildren(src, _countItem)
                && ItemSourcePolicy.SceneOf(src) != null
            )
                return src;
            if (src.Children != null)
            {
                var child = FindFirstSourceWithScene(src.Children);
                if (child != null)
                    return child;
            }
        }
        return null;
    }

    // ── Reachability ────────────────────────────────────────────────────

    /// <summary>
    /// Classify a target's reachability: Complete (fully connected path),
    /// Partial (path exists but doesn't reach the exact point), or Invalid
    /// (no NavMesh connection at all). Both positions are snapped to the
    /// NavMesh surface before testing.
    /// </summary>
    private NavMeshPathStatus GetReachability(Vector3 from, Vector3 to)
    {
        if (!NavMesh.SamplePosition(from, out var fromHit, 5f, NavMesh.AllAreas))
            return NavMeshPathStatus.PathInvalid;
        if (!NavMesh.SamplePosition(to, out var toHit, 5f, NavMesh.AllAreas))
            return NavMeshPathStatus.PathInvalid;

        _scratchPath.ClearCorners();
        NavMesh.CalculatePath(fromHit.position, toHit.position, NavMesh.AllAreas, _scratchPath);
        return _scratchPath.status;
    }

    // ── Utilities ──────────────────────────────────────────────────

    private void UpdateDistanceAndDirection(Vector3 targetPos, Vector3 playerPos)
    {
        var delta = targetPos - playerPos;
        Distance = delta.magnitude;
        Direction = Distance > 0.1f ? delta.normalized : Vector3.zero;
    }

    private static Vector3? GetPlayerPosition()
    {
        var pc = GameData.PlayerControl;
        return pc != null ? pc.transform.position : null;
    }

    /// <summary>Append gate requirements and advisory guidance to the target name.</summary>
    private string WithCharacterUnlockText(string displayName, string? targetKey)
    {
        if (targetKey == null)
            return displayName;
        var atoms = _state.Gates.ExplainCharacter(targetKey);
        if (atoms.Count == 0)
            return _state.Gates.IsCharacterAvailable(targetKey)
                ? displayName
                : $"{displayName}\nUnavailable";
        var descriptions = new string[atoms.Count];
        for (int i = 0; i < atoms.Count; i++)
            descriptions[i] = _state.Gates.Describe(atoms[i]);
        return $"{displayName}\n{string.Join("\n", descriptions)}";
    }

    /// <summary>
    /// Fill the reusable item set for the resolved navigation step.
    /// </summary>
    private HashSet<string> BuildNeededItems(string questKey)
    {
        CorpsePriorityPolicy.FillItems(
            _resolvedStep,
            _data.GetByRuntimeKey(questKey),
            _countItem,
            _neededItems
        );
        return _neededItems;
    }

    private NavigationTarget MakeTarget(
        NavigationTarget.Kind kind,
        Vector3 position,
        string displayName,
        string scene,
        string questKey,
        int stepOrder,
        string? sourceId = null
    )
    {
        return new NavigationTarget(
            kind,
            position,
            displayName,
            scene,
            questKey,
            stepOrder,
            sourceId,
            _originQuestKey,
            _originStepOrder
        );
    }
}
