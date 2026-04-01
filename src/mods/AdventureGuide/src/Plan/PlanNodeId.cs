namespace AdventureGuide.Plan;

/// <summary>
/// Stable identifier for nodes in a canonical <see cref="QuestPlan"/>.
/// Entity nodes typically use their graph node key; synthetic group nodes use
/// a builder-generated key in the same ID space.
/// </summary>
public readonly struct PlanNodeId
{
    public string Value { get; }

    public PlanNodeId(string value)
    {
        Value = value ?? string.Empty;
    }

    public override string ToString() => Value;

    public override int GetHashCode() => Value.GetHashCode();

    public override bool Equals(object? obj) =>
        obj is PlanNodeId other && string.Equals(Value, other.Value, System.StringComparison.Ordinal);

    public static bool operator ==(PlanNodeId left, PlanNodeId right) => left.Equals(right);
    public static bool operator !=(PlanNodeId left, PlanNodeId right) => !left.Equals(right);

    public static implicit operator PlanNodeId(string value) => new(value);
}