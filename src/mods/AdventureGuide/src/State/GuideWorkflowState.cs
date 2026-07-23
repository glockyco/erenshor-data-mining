using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using Newtonsoft.Json;
using UnityEngine;

namespace AdventureGuide.State;

/// <summary>
/// Bounded runtime state for guide-only scripted workflows. Game quest state is
/// deliberately absent: workflow evidence comes only from inventory deltas,
/// exported trigger bounds, descriptor-matched entities, and reward containers.
/// </summary>
public sealed class GuideWorkflowState
{
    private sealed class Runtime
    {
        public readonly QuestEntry Quest;
        public readonly WorkflowCycleState Cycle;
        public readonly Dictionary<int, ObservedTarget> ObservedTargets = new();
        public readonly List<int> MissingTargetIds = new();
        public Character? RewardInstance;

        public Runtime(QuestEntry quest)
        {
            Quest = quest;
            Cycle = new WorkflowCycleState(quest);
        }
    }

    private sealed class ObservedTarget
    {
        public readonly Character Character;
        public readonly string Group;

        public ObservedTarget(Character character, string group)
        {
            Character = character;
            Group = group;
        }
    }

    private sealed class RecoveryEnvelope
    {
        [JsonProperty("workflow")]
        public RecoveryHint? Workflow { get; set; }
    }

    private sealed class RecoveryHint
    {
        [JsonProperty("stable_key")]
        public string StableKey { get; set; } = "";

        [JsonProperty("generation")]
        public int Generation { get; set; }

        [JsonProperty("trigger_latched")]
        public bool TriggerLatched { get; set; }
    }

    private readonly GuideData _data;
    private readonly EntityRegistry _entities;
    private readonly Func<IReadOnlyList<Character>> _findLiveCharacters;
    private readonly Dictionary<string, Runtime> _byStableKey = new(
        StringComparer.OrdinalIgnoreCase
    );
    private readonly DiscoveryWindow _discovery = new();
    private GuideConfig? _config;
    private IConfigValue<string>? _recoveryEntry;
    private string? _selectedWorkflowKey;
    private int _boundSlotIndex = -1;
    private string _currentScene = "";
    private float _evaluationTimer;

    private const float EvaluationInterval = 0.25f;

    public event Action<QuestEntry>? Changed;
    public event Action<QuestEntry>? CycleReset;

    public GuideWorkflowState(
        GuideData data,
        EntityRegistry entities,
        Func<IReadOnlyList<Character>>? findLiveCharacters = null
    )
    {
        _data = data;
        _entities = entities;
        _findLiveCharacters = findLiveCharacters ?? FindLiveCharacters;
        foreach (var quest in data.All)
        {
            if (!quest.IsGuideOnly)
                continue;
            _byStableKey.Add(quest.StableKey, new Runtime(quest));
        }
    }

    public void LoadFromConfig(GuideConfig config) => _config = config;

    public void OnCharacterLoaded(Func<string, int> countItem)
    {
        if (_config == null)
            return;
        var slot = GameData.CurrentCharacterSlot;
        if (slot == null || slot.index == _boundSlotIndex)
            return;

        SaveToConfig();
        _boundSlotIndex = slot.index;
        _recoveryEntry = _config.BindPerCharacter(slot.index, "WorkflowRecovery", "");
        foreach (var runtime in _byStableKey.Values)
            ResetRuntime(runtime, countItem(runtime.Quest.WorkflowCycle!.Trigger.ItemStableKey));
        _selectedWorkflowKey = null;

        var raw = _recoveryEntry.Value;
        if (!string.IsNullOrWhiteSpace(raw))
        {
            var envelope = JsonConvert.DeserializeObject<RecoveryEnvelope>(raw);
            if (
                envelope?.Workflow != null
                && _byStableKey.TryGetValue(envelope.Workflow.StableKey, out var runtime)
            )
            {
                runtime.Cycle.Restore(
                    envelope.Workflow.Generation,
                    envelope.Workflow.TriggerLatched,
                    runtime.Cycle.LastItemCount
                );
                _selectedWorkflowKey = runtime.Quest.StableKey;
            }
        }

        ScheduleDiscovery();
    }

    public void SaveToConfig()
    {
        if (_recoveryEntry == null)
            return;
        if (
            _selectedWorkflowKey == null
            || !_byStableKey.TryGetValue(_selectedWorkflowKey, out var runtime)
            || (runtime.Cycle.Generation == 0 && !runtime.Cycle.TriggerLatched)
        )
        {
            _recoveryEntry.Value = "";
            return;
        }

        var envelope = new RecoveryEnvelope
        {
            Workflow = new RecoveryHint
            {
                StableKey = runtime.Quest.StableKey,
                Generation = runtime.Cycle.Generation,
                TriggerLatched = runtime.Cycle.TriggerLatched,
            },
        };
        _recoveryEntry.Value = JsonConvert.SerializeObject(envelope, Formatting.None);
    }

    public void OnSceneChanged(string scene, Func<string, int> countItem)
    {
        _currentScene = scene;
        foreach (var runtime in _byStableKey.Values)
        {
            runtime.ObservedTargets.Clear();
            runtime.RewardInstance = null;
            int current = countItem(runtime.Quest.WorkflowCycle!.Trigger.ItemStableKey);
            if (runtime.Cycle.BeginScene(current))
                Changed?.Invoke(runtime.Quest);
        }
        ScheduleDiscovery();
    }

    public void OnInventoryChanged(
        string scene,
        Vector3? playerPosition,
        Func<string, int> countItem
    )
    {
        foreach (var runtime in _byStableKey.Values)
        {
            var trigger = runtime.Quest.WorkflowCycle!.Trigger;
            int current = countItem(trigger.ItemStableKey);
            bool atTrigger =
                playerPosition.HasValue
                && string.Equals(scene, trigger.Location.Scene, StringComparison.OrdinalIgnoreCase)
                && trigger.Location.Contains(
                    playerPosition.Value.x,
                    playerPosition.Value.y,
                    playerPosition.Value.z
                );
            bool wasLatched = runtime.Cycle.TriggerLatched;
            if (runtime.Cycle.ObserveInventory(current, atTrigger))
                Changed?.Invoke(runtime.Quest);
            if (!wasLatched && runtime.Cycle.TriggerLatched)
            {
                _selectedWorkflowKey = runtime.Quest.StableKey;
                SaveToConfig();
            }
        }
    }

    public void Update(float deltaTime, Func<string, int> countItem)
    {
        _evaluationTimer -= deltaTime;
        if (_evaluationTimer <= 0f)
        {
            _evaluationTimer = EvaluationInterval;
            foreach (var runtime in _byStableKey.Values)
            {
                if (runtime.Cycle.TriggerLatched)
                    Evaluate(runtime, countItem);
            }
        }

        if (!_discovery.Advance(deltaTime))
            return;

        RevalidateLiveEntities(countItem);
        if (_discovery.IsComplete)
            CompleteRecoveryDiscovery();
    }

    public void ObserveCharacterStarted(Character character)
    {
        if (character == null || !IsCurrentWorkflowScene())
            return;
        MatchObservedCharacter(character);
    }

    public void ObserveCharacterDeath(Character character, Func<string, int> countItem)
    {
        if (character == null)
            return;
        int instanceId = character.GetInstanceID();
        foreach (var runtime in _byStableKey.Values)
        {
            if (
                runtime.RewardInstance != null
                && runtime.RewardInstance.GetInstanceID() == instanceId
            )
            {
                // Death only creates the reward corpse. Completion is observed
                // later at NPC.ExpediteRot, which LootWindow calls after the
                // descriptor-matched corpse has been emptied.
                return;
            }
            if (!runtime.ObservedTargets.Remove(instanceId, out var observed))
                continue;
            runtime.Cycle.RecordTargetDeath(observed.Group, runtime.ObservedTargets.Count > 0);
            if (runtime.Cycle.TargetsDefeated)
            {
                if (runtime.Quest.WorkflowCycle!.RewardContainer == null)
                {
                    ResetCycle(runtime, countItem);
                    return;
                }
                runtime.Cycle.UpdatePresence(liveTargetCount: 0, lostObservedTarget: false);
            }
            Changed?.Invoke(runtime.Quest);
            return;
        }

        MatchUnregisteredDeath(character, countItem);
    }

    public void ObserveRewardContainerConsumed(Character character, Func<string, int> countItem)
    {
        if (character == null)
            return;
        int instanceId = character.GetInstanceID();
        foreach (var runtime in _byStableKey.Values)
        {
            if (
                !runtime.Cycle.RewardSeen
                || runtime.RewardInstance == null
                || runtime.RewardInstance.GetInstanceID() != instanceId
            )
                continue;
            ResetCycle(runtime, countItem);
            return;
        }
    }

    public int GetCurrentStepIndex(QuestEntry quest, Func<string, int> countItem)
    {
        return _byStableKey.TryGetValue(quest.StableKey, out var runtime)
            ? runtime.Cycle.GetCurrentStepIndex(countItem)
            : 0;
    }

    public WorkflowStage GetStage(QuestEntry quest) =>
        _byStableKey.TryGetValue(quest.StableKey, out var runtime)
            ? runtime.Cycle.Stage
            : WorkflowStage.Unverifiable;

    public int GetGeneration(QuestEntry quest) =>
        _byStableKey.TryGetValue(quest.StableKey, out var runtime) ? runtime.Cycle.Generation : 0;

    public bool IsInProgress(QuestEntry quest) =>
        _byStableKey.TryGetValue(quest.StableKey, out var runtime)
        && runtime.Cycle.Stage is not WorkflowStage.NeedItem;

    public bool IsInCurrentScene(QuestEntry quest) =>
        quest.WorkflowCycle != null
        && string.Equals(
            quest.WorkflowCycle.Trigger.Location.Scene,
            _currentScene,
            StringComparison.OrdinalIgnoreCase
        );

    public bool IsUnverifiable(QuestEntry quest) =>
        _byStableKey.TryGetValue(quest.StableKey, out var runtime)
        && runtime.Cycle.Stage == WorkflowStage.Unverifiable;

    private void Evaluate(Runtime runtime, Func<string, int> countItem)
    {
        var trigger = runtime.Quest.WorkflowCycle!.Trigger;
        int current = countItem(trigger.ItemStableKey);
        bool changed = runtime.Cycle.RefreshInventory(current);
        if (!runtime.Cycle.TriggerLatched)
        {
            if (changed)
                Changed?.Invoke(runtime.Quest);
            return;
        }

        runtime.MissingTargetIds.Clear();
        foreach (var pair in runtime.ObservedTargets)
        {
            if (pair.Value.Character == null)
                runtime.MissingTargetIds.Add(pair.Key);
        }
        foreach (int instanceId in runtime.MissingTargetIds)
            runtime.ObservedTargets.Remove(instanceId);
        bool lostObservedTarget = runtime.MissingTargetIds.Count > 0;

        if (runtime.Cycle.RewardSeen)
        {
            if (
                runtime.RewardInstance == null
                || runtime.RewardInstance.gameObject == null
                || !runtime.RewardInstance.gameObject.activeInHierarchy
            )
            {
                MarkUnverifiable(runtime);
                return;
            }
            changed |= runtime.Cycle.UpdatePresence(
                runtime.ObservedTargets.Count,
                lostObservedTarget
            );
            if (changed)
                Changed?.Invoke(runtime.Quest);
            return;
        }

        changed |= runtime.Cycle.UpdatePresence(runtime.ObservedTargets.Count, lostObservedTarget);
        if (changed)
            Changed?.Invoke(runtime.Quest);
    }

