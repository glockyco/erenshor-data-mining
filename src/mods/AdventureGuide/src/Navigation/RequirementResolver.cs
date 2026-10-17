using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

public sealed class RequirementLink
{
    public string Label { get; }
    public IReadOnlyList<string> Alternatives { get; }
    public GateAtom? Atom { get; }

    public RequirementLink(string label, IReadOnlyList<string> alternatives, GateAtom? atom = null)
    {
        Label = label;
        Alternatives = alternatives;
        Atom = atom;
    }
}

public sealed class RequirementResolution
{
    public QuestEntry Quest { get; }
    public QuestStep Step { get; }
    public bool CanNavigate { get; }
    public string? Message { get; }
    public IReadOnlyList<RequirementLink> Chain { get; }
    public IReadOnlyList<GateAtom> Advisories { get; }
    public string? SelectedScene { get; }
    public AdventureGuide.Data.SpawnPoint? SelectedSpawn { get; }
    public ZoneLineEntry? EntryLine { get; }

    /// <summary>Allowed placements after source filtering. Null leaves placements unconstrained.</summary>
    public IReadOnlyList<AdventureGuide.Data.SpawnPoint>? AvailableSpawns { get; }
    public string DisplayText { get; }

    public RequirementResolution(
        QuestEntry quest,
        QuestStep step,
        bool canNavigate,
        string? message,
        IReadOnlyList<RequirementLink> chain,
        IReadOnlyList<GateAtom> advisories,
        string? selectedScene = null,
        AdventureGuide.Data.SpawnPoint? selectedSpawn = null,
        ZoneLineEntry? entryLine = null,
        IReadOnlyList<AdventureGuide.Data.SpawnPoint>? availableSpawns = null
    )
    {
        Quest = quest;
        Step = step;
        CanNavigate = canNavigate;
        Message = message;
        Chain = chain;
        Advisories = advisories;
        SelectedScene = selectedScene;
        SelectedSpawn = selectedSpawn;
        EntryLine = entryLine;
        AvailableSpawns = availableSpawns;
        var lines = new List<string>(chain.Count + 1);
        foreach (var link in chain)
            lines.Add(
                link.Label
                    + (
                        link.Alternatives.Count == 0
                            ? ""
                            : " (or " + string.Join(" or ", link.Alternatives) + ")"
                    )
            );
        if (message != null)
            lines.Add(message);
        DisplayText = string.Join("\n", lines);
    }
}

/// <summary>Follows one requirement chain. Route-cost ties never expand dependency chains.</summary>
public sealed class RequirementResolver
{
    private readonly GuideData _data;
    private readonly GateConditions _gates;
    private readonly ZoneGraph _graph;
    private readonly Func<QuestEntry, QuestStep?> _currentStep;

    public RequirementResolver(
        GuideData data,
        GateConditions gates,
        ZoneGraph graph,
        Func<QuestEntry, QuestStep?> currentStep
    )
    {
        _data = data;
        _gates = gates;
        _graph = graph;
        _currentStep = currentStep;
    }

    public QuestStep? BuildAcquisitionStep(QuestEntry quest)
    {
        if (quest.Acquisition == null || quest.Acquisition.Count == 0)
            return null;
        var sources = new List<ItemSource>();
        foreach (var acquisition in quest.Acquisition)
        {
            if (acquisition.Method == "item_read")
            {
                var itemStep = new QuestStep
                {
                    TargetKey = acquisition.SourceStableKey,
                    TargetName = acquisition.SourceName,
                };
                var itemSources = ItemSourcePolicy.SourcesFor(quest, itemStep);
                if (itemSources != null)
                    sources.AddRange(itemSources);
            }
            else if (acquisition.SourceStableKey != null || acquisition.ZoneName != null)
            {
                sources.Add(
                    new ItemSource
                    {
                        Type = acquisition.Method == "quest_chain" ? "quest_reward" : "pickup",
                        Name = acquisition.SourceName,
                        SourceKey = acquisition.SourceStableKey,
                        QuestKey =
                            acquisition.Method == "quest_chain"
                                ? acquisition.SourceStableKey
                                : null,
                        Scene =
                            acquisition.Method == "zone_entry" && acquisition.ZoneName != null
                                ? _data.GetSceneName(acquisition.ZoneName)
                                : null,
                        Zone = acquisition.ZoneName,
                    }
                );
            }
        }
        return sources.Count == 0
            ? null
            : new QuestStep
            {
                Action = "acquire",
                TargetType = "item",
                TargetKey = quest.StableKey,
                TargetName = quest.DisplayName,
                Description = "Start " + quest.DisplayName + ".",
                Sources = sources,
            };
    }

    public RequirementResolution Resolve(
        QuestEntry quest,
        QuestStep step,
        string scene,
        ZoneLineEntry? pinnedLine = null,
        ItemSource? selectedSource = null
    )
    {
        var chain = new List<RequirementLink>();
        var advisories = new List<GateAtom>();
        var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var routes = _graph.BuildRouteLookup(scene);
        bool requirement = false;
        while (true)
        {
            string identity = quest.RuntimeKey + ":" + step.Order + ":" + step.TargetKey;
            if (!visited.Add("step:" + identity))
                return Finish(false, "Requirement cycle prevents navigation.");

            Candidate? best = null;
            bool gatedAlternative = false;
            List<Candidate>? available = step.TargetType == "item" ? new List<Candidate>() : null;
            var sourceChoice = SourceNavigationSelection.Contains(
                ItemSourcePolicy.SourcesFor(quest, step),
                selectedSource
            )
                ? selectedSource
                : null;
            foreach (var candidate in Candidates(quest, step, routes, sourceChoice))
            {
                Evaluate(candidate, quest, routes, requirement ? null : pinnedLine);
                if (
                    candidate.Missing == null
                    && candidate.Failure == null
                    && candidate.RewardQuest == null
                )
                    available?.Add(candidate);
                gatedAlternative |= candidate.Missing != null || candidate.Failure != null;
                if (best == null || Better(candidate, best))
                    best = candidate;
            }
            if (best == null)
            {
                if (
                    !requirement
                    && step.TargetType == "item"
                    && HasAvailableRandomSource(ItemSourcePolicy.SourcesFor(quest, step))
                )
                    return Finish(true, null);
                if (requirement)
                    chain.Add(
                        new RequirementLink(
                            step.TargetName ?? step.Description,
                            Array.Empty<string>()
                        )
                    );
                return Finish(false, NoSourceMessage(quest, step));
            }
            foreach (var atom in best.Advisories)
            {
                if (
                    advisories.Exists(existing =>
                        existing.Kind == atom.Kind
                        && existing.Ref == atom.Ref
                        && existing.Slot == atom.Slot
                    )
                )
                    continue;
                advisories.Add(atom);
                chain.Add(new RequirementLink(_gates.Describe(atom), Array.Empty<string>(), atom));
            }
            if (best.Failure != null)
            {
                if (
                    best.Missing?.First is GateAtom failedAtom
                    && failedAtom.Kind != GateAtomKind.QuestNotDone
                )
                {
                    if (!requirement)
                        chain.Insert(
                            0,
                            new RequirementLink(
                                step.TargetName ?? step.Description,
                                Array.Empty<string>()
                            )
                        );
                    chain.Add(
                        new RequirementLink(
                            DescribeGroup(best.Missing.Group!),
                            Alternatives(best.Missing),
                            failedAtom
                        )
                    );
                }
                return Finish(false, best.Failure);
            }
            if (best.Missing != null)
            {
                if (!requirement)
                    chain.Insert(
                        0,
                        new RequirementLink(
                            step.TargetName ?? step.Description,
                            Array.Empty<string>()
                        )
                    );
                var choice = best.Missing;
                var atom = choice.First!;
                if (!visited.Add("atom:" + atom.Kind + ":" + atom.Ref + ":" + atom.Slot))
                    return Finish(false, "Requirement cycle prevents navigation.");
                chain.Add(
                    new RequirementLink(DescribeGroup(choice.Group!), Alternatives(choice), atom)
                );
                if (!TryRequirement(atom, quest, out var nextQuest, out var nextStep))
                    return Finish(false, NoRequirementSourceMessage(atom, quest));
                quest = nextQuest;
                step = nextStep;
                requirement = true;
                continue;
            }
            if (best.RewardQuest != null)
            {
                if (!requirement)
                    chain.Insert(
                        0,
                        new RequirementLink(
                            step.TargetName ?? step.Description,
                            Array.Empty<string>()
                        )
                    );
                var nextStep = _currentStep(best.RewardQuest);
                if (nextStep == null)
                    return Finish(
                        false,
                        "No current step is available for " + best.RewardQuest.DisplayName + "."
                    );
                var atom = new GateAtom
                {
                    Kind = GateAtomKind.QuestDone,
                    Ref = best.RewardQuest.DBName,
                };
                chain.Add(new RequirementLink(_gates.Describe(atom), Array.Empty<string>(), atom));
                quest = best.RewardQuest;
                step = nextStep;
                requirement = true;
                continue;
            }
            if (best.Input != null && available != null)
                for (int i = available.Count - 1; i >= 0; i--)
                    if (!ReferenceEquals(available[i].Input, best.Input))
                        available.RemoveAt(i);
            if (best.Input != null)
            {
                if (!requirement)
                    chain.Insert(
                        0,
                        new RequirementLink(
                            step.TargetName ?? step.Description,
                            Array.Empty<string>()
                        )
                    );
                step = IngredientStep(step, best.Input, best.InputQuantity);
                requirement = true;
            }
            bool constrainSource =
                best.Source != null
                && (
                    sourceChoice != null
                    || requirement
                    || best.HadGatedAlternative
                    || best.Source.AcquisitionKey != null
                    || gatedAlternative
                );
            List<AdventureGuide.Data.SpawnPoint>? availableSpawns = null;
            if (constrainSource)
            {
                var sources = new List<ItemSource>();
                availableSpawns = new List<AdventureGuide.Data.SpawnPoint>();
                foreach (var candidate in available!)
                {
                    if (candidate.Source != null && !sources.Contains(candidate.Source))
                        sources.Add(candidate.Source);
                    if (candidate.Spawn != null && !availableSpawns.Contains(candidate.Spawn))
                        availableSpawns.Add(candidate.Spawn);
                }
                step = SourceStep(step, sources);
            }
            bool selectPlacement =
                step.TargetType != "item" || (constrainSource && available!.Count == 1);
            if (requirement)
                chain.Add(
                    new RequirementLink(
                        best.Source?.Name ?? step.TargetName ?? step.Description,
                        Array.Empty<string>()
                    )
                );
            return Finish(
                true,
                null,
                selectPlacement ? best.Scene : null,
                selectPlacement ? best.Spawn : null,
                selectPlacement ? best.Placement?.EntryLine : null,
                availableSpawns
            );
        }

        RequirementResolution Finish(
            bool canNavigate,
            string? message,
            string? selectedScene = null,
            AdventureGuide.Data.SpawnPoint? selectedSpawn = null,
            ZoneLineEntry? entryLine = null,
            IReadOnlyList<AdventureGuide.Data.SpawnPoint>? availableSpawns = null
        ) =>
            new(
                quest,
                step,
                canNavigate,
                message,
                chain,
                advisories,
                selectedScene,
                selectedSpawn,
                entryLine,
                availableSpawns
            );
    }

