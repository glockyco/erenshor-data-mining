using AdventureGuide.Data;

namespace AdventureGuide.State;

public interface IGateFacts
{
    bool IsQuestCompleted(string questDbName);
    bool ReadAccountState(string key);
    string? ReadCharacterZoneState(string key);
    UnityEngine.Vector3? ReadCharacterPositionState(string key);
    int PlayerLevel { get; }
    int ItemCount(string itemStableKey);
    bool IsOnKeyring(string gameId);
    string? StoredItemIn(string slot);
}

/// <summary>OR groups of AND atoms, with encounter atoms retained as guidance.</summary>
public sealed partial class GateConditions
{
    private readonly GuideData _data;
    private readonly Dictionary<string, string> _characterNames = new(
        StringComparer.OrdinalIgnoreCase
    );
    public Func<ItemSource, bool> IsSourceAvailablePredicate { get; }
    public IGateFacts Facts { get; }

    public GateConditions(GuideData data, IGateFacts facts)
    {
        _data = data;
        IsSourceAvailablePredicate = IsSourceAvailable;
        Facts = facts;
        foreach (var quest in data.All)
        {
            if (quest.Steps == null)
                continue;
            foreach (var step in quest.Steps)
            {
                if (step.TargetKey != null && step.TargetName != null)
                    _characterNames[step.TargetKey] = step.TargetName;
                ReadSourceNames(step.Sources);
            }
        }
        foreach (var item in data.GateItems.Values)
            ReadSourceNames(item.Sources);
    }

    private void ReadSourceNames(List<ItemSource>? sources)
    {
        if (sources == null)
            return;
        for (int i = 0; i < sources.Count; i++)
        {
            var source = sources[i];
            if (source.SourceKey != null && source.Name != null)
                _characterNames[source.SourceKey] = source.Name;
            ReadSourceNames(source.Children);
        }
    }

    public bool IsProjectedQuestCompleted(QuestEntry quest) =>
        _data.EncounterProjection.IsBoundQuest(quest.DBName)
        && _data.EncounterProjection.IsQuestCompleted(quest.DBName, Facts);

    public bool Holds(GateAtom atom) =>
        atom.Kind switch
        {
            GateAtomKind.QuestDone => _data.EncounterProjection.IsQuestCompleted(atom.Ref, Facts),
            GateAtomKind.QuestNotDone => !_data.EncounterProjection.IsQuestCompleted(
                atom.Ref,
                Facts
            ),
            GateAtomKind.AccountState => _data.EncounterProjection.ReadAccountState(atom.Ref, Facts)
                == (atom.Value == "true"),
            GateAtomKind.ItemHeld => Facts.ItemCount(atom.Ref) > 0,
            GateAtomKind.KeyHeld => Facts.ItemCount(atom.Ref) > 0
                || (atom.GameId != null && Facts.IsOnKeyring(atom.GameId)),
            GateAtomKind.RoomFurnished or GateAtomKind.PlanningSlotItem => atom.Slot != null
                && string.Equals(
                    Facts.StoredItemIn(atom.Slot),
                    atom.Ref,
                    StringComparison.OrdinalIgnoreCase
                ),
            GateAtomKind.EncounterWon => true,
            _ => throw new InvalidOperationException($"Unknown gate atom kind '{atom.Kind}'"),
        };

    public bool IsAvailable(int? condition)
    {
        if (!condition.HasValue)
            return true;
        var groups = _data.Conditions[condition.Value];
        for (int i = 0; i < groups.Count; i++)
        {
            var group = groups[i];
            bool holds = true;
            for (int j = 0; j < group.Count; j++)
                if (!Holds(group[j]))
                {
                    holds = false;
                    break;
                }
            if (holds)
                return true;
        }
        return false;
    }

    public bool CanBecomeAvailable(int? condition)
    {
        if (!condition.HasValue)
            return true;
        foreach (var group in _data.Conditions[condition.Value])
        {
            bool possible = true;
            foreach (var atom in group)
                if (
                    (
                        atom.Kind == GateAtomKind.QuestNotDone
                        || (atom.Kind == GateAtomKind.AccountState && atom.Value == "false")
                    ) && !Holds(atom)
                )
                {
                    possible = false;
                    break;
                }
            if (possible)
                return true;
        }
        return false;
    }

    public bool IsSpawnAvailable(AdventureGuide.Data.SpawnPoint spawn) =>
        IsAvailable(spawn.Condition);

    public bool IsCharacterAvailable(string characterKey)
    {
        if (!_data.CharacterSpawns.TryGetValue(characterKey, out var spawns) || spawns.Count == 0)
            return true;
        for (int i = 0; i < spawns.Count; i++)
            if (IsSpawnAvailable(spawns[i]))
                return true;
        return false;
    }

    public bool IsSourceAvailable(ItemSource source) =>
        IsAvailable(source.Condition)
        && IsCanonicalSourceAvailable(source)
        && (
            source.AcquisitionKey != null
                ? source.CanonicalSpawn == null || IsSpawnAvailable(source.CanonicalSpawn)
                : source.SourceKey == null || IsCharacterAvailable(source.SourceKey)
        );