    private void MatchObservedCharacter(Character character)
    {
        var candidates = new List<(Runtime Runtime, string? TargetGroup, bool Reward)>();
        foreach (var runtime in _byStableKey.Values)
        {
            if (!runtime.Cycle.TriggerLatched || !IsRuntimeScene(runtime))
                continue;
            var cycle = runtime.Quest.WorkflowCycle!;
            if (
                cycle.RewardContainer != null
                && MatchesCharacter(
                    character,
                    cycle.RewardContainer.StableKey,
                    cycle.RewardContainer.DisplayName
                )
            )
                candidates.Add((runtime, null, true));
            foreach (var target in cycle.Targets)
            {
                if (MatchesCharacter(character, target.StableKey, target.DisplayName))
                    candidates.Add(
                        (runtime, CharacterStableKey.Normalize(target.StableKey), false)
                    );
            }
        }

        var distinctRuntimes = candidates
            .Select(candidate => candidate.Runtime)
            .Distinct()
            .ToList();
        if (distinctRuntimes.Count > 1)
        {
            foreach (var runtime in distinctRuntimes)
                MarkUnverifiable(runtime);
            return;
        }
        if (candidates.Count == 0)
            return;

        var candidate = candidates[0];
        if (candidate.Reward)
            ObserveReward(candidate.Runtime, character);
        else
            ObserveTarget(candidate.Runtime, character, candidate.TargetGroup!);
    }

    private void ObserveTarget(Runtime runtime, Character character, string group)
    {
        int instanceId = character.GetInstanceID();
        if (runtime.ObservedTargets.ContainsKey(instanceId))
            return;
        runtime.ObservedTargets.Add(instanceId, new ObservedTarget(character, group));
        var npc = character.GetComponent<NPC>();
        if (npc != null)
            _entities.Register(npc, group);
        if (runtime.Cycle.ObserveTarget())
            Changed?.Invoke(runtime.Quest);
        _selectedWorkflowKey = runtime.Quest.StableKey;
    }

    private void ObserveReward(Runtime runtime, Character character)
    {
        var reward = runtime.Quest.WorkflowCycle!.RewardContainer!;
        runtime.RewardInstance = character;
        var npc = character.GetComponent<NPC>();
        if (npc != null)
            _entities.Register(npc, reward.StableKey);
        if (runtime.Cycle.ObserveReward())
            Changed?.Invoke(runtime.Quest);
        _selectedWorkflowKey = runtime.Quest.StableKey;
        SaveToConfig();
    }

    private void MatchUnregisteredDeath(Character character, Func<string, int> countItem)
    {
        var matches = new List<(Runtime Runtime, string Group)>();
        foreach (var runtime in _byStableKey.Values)
        {
            if (!runtime.Cycle.TriggerLatched || !IsRuntimeScene(runtime))
                continue;
            foreach (var target in runtime.Quest.WorkflowCycle!.Targets)
            {
                if (MatchesCharacter(character, target.StableKey, target.DisplayName))
                    matches.Add((runtime, CharacterStableKey.Normalize(target.StableKey)));
            }
        }
        var distinct = matches.Select(match => match.Runtime).Distinct().ToList();
        if (distinct.Count != 1 || matches.Count == 0)
        {
            foreach (var runtime in distinct)
                MarkUnverifiable(runtime);
            return;
        }

        var match = matches[0];
        match.Runtime.Cycle.RecordTargetDeath(match.Group, anyLiveTargets: false);
        if (!match.Runtime.Cycle.TargetsDefeated)
        {
            Changed?.Invoke(match.Runtime.Quest);
            return;
        }
        if (match.Runtime.Quest.WorkflowCycle!.RewardContainer == null)
        {
            ResetCycle(match.Runtime, countItem);
            return;
        }
        match.Runtime.Cycle.UpdatePresence(liveTargetCount: 0, lostObservedTarget: false);
        Changed?.Invoke(match.Runtime.Quest);
    }

