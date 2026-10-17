using AdventureGuide.Data;

namespace AdventureGuide.State;

public sealed partial class GateConditions
{
    private bool IsCanonicalSourceAvailable(ItemSource source)
    {
        var fact = source.CanonicalFact;
        if (fact == null)
            return true;
        return SourceGatesHold(fact.AvailabilityGates)
            && (
                source.CanonicalLocation == null
                || SourceGatesHold(source.CanonicalLocation.AvailabilityGates)
            );
    }

    public IReadOnlyList<List<List<GateAtom>>> SourceRequirements(ItemSource source)
    {
        if (source.CanonicalFact == null)
            return Array.Empty<List<List<GateAtom>>>();
        var result = new List<List<List<GateAtom>>>();
        Add(source.CanonicalFact.AvailabilityGates);
        if (source.CanonicalLocation != null)
            Add(source.CanonicalLocation.AvailabilityGates);
        return result;

        void Add(SourceGate[] gates)
        {
            foreach (var gate in gates)
            {
                var groups = new List<List<GateAtom>>();
                foreach (var alternative in gate.Alternatives)
                {
                    var group = new List<GateAtom>();
                    bool possible = true;
                    foreach (var atom in alternative)
                    {
                        if (atom.GuidanceAtom != null)
                            group.Add(atom.GuidanceAtom);
                        else if (!SourceAtomHolds(atom))
                        {
                            possible = false;
                            break;
                        }
                    }
                    if (possible)
                        groups.Add(group);
                }
                if (groups.Count > 0)
                    result.Add(groups);
            }
        }
    }

    public string? CanonicalSourceFailure(ItemSource source)
    {
        if (source.CanonicalFact == null)
            return null;
        return Failure(source.CanonicalFact.AvailabilityGates)
            ?? (
                source.CanonicalLocation == null
                    ? null
                    : Failure(source.CanonicalLocation.AvailabilityGates)
            );

        string? Failure(SourceGate[] gates)
        {
            foreach (var gate in gates)
            {
                bool possible = false;
                SourceCondition? blocked = null;
                foreach (var alternative in gate.Alternatives)
                {
                    bool candidate = true;
                    foreach (var atom in alternative)
                        if (atom.GuidanceAtom == null && !SourceAtomHolds(atom))
                        {
                            candidate = false;
                            blocked ??= atom;
                            break;
                        }
                    possible |= candidate;
                }
                if (!possible)
                    return blocked?.Predicate == "actor_level"
                        ? "This source requires a player level in its stated range."
                        : "This source is not available in the current state.";
            }
            return null;
        }
    }

    private bool SourceGatesHold(SourceGate[] gates)
    {
        for (int i = 0; i < gates.Length; i++)
        {
            var alternatives = gates[i].Alternatives;
            bool satisfied = false;
            for (int group = 0; group < alternatives.Length && !satisfied; group++)
            {
                satisfied = true;
                var atoms = alternatives[group];
                for (int atom = 0; atom < atoms.Length; atom++)
                    if (!SourceAtomHolds(atoms[atom]))
                    {
                        satisfied = false;
                        break;
                    }
            }
            if (!satisfied)
                return false;
        }
        return true;
    }

    private bool SourceAtomHolds(SourceCondition atom) =>
        atom.Predicate switch
        {
            "never" => false,
            "quest_done" => _data.EncounterProjection.IsQuestCompleted(atom.QuestDBName!, Facts),
            "quest_not_done" => !_data.EncounterProjection.IsQuestCompleted(
                atom.QuestDBName!,
                Facts
            ),
            "item_held" => Facts.ItemCount(atom.ReferenceStableKey!) > 0,
            "item_not_owned" => Facts.ItemCount(atom.ReferenceStableKey!) == 0,
            "key_held" => Facts.ItemCount(atom.ReferenceStableKey!) > 0
                || atom.GameId != null && Facts.IsOnKeyring(atom.GameId),
            "room_furnished" or "planning_slot_item" => string.Equals(
                Facts.StoredItemIn(atom.ReferenceSlot!),
                atom.ReferenceStableKey,
                StringComparison.OrdinalIgnoreCase
            ),
            "account_state" => _data.EncounterProjection.ReadAccountState(
                atom.ReferenceStableKey!,
                Facts
            ) == (atom.Value == "true"),
            "actor_level" when atom.Actor == "player" => Within(Facts.PlayerLevel, atom),
            // These describe the source actor, action or encounter, not a player-state unlock.
            "actor_level"
            or "actor_class"
            or "encounter_won"
            or "quality"
            or "route"
            or "zone_use"
            or "source_replenishment"
            or "formula_operand" => true,
            "time_of_day" => throw new InvalidOperationException(
                "Fishing time belongs to operation input, not availability"
            ),
            _ => throw new InvalidOperationException(
                $"Unsupported canonical availability predicate: {atom.Predicate}"
            ),
        };

    private static bool Within(double value, SourceCondition atom) =>
        (
            !atom.Minimum.HasValue
            || (atom.MinimumInclusive ? value >= atom.Minimum.Value : value > atom.Minimum.Value)
        )
        && (
            !atom.Maximum.HasValue
            || (atom.MaximumInclusive ? value <= atom.Maximum.Value : value < atom.Maximum.Value)
        );
}
