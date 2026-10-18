using System.Globalization;
using System.Runtime.CompilerServices;
using System.Text;

namespace AdventureGuide.Data;

/// <summary>An acquisition in one material-use context, retaining its actual endpoints.</summary>
public sealed class SourceChoice
{
    private static readonly ConditionalWeakTable<List<ItemSource>, ChoiceList> Cache = new();
    private readonly HashSet<ItemSource>? _members;

    public ItemSource Primary => Members[0];
    public IReadOnlyList<ItemSource> Members { get; }
    public IReadOnlyList<SourceChoiceLocation> Locations { get; }

    private SourceChoice(List<ItemSource> members)
    {
        Members = members.AsReadOnly();
        if (members.Count > 1)
            _members = new HashSet<ItemSource>(members);
        var locations = new List<List<ItemSource>>();
        foreach (var source in members)
        {
            List<ItemSource>? matching = null;
            foreach (var location in locations)
                if (SamePhysicalLocation(location[0], source))
                {
                    matching = location;
                    break;
                }
            if (matching == null)
                locations.Add(new List<ItemSource> { source });
            else
                matching.Add(source);
        }
        var result = new SourceChoiceLocation[locations.Count];
        for (int i = 0; i < result.Length; i++)
            result[i] = new SourceChoiceLocation(locations[i]);
        Locations = Array.AsReadOnly(result);
    }

    public bool Contains(ItemSource source) =>
        _members?.Contains(source) ?? ReferenceEquals(Primary, source);

    // Keys are original immutable DTO lists. Their projections disappear with those lists.
    public static IReadOnlyList<SourceChoice> ForSources(List<ItemSource>? sources) =>
        sources == null ? Array.Empty<SourceChoice>() : Cache.GetValue(sources, Build).Choices;

    public static SourceChoice? FindContaining(List<ItemSource>? sources, ItemSource source)
    {
        foreach (var choice in ForSources(sources))
            if (choice.Contains(source))
                return choice;
        if (sources != null)
            foreach (var parent in sources)
                if (FindContaining(parent.Children, source) is SourceChoice found)
                    return found;
        return null;
    }

    private static ChoiceList Build(List<ItemSource> sources)
    {
        var groups = new List<List<ItemSource>>();
        var acquisitions = new Dictionary<string, List<List<ItemSource>>>(StringComparer.Ordinal);
        foreach (var source in sources)
        {
            List<ItemSource>? matching = null;
            if (!string.IsNullOrEmpty(source.AcquisitionKey))
            {
                if (!acquisitions.TryGetValue(source.AcquisitionKey!, out var contexts))
                    acquisitions.Add(source.AcquisitionKey!, contexts = new());
                foreach (var context in contexts)
                    if (SameUseContext(context[0], source))
                    {
                        matching = context;
                        break;
                    }
                if (matching == null)
                {
                    matching = new List<ItemSource>();
                    contexts.Add(matching);
                    groups.Add(matching);
                }
            }
            else
            {
                matching = new List<ItemSource>();
                groups.Add(matching);
            }
            matching.Add(source);
        }
        var choices = new SourceChoice[groups.Count];
        for (int i = 0; i < choices.Length; i++)
            choices[i] = new SourceChoice(groups[i]);
        return new ChoiceList(Array.AsReadOnly(choices));
    }

    private sealed class ChoiceList
    {
        public IReadOnlyList<SourceChoice> Choices { get; }

        public ChoiceList(IReadOnlyList<SourceChoice> choices) => Choices = choices;
    }

    private static bool SameUseContext(ItemSource a, ItemSource b) =>
        a.UseKey == b.UseKey
        && a.ItemStableKey == b.ItemStableKey
        && a.OutputQuality == b.OutputQuality
        && a.Quantity == b.Quantity
        && a.Condition == b.Condition
        && a.Type == b.Type
        && a.RecipeKey == b.RecipeKey
        && a.QuestKey == b.QuestKey
        && SameStrings(a.OperationUseKeys, b.OperationUseKeys)
        && SameChildUses(a.Children, b.Children);

    private static bool SameChildUses(List<ItemSource>? a, List<ItemSource>? b)
    {
        if (ReferenceEquals(a, b))
            return true;
        if ((a?.Count ?? 0) != (b?.Count ?? 0))
            return false;
        if (a == null || b == null)
            return true;
        // Candidate acquisitions are not material-use identities. Native slot keys are.
        for (int i = 0; i < a.Count; i++)
        {
            int left = 0;
            int right = 0;
            for (int j = 0; j < a.Count; j++)
            {
                if (SameUseContext(a[j], a[i]))
                    left++;
                if (SameUseContext(b[j], a[i]))
                    right++;
            }
            if (left != right)
                return false;
        }
        return true;
    }