    private void RevalidateLiveEntities(Func<string, int> countItem)
    {
        if (!IsCurrentWorkflowScene())
            return;
        var live = _findLiveCharacters()
            .Where(character =>
                character != null && character.Alive && character.GetComponent<NPC>() != null
            )
            .ToList();

        foreach (var character in live)
            MatchObservedCharacter(character);

        var sceneRuntimes = _byStableKey.Values.Where(IsRuntimeScene).ToList();
        var signatureCounts = sceneRuntimes
            .GroupBy(TargetSignature, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(
                group => group.Key,
                group => group.Count(),
                StringComparer.OrdinalIgnoreCase
            );
        foreach (var runtime in sceneRuntimes)
        {
            if (
                runtime.Cycle.TriggerLatched
                || runtime.Cycle.Stage == WorkflowStage.RewardAvailable
            )
                continue;
            var signature = TargetSignature(runtime);
            bool anyMatch = runtime.Quest.WorkflowCycle!.Targets.Any(target =>
                live.Any(character =>
                    MatchesCharacter(character, target.StableKey, target.DisplayName)
                )
            );
            if (!anyMatch)
                continue;
            if (signatureCounts[signature] != 1)
            {
                MarkUnverifiable(runtime);
                continue;
            }

            int current = countItem(runtime.Quest.WorkflowCycle.Trigger.ItemStableKey);
            _selectedWorkflowKey = runtime.Quest.StableKey;
            if (runtime.Cycle.RecoverFromLiveTargets(current))
                Changed?.Invoke(runtime.Quest);
            foreach (var character in live)
            {
                foreach (var target in runtime.Quest.WorkflowCycle.Targets)
                {
                    if (MatchesCharacter(character, target.StableKey, target.DisplayName))
                    {
                        ObserveTarget(
                            runtime,
                            character,
                            CharacterStableKey.Normalize(target.StableKey)
                        );
                        break;
                    }
                }
            }
            SaveToConfig();
        }
    }

    private static IReadOnlyList<Character> FindLiveCharacters() =>
        UnityEngine.Object.FindObjectsOfType<Character>();

    /// <summary>
    /// Finish the bounded live-entity recovery window. A latched workflow
    /// without positive target or reward evidence becomes explicitly unavailable
    /// rather than guessing progress from absence.
    /// </summary>
    private void CompleteRecoveryDiscovery()
    {
        foreach (var runtime in _byStableKey.Values)
        {
            bool hasRuntimeEvidence = runtime.ObservedTargets.Count > 0 || runtime.Cycle.RewardSeen;
            if (IsRuntimeScene(runtime) && runtime.Cycle.CompleteRecovery(hasRuntimeEvidence))
                Changed?.Invoke(runtime.Quest);
        }
    }

    private void ResetCycle(Runtime runtime, Func<string, int> countItem)
    {
        int current = countItem(runtime.Quest.WorkflowCycle!.Trigger.ItemStableKey);
        runtime.Cycle.ResetCycle(current);
        runtime.RewardInstance = null;
        runtime.ObservedTargets.Clear();
        runtime.MissingTargetIds.Clear();
        _selectedWorkflowKey = runtime.Quest.StableKey;
        SaveToConfig();
        CycleReset?.Invoke(runtime.Quest);
        Changed?.Invoke(runtime.Quest);
    }

    private static void ResetRuntime(Runtime runtime, int currentItemCount)
    {
        runtime.Cycle.Reset(currentItemCount);
        runtime.RewardInstance = null;
        runtime.ObservedTargets.Clear();
        runtime.MissingTargetIds.Clear();
    }

    private void MarkUnverifiable(Runtime runtime)
    {
        if (runtime.Cycle.MarkUnverifiable())
            Changed?.Invoke(runtime.Quest);
    }

    private bool IsRuntimeScene(Runtime runtime) =>
        string.Equals(
            runtime.Quest.WorkflowCycle!.Trigger.Location.Scene,
            _currentScene,
            StringComparison.OrdinalIgnoreCase
        );

    private bool IsCurrentWorkflowScene() => _byStableKey.Values.Any(IsRuntimeScene);

    private static string TargetSignature(Runtime runtime) => runtime.Cycle.TargetSignature;

    private static bool MatchesCharacter(Character character, string stableKey, string displayName)
    {
        var npc = character.GetComponent<NPC>();
        if (npc == null)
            return false;
        if (string.Equals(npc.NPCName, displayName, StringComparison.OrdinalIgnoreCase))
            return true;
        var runtimeKey = EntityRegistry.DeriveStableKey(npc);
        return runtimeKey != null
            && string.Equals(
                CharacterStableKey.Normalize(runtimeKey),
                CharacterStableKey.Normalize(stableKey),
                StringComparison.OrdinalIgnoreCase
            );
    }

    private void ScheduleDiscovery() => _discovery.Schedule();
}