    private sealed class Choice
    {
        public List<GateAtom>? Group;
        public GateAtom? First;
        public IReadOnlyList<List<GateAtom>>? Groups;
        public int Missing;
        public int Cost = int.MaxValue;
        public string? Failure;
    }

    private sealed class Candidate
    {
        public string Scene = "";
        public ItemSource? Source;
        public AdventureGuide.Data.SpawnPoint? Spawn;
        public PlacementRoute? Placement;
        public QuestEntry? RewardQuest;
        public readonly List<int> Conditions = new();
        public readonly List<GateAtom> Advisories = new();
        public readonly List<ItemSource> SourceChain = new();
        public ItemSource? Input;
        public double InputQuantity;
        public Choice? Missing;
        public string? Failure;
        public int Hops;
        public bool HadGatedAlternative;
    }

    private IEnumerable<Candidate> Candidates(
        QuestEntry quest,
        QuestStep step,
        ZoneGraph.RouteLookup routes,
        ItemSource? selectedSource
    )
    {
        if (step.Location != null)
        {
            yield return new Candidate { Scene = step.Location.Scene };
            yield break;
        }
        if (step.TargetType == "item")
        {
            var sources = ItemSourcePolicy.SourcesFor(quest, step);
            if (sources != null)
                foreach (var candidate in SourceCandidates(sources, routes, selectedSource))
                    yield return candidate;
            yield break;
        }
        if (
            step.TargetKey != null
            && _data.CharacterSpawns.TryGetValue(step.TargetKey, out var spawns)
        )
        {
            bool gated = spawns.Exists(spawn => !_gates.IsSpawnAvailable(spawn));
            foreach (var spawn in spawns)
            {
                var candidate = new Candidate
                {
                    Scene = spawn.Scene,
                    Spawn = spawn,
                    HadGatedAlternative = gated,
                };
                if (spawn.Condition.HasValue)
                    candidate.Conditions.Add(spawn.Condition.Value);
                yield return candidate;
            }
            yield break;
        }
        string? destinationScene = step.ZoneName == null ? null : _data.GetSceneName(step.ZoneName);
        if (destinationScene == null && step.TargetType == "zone")
            foreach (var zone in _data.ZoneLookup)
                if (
                    string.Equals(
                        zone.Value.StableKey,
                        step.TargetKey,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    destinationScene = zone.Key;
                    break;
                }
        if (destinationScene != null)
            yield return new Candidate { Scene = destinationScene };
    }

    private IEnumerable<Candidate> SourceCandidates(
        List<ItemSource> sources,
        ZoneGraph.RouteLookup routes,
        ItemSource? selectedSource = null
    )
    {
        bool gated = sources.Exists(source =>
            !_gates.IsSourceAvailable(source) || HasEntryPlacement(source)
        );
        foreach (var source in sources)
        {
            if (
                selectedSource != null
                && !ReferenceEquals(source, selectedSource)
                && !SourceNavigationSelection.Contains(source.Children, selectedSource)
            )
                continue;
            if (!ItemSourcePolicy.NeedsUsedItem(source, _gates.Facts.ItemCount, sources))
                continue;
            if (source.Type == "quest_reward" && source.QuestKey != null)
            {
                var quest = _data.GetByStableKey(source.QuestKey);
                var step = quest == null ? null : _currentStep(quest);
                string? rewardScene =
                    step == null ? null : StepSceneResolver.ResolveScene(quest!, step, _data);
                if (step != null)
                {
                    var candidate = new Candidate
                    {
                        Scene = rewardScene ?? "",
                        Source = source,
                        RewardQuest = quest,
                        HadGatedAlternative = gated,
                        SourceChain = { source },
                    };
                    if (source.Condition.HasValue)
                        candidate.Conditions.Add(source.Condition.Value);
                    yield return candidate;
                }
                continue;
            }
            if (
                source.Children is { Count: > 0 }
                && ItemSourcePolicy.HasPendingChildren(source, _gates.Facts.ItemCount)
            )
            {
                foreach (
                    var candidate in SourceCandidates(
                        source.Children,
                        routes,
                        ReferenceEquals(source, selectedSource) ? null : selectedSource
                    )
                )
                {
                    if (source.Condition.HasValue)
                        candidate.Conditions.Insert(0, source.Condition.Value);
                    candidate.HadGatedAlternative |= gated;
                    candidate.SourceChain.Insert(0, source);
                    if (source.Type == "ingredient")
                    {
                        candidate.Input = source;
                        candidate.InputQuantity = ItemSourcePolicy.RequiredInputQuantity(
                            source,
                            sources
                        );
                    }
                    yield return candidate;
                }
                continue;
            }
            if (!ItemSourcePolicy.IsStaticCandidate(source))
                continue;
            if (source.AcquisitionKey != null)
            {
                var location = source.CanonicalLocation;
                if (location?.Scene != null && location.Relation != "unlocated")
                {
                    var spawn = source.CanonicalSpawn;
                    var candidate = new Candidate
                    {
                        Scene = location.Scene,
                        Source = source,
                        Spawn = spawn,
                        SourceChain = { source },
                        HadGatedAlternative = gated,
                    };
                    if (source.Condition.HasValue)
                        candidate.Conditions.Add(source.Condition.Value);
                    if (spawn?.Condition is int condition)
                        candidate.Conditions.Add(condition);
                    yield return candidate;
                }
                continue;
            }

            if (
                source.SourceKey != null
                && _data.CharacterSpawns.TryGetValue(source.SourceKey, out var spawns)
            )
            {
                foreach (var spawn in spawns)
                {
                    var placement = spawn.Entries == null ? null : routes.GetPlacementRoute(spawn);
                    if (spawn.Entries != null && placement == null)
                        continue;
                    var candidate = new Candidate
                    {
                        Scene = spawn.Scene,
                        Source = source,
                        Spawn = spawn,
                        Placement = placement,
                        HadGatedAlternative = gated,
                        SourceChain = { source },
                    };
                    if (source.Condition.HasValue)
                        candidate.Conditions.Add(source.Condition.Value);
                    if (spawn.Condition.HasValue)
                        candidate.Conditions.Add(spawn.Condition.Value);
                    yield return candidate;
                }
                continue;
            }
            string? sourceScene = source.Scene;
            if (PositionedSource.TryParse(source.SourceKey, out var position))
                sourceScene = position.Scene;
            sourceScene ??= source.Zone == null ? null : _data.GetSceneName(source.Zone);
            if (sourceScene != null)
            {
                var candidate = new Candidate
                {
                    Scene = sourceScene,
                    Source = source,
                    HadGatedAlternative = gated,
                    SourceChain = { source },
                };
                if (source.Condition.HasValue)
                    candidate.Conditions.Add(source.Condition.Value);
                yield return candidate;
            }
        }
    }

    private bool HasEntryPlacement(ItemSource source)
    {
        if (source.AcquisitionKey != null)
            return source.CanonicalSpawn?.Entries != null;
        if (
            source.SourceKey != null
            && _data.CharacterSpawns.TryGetValue(source.SourceKey, out var spawns)
            && spawns.Exists(spawn => spawn.Entries != null)
        )
            return true;
        return source.Children?.Exists(HasEntryPlacement) == true;
    }

    private void Evaluate(
        Candidate candidate,
        QuestEntry owner,
        ZoneGraph.RouteLookup routes,
        ZoneLineEntry? pinnedLine
    )
    {
        string scene = routes.Scene;
        foreach (var source in candidate.SourceChain)
        {
            candidate.Failure ??= _gates.CanonicalSourceFailure(source);
            foreach (var groups in _gates.SourceRequirements(source))
                Apply(candidate, SelectGroups(groups, owner, routes));
        }
        if (candidate.Spawn != null)
            candidate.Placement ??= routes.GetPlacementRoute(candidate.Spawn);
        if (candidate.Spawn != null && candidate.Placement == null)
        {
            candidate.Failure = "No route reaches this requirement.";
            return;
        }
        if (
            candidate.Spawn?.Entries == null
            && pinnedLine?.Condition is int pinnedCondition
            && string.Equals(scene, pinnedLine.Scene, StringComparison.OrdinalIgnoreCase)
            && _graph.ResolveDestination(pinnedLine).HasValue
            && !string.Equals(scene, candidate.Scene, StringComparison.OrdinalIgnoreCase)
        )
            Apply(candidate, Select(pinnedCondition, owner, routes));
        foreach (int condition in candidate.Conditions)
            Apply(candidate, Select(condition, owner, routes));
        if (candidate.Placement?.EntryLine?.Condition is int entryCondition)
            Apply(candidate, Select(entryCondition, owner, routes));
        if (candidate.RewardQuest != null && candidate.Scene.Length == 0)
        {
            candidate.Hops = int.MaxValue;
            return;
        }
        var route =
            candidate.Spawn == null
                ? routes.FindRoute(candidate.Scene)
                : candidate.Placement!.Value.Route;
        if (
            route == null
            && (
                candidate.Spawn != null
                || string.Equals(scene, candidate.Scene, StringComparison.OrdinalIgnoreCase)
            )
        )
            return;
        if (route == null)
        {
            candidate.Failure ??= "No route reaches this requirement.";
            return;
        }
        candidate.Hops = route.Path.Count - 1;
        // The fallback route may have an open first hop and a locked later hop.
        for (int hop = 1; hop < route.Path.Count; hop++)
        {
            Choice? best = null;
            foreach (var line in _graph.LinesForHop(route.Path[hop - 1], route.Path[hop]))
            {
                if (!_gates.CanBecomeAvailable(line.Condition))
                    continue;
                var choice = line.Condition.HasValue
                    ? Select(line.Condition.Value, owner, routes)
                    : new Choice();
                if (best == null || Better(choice, best))
                    best = choice;
            }
            if (best != null)
                Apply(candidate, best);
        }
    }

    private void Apply(Candidate candidate, Choice choice)
    {
        if (choice.Group != null || choice.Failure != null)
        {
            if (candidate.Missing == null && candidate.Failure == null)
            {
                candidate.Missing = choice.First == null ? null : choice;
                candidate.Failure = choice.Failure;
            }
        }
        if (choice.Groups == null)
            return;
        foreach (var group in choice.Groups)
        foreach (var atom in group)
            if (atom.Kind == GateAtomKind.EncounterWon)
                candidate.Advisories.Add(atom);
    }

    private Choice Select(int condition, QuestEntry owner, ZoneGraph.RouteLookup routes) =>
        SelectGroups(_data.Conditions[condition], owner, routes);

    private Choice SelectGroups(
        IReadOnlyList<List<GateAtom>> groups,
        QuestEntry owner,
        ZoneGraph.RouteLookup routes
    )
    {
        Choice? best = null;
        foreach (var group in groups)
        {
            var choice = new Choice { Groups = groups, Group = group };
            foreach (var atom in group)
            {
                if (_gates.Holds(atom))
                    continue;
                choice.Missing++;
                choice.First ??= atom;
                if (
                    atom.Kind == GateAtomKind.QuestNotDone
                    || atom.Kind == GateAtomKind.AccountState && atom.Value == "false"
                )
                    choice.Failure = "This target is no longer available.";
            }
            if (choice.First != null && choice.Failure == null)
            {
                choice.Cost = RequirementCost(choice.First, owner, routes);
                if (choice.Cost == int.MaxValue)
                    choice.Failure = NoRequirementSourceMessage(choice.First, owner);
            }
            if (best == null || Better(choice, best))
                best = choice;
        }
        return best
            ?? new Choice
            {
                Groups = groups,
                Failure = "This target has no available condition group.",
            };
    }

    private static bool Better(Choice candidate, Choice best)
    {
        if ((candidate.Failure == null) != (best.Failure == null))
            return candidate.Failure == null;
        if (candidate.Missing != best.Missing)
            return candidate.Missing < best.Missing;
        return candidate.Cost < best.Cost;
    }

    private static bool Better(Candidate candidate, Candidate best)
    {
        if ((candidate.Failure == null) != (best.Failure == null))
            return candidate.Failure == null;
        if ((candidate.Missing == null) != (best.Missing == null))
            return candidate.Missing == null;
        if (candidate.Missing != null && best.Missing != null)
        {
            if (candidate.Missing.Missing != best.Missing.Missing)
                return candidate.Missing.Missing < best.Missing.Missing;
            if (candidate.Missing.Cost != best.Missing.Cost)
                return candidate.Missing.Cost < best.Missing.Cost;
        }
        return candidate.Hops < best.Hops;
    }

    private int RequirementCost(GateAtom atom, QuestEntry owner, ZoneGraph.RouteLookup routes)
    {
        if (!TryRequirement(atom, owner, out var quest, out var step))
            return int.MaxValue;
        int best = int.MaxValue;
        bool hasCandidate = false;
        foreach (var candidate in Candidates(quest, step, routes, null))
        {
            hasCandidate = true;
            // A reward's current step can name another reward. Follow it only
            // in Resolve, rather than expanding its dependency tree to rank it.
            if (candidate.RewardQuest != null && candidate.Scene.Length == 0)
            {
                best = Math.Min(best, int.MaxValue - 1);
                continue;
            }
            if (candidate.Spawn != null)
            {
                var placement = candidate.Placement ?? routes.GetPlacementRoute(candidate.Spawn);
                if (placement != null)
                    best = Math.Min(best, placement.Value.Route?.Path.Count - 1 ?? 0);
                continue;
            }
            best = Math.Min(best, routes.HopCount(candidate.Scene));
        }
        // A known quest step can explain a non-spatial source such as crafting.
        // Follow it before stopping so the endpoint remains the quest's current step.
        if (!hasCandidate && atom.Kind == GateAtomKind.QuestDone)
            return int.MaxValue - 1;
        return best;
    }

    private bool HasAvailableRandomSource(List<ItemSource>? sources)
    {
        if (sources == null)
            return false;
        foreach (var source in sources)
        {
            if (!_gates.IsSourceAvailable(source))
                continue;
            if (
                ItemSourcePolicy.IsRandomSource(source) || HasAvailableRandomSource(source.Children)
            )
                return true;
        }
        return false;
    }

    private string RequirementName(GateAtom atom) =>
        atom.Kind is GateAtomKind.QuestDone or GateAtomKind.QuestNotDone
            ? _data.GetByDBName(atom.Ref)?.DisplayName ?? atom.Ref
        : _data.GateItems.TryGetValue(atom.Ref, out var item) ? item.Name
        : atom.Ref;

    private string NoRequirementSourceMessage(GateAtom atom, QuestEntry owner)
    {
        if (TryRequirement(atom, owner, out var quest, out var step))
            return NoSourceMessage(quest, step);
        string name = RequirementName(atom);
        return atom.Kind == GateAtomKind.QuestDone
            ? name + " cannot be started from a known source."
            : "No reachable source is known for " + name + ".";
    }

    private string NoSourceMessage(QuestEntry quest, QuestStep step)
    {
        string name = step.TargetName ?? quest.DisplayName;
        var crafting = FindCraftingSource(ItemSourcePolicy.SourcesFor(quest, step));
        return crafting != null
            ? $"{name} is crafted ({crafting.Name}) and has no source the guide can navigate to."
            : "No reachable source is known for " + name + ".";
    }

    private ItemSource? FindCraftingSource(List<ItemSource>? sources)
    {
        if (sources == null)
            return null;
        foreach (var source in sources)
        {
            if (!_gates.IsSourceAvailable(source))
                continue;
            if (source.Type == "crafting")
                return source;
            if (FindCraftingSource(source.Children) is { } crafting)
                return crafting;
        }
        return null;
    }

    private bool TryRequirement(
        GateAtom atom,
        QuestEntry owner,
        out QuestEntry quest,
        out QuestStep step
    )
    {
        quest = owner;
        step = null!;
        if (atom.Kind == GateAtomKind.QuestDone)
        {
            var requiredQuest = _data.GetByDBName(atom.Ref) ?? _data.GetByStableKey(atom.Ref);
            if (requiredQuest == null || _currentStep(requiredQuest) is not { } current)
                return false;
            quest = requiredQuest;
            step = current;
            return true;
        }
        if (
            (
                atom.Kind is GateAtomKind.ItemHeld or GateAtomKind.KeyHeld
                || atom.Kind == GateAtomKind.PlanningSlotItem
                    && _gates.Facts.ItemCount(atom.Ref) <= 0
            ) && _data.GateItems.TryGetValue(atom.Ref, out var item)
        )
        {
            step = new QuestStep
            {
                Action = "obtain",
                TargetType = "item",
                TargetKey = atom.Ref,
                TargetName = item.Name,
                Description = "Obtain " + item.Name + ".",
                Sources = item.Sources,
            };
            return true;
        }
        if (atom.Kind is GateAtomKind.RoomFurnished or GateAtomKind.PlanningSlotItem)
        {
            foreach (var entry in _data.All)
            {
                if (entry.RequiredItems != null)
                    foreach (var required in entry.RequiredItems)
                        if (FindPlanningTable(required.Sources) is { } source)
                        {
                            step = PlanningStep(source, atom);
                            return true;
                        }
                if (entry.Steps != null)
                    foreach (var entryStep in entry.Steps)
                        if (FindPlanningTable(entryStep.Sources) is { } source)
                        {
                            step = PlanningStep(source, atom);
                            return true;
                        }
            }
        }
        return false;
    }

    private static ItemSource? FindPlanningTable(List<ItemSource>? sources)
    {
        if (sources == null)
            return null;
        foreach (var source in sources)
        {
            if (
                PositionedSource.TryParse(source.SourceKey, out var position)
                && position.Kind == "planningtable"
            )
                return source;
            if (FindPlanningTable(source.Children) is { } child)
                return child;
        }
        return null;
    }

    private static QuestStep PlanningStep(ItemSource source, GateAtom atom)
    {
        PositionedSource.TryParse(source.SourceKey, out var position);
        return new QuestStep
        {
            Action = "go_to",
            TargetType = "location",
            TargetKey = source.SourceKey,
            TargetName = source.Name,
            Description =
                atom.Kind == GateAtomKind.PlanningSlotItem
                    ? atom.Instruction
                        ?? throw new InvalidOperationException(
                            "Planning slot atom has no instruction"
                        )
                    : "Furnish the Reliquary room at the planning table.",
            Location = new WorkflowLocation
            {
                StableKey = source.SourceKey!,
                DisplayName = source.Name ?? "Planning Table",
                Scene = position.Scene,
                X = position.X,
                Y = position.Y,
                Z = position.Z,
            },
        };
    }

    private static QuestStep IngredientStep(
        QuestStep original,
        ItemSource input,
        double quantity
    ) =>
        new()
        {
            Order = original.Order,
            Action = "obtain",
            Description = "Obtain " + input.Name + ".",
            TargetName = input.Name,
            TargetType = "item",
            TargetKey = input.ItemStableKey,
            Quantity = (int)Math.Ceiling(quantity),
            Sources = input.Children,
        };

    private static QuestStep SourceStep(QuestStep original, List<ItemSource> sources) =>
        new()
        {
            Order = original.Order,
            Action = original.Action,
            Description = original.Description,
            TargetName = original.TargetName,
            TargetType = original.TargetType,
            TargetKey = original.TargetKey,
            Quantity = original.Quantity,
            ZoneName = original.ZoneName,
            Keyword = original.Keyword,
            Tips = original.Tips,
            OrGroup = original.OrGroup,
            LevelEstimate = original.LevelEstimate,
            Sources = sources,
        };

    private string DescribeGroup(List<GateAtom> group)
    {
        var labels = new List<string>();
        foreach (var atom in group)
            if (atom.Kind != GateAtomKind.EncounterWon && !_gates.Holds(atom))
                labels.Add(_gates.Describe(atom));
        return string.Join(" and ", labels);
    }

    private IReadOnlyList<string> Alternatives(Choice choice)
    {
        var alternatives = new List<string>();
        foreach (var group in choice.Groups!)
        {
            if (ReferenceEquals(group, choice.Group))
                continue;
            string label = DescribeGroup(group);
            if (label.Length > 0)
                alternatives.Add(label);
        }
        return alternatives;
    }
}