    private static bool SamePhysicalLocation(ItemSource a, ItemSource b)
    {
        var x = a.CanonicalLocation;
        var y = b.CanonicalLocation;
        if (
            x == null
            || y == null
            || string.IsNullOrEmpty(x.SourceCopyStableKey)
            || x.SourceCopyStableKey != y.SourceCopyStableKey
            || string.IsNullOrEmpty(x.Scene)
            || x.Scene != y.Scene
            || x.ZoneStableKey != y.ZoneStableKey
            || x.Relation != y.Relation
            || !Finite(x.X)
            || !Finite(x.Y)
            || !Finite(x.Z)
            || x.X != y.X
            || x.Y != y.Y
            || x.Z != y.Z
            || x.PlayerLevelMin != y.PlayerLevelMin
            || x.PlayerLevelMax != y.PlayerLevelMax
            || a.Scene != b.Scene
            || a.Zone != b.Zone
            || a.X != b.X
            || a.Y != b.Y
            || a.Z != b.Z
            || a.Level != b.Level
            || a.LevelMax != b.LevelMax
            || a.Instruction != b.Instruction
            || a.Keyword != b.Keyword
            || a.TimeRestriction != b.TimeRestriction
            || a.Chance != b.Chance
            || a.ChanceMax != b.ChanceMax
            || a.DayChance != b.DayChance
            || a.NightChance != b.NightChance
            || !SameStrings(a.EntryZoneLineKeys, b.EntryZoneLineKeys)
            || !SameStrings(x.EntryZoneLineKeys, y.EntryZoneLineKeys)
        )
            return false;

        // Scope rebinding is safe only after the actor and physical context agree.
        return ConditionsKey(x.Conditions, x) == ConditionsKey(y.Conditions, y)
            && ConditionsKey(a.CanonicalFact?.Conditions, x)
                == ConditionsKey(b.CanonicalFact?.Conditions, y)
            && ConditionsKey(a.CanonicalUse?.Conditions, x)
                == ConditionsKey(b.CanonicalUse?.Conditions, y);
    }

    private static bool Finite(float? value) =>
        value.HasValue && !float.IsNaN(value.Value) && !float.IsInfinity(value.Value);

    private static bool SameStrings(IReadOnlyList<string>? a, IReadOnlyList<string>? b)
    {
        if (ReferenceEquals(a, b))
            return true;
        int count = a?.Count ?? 0;
        if (count != (b?.Count ?? 0))
            return false;
        for (int i = 0; i < count; i++)
        {
            int left = 0;
            int right = 0;
            for (int j = 0; j < count; j++)
            {
                if (a![j] == a[i])
                    left++;
                if (b![j] == a[i])
                    right++;
            }
            if (left != right)
                return false;
        }
        return true;
    }

    private static bool OwnScope(string scope, SourceLocation location) =>
        !string.IsNullOrEmpty(scope)
        && (
            scope == location.LocationKey
            || scope == location.PlacementKey
            || scope == location.GateScope
        );

    private static string ConditionsKey(List<SourceCondition>? conditions, SourceLocation location)
    {
        if (conditions == null || conditions.Count == 0)
            return "";
        var families = new Dictionary<(string Scope, string Gate), Dictionary<int, List<string>>>();
        foreach (var atom in conditions)
        {
            bool own = OwnScope(atom.Scope, location);
            var family = (atom.Scope, atom.GateKey);
            if (!families.TryGetValue(family, out var groups))
                families.Add(family, groups = new());
            if (!groups.TryGetValue(atom.GroupIndex, out var atoms))
                groups.Add(atom.GroupIndex, atoms = new());
            var key = new StringBuilder();
            Field(key, atom.Predicate);
            Field(key, atom.ReferenceStableKey);
            Field(key, atom.ReferenceSlot);
            Field(key, atom.Actor);
            Field(key, atom.Value);
            Field(key, atom.Minimum?.ToString("R", CultureInfo.InvariantCulture));
            Field(key, atom.Maximum?.ToString("R", CultureInfo.InvariantCulture));
            key.Append(atom.MinimumInclusive ? '1' : '0');
            key.Append(atom.MaximumInclusive ? '1' : '0');
            key.Append(own ? '1' : '0');
            Field(key, own ? null : atom.Scope);
            Field(key, atom.Phase);
            atoms.Add(key.ToString());
        }
        var familyKeys = new List<string>(families.Count);
        foreach (var groups in families.Values)
        {
            var groupKeys = new List<string>(groups.Count);
            foreach (var atoms in groups.Values)
                groupKeys.Add(SortedKey(atoms));
            familyKeys.Add(SortedKey(groupKeys));
        }
        // AND families, OR groups, AND atoms. Only provenance labels disappear.
        return SortedKey(familyKeys);
    }

    private static string SortedKey(List<string> values)
    {
        values.Sort(StringComparer.Ordinal);
        var key = new StringBuilder();
        foreach (string value in values)
            Field(key, value);
        return key.ToString();
    }

    private static void Field(StringBuilder key, string? value)
    {
        if (value == null)
            key.Append("-1:");
        else
            key.Append(value.Length.ToString(CultureInfo.InvariantCulture))
                .Append(':')
                .Append(value);
    }
}

public sealed class SourceChoiceLocation
{
    public ItemSource Primary => Members[0];
    public IReadOnlyList<ItemSource> Members { get; }

    internal SourceChoiceLocation(List<ItemSource> members) => Members = members.AsReadOnly();
}