    public bool UsesFurnishings(int? condition)
    {
        if (!condition.HasValue)
            return false;
        var groups = _data.Conditions[condition.Value];
        for (int i = 0; i < groups.Count; i++)
        for (int j = 0; j < groups[i].Count; j++)
            if (groups[i][j].Kind == GateAtomKind.RoomFurnished)
                return true;
        return false;
    }

    public bool CharacterUsesFurnishings(string characterKey)
    {
        if (!_data.CharacterSpawns.TryGetValue(characterKey, out var spawns))
            return false;
        for (int i = 0; i < spawns.Count; i++)
            if (UsesFurnishings(spawns[i].Condition))
                return true;
        return false;
    }

    // Prefer a holding alternative, then the fewest unmet observable atoms.
    // Explanations are built only for display, never by availability checks.
    public IReadOnlyList<GateAtom> Explain(int? condition)
    {
        if (!condition.HasValue)
            return Array.Empty<GateAtom>();
        var groups = _data.Conditions[condition.Value];
        List<GateAtom>? best = null;
        int bestMissing = int.MaxValue;
        for (int i = 0; i < groups.Count; i++)
        {
            int missing = Missing(groups[i]);
            if (missing < bestMissing)
            {
                best = groups[i];
                bestMissing = missing;
            }
        }
        if (best == null)
            return Array.Empty<GateAtom>();
        var result = new List<GateAtom>();
        for (int i = 0; i < best.Count; i++)
            if (best[i].Kind != GateAtomKind.EncounterWon && !Holds(best[i]))
                result.Add(best[i]);
        for (int i = 0; i < groups.Count; i++)
        for (int j = 0; j < groups[i].Count; j++)
        {
            var atom = groups[i][j];
            if (atom.Kind != GateAtomKind.EncounterWon)
                continue;
            bool duplicate = false;
            for (int k = 0; k < result.Count; k++)
                if (result[k].Kind == atom.Kind && result[k].Ref == atom.Ref)
                {
                    duplicate = true;
                    break;
                }
            if (!duplicate)
                result.Add(atom);
        }
        return result;
    }

    private int Missing(List<GateAtom> group)
    {
        int missing = 0;
        for (int i = 0; i < group.Count; i++)
            if (!Holds(group[i]))
                missing++;
        return missing;
    }

    public IReadOnlyList<GateAtom> ExplainCharacter(string characterKey)
    {
        if (!_data.CharacterSpawns.TryGetValue(characterKey, out var spawns))
            return Array.Empty<GateAtom>();
        int? best = null;
        int bestMissing = int.MaxValue;
        for (int i = 0; i < spawns.Count; i++)
        {
            var condition = spawns[i].Condition;
            if (!condition.HasValue)
                return Array.Empty<GateAtom>();
            var groups = _data.Conditions[condition.Value];
            for (int j = 0; j < groups.Count; j++)
            {
                int missing = Missing(groups[j]);
                if (missing < bestMissing)
                {
                    best = condition;
                    bestMissing = missing;
                }
            }
        }
        return Explain(best);
    }

    public string Describe(GateAtom atom)
    {
        if (atom.Kind == GateAtomKind.PlanningSlotItem)
            return atom.Instruction
                ?? throw new InvalidOperationException("Planning slot atom has no instruction");
        string name =
            _data.GetByDBName(atom.Ref)?.DisplayName
            ?? _data.GetByStableKey(atom.Ref)?.DisplayName
            ?? (
                _data.GateItems.TryGetValue(atom.Ref, out var item) ? item.Name
                : _characterNames.TryGetValue(atom.Ref, out var characterName) ? characterName
                : ReferenceName(atom.Ref)
            );
        return atom.Kind switch
        {
            GateAtomKind.QuestDone => "Complete " + name,
            GateAtomKind.QuestNotDone => "Before completing " + name,
            GateAtomKind.ItemHeld => DescribeItemRequirement(atom.Ref, name),
            GateAtomKind.KeyHeld => DescribeItemRequirement(atom.Ref, name),
            GateAtomKind.RoomFurnished => name + " in a Reliquary room",
            GateAtomKind.AccountState => atom.Value == "false"
                ? "Before claiming your Reliquary"
                : "Claim your Reliquary",
            GateAtomKind.EncounterWon => "Defeat " + name + " first",
            _ => throw new InvalidOperationException($"Unknown gate atom kind '{atom.Kind}'"),
        };
    }

    private string DescribeItemRequirement(string reference, string name) =>
        _data.GateItems.TryGetValue(reference, out var item) && item.DoorZones is { Count: > 0 }
            ? "Requires " + name + " (opens a door in " + string.Join(" or ", item.DoorZones) + ")"
            : "Requires " + name;

    private static string ReferenceName(string reference)
    {
        int start = reference.IndexOf(':') + 1;
        int end = reference.IndexOf(':', start);
        string name =
            end < 0 ? reference.Substring(start) : reference.Substring(start, end - start);
        return System.Globalization.CultureInfo.InvariantCulture.TextInfo.ToTitleCase(name);
    }
}
