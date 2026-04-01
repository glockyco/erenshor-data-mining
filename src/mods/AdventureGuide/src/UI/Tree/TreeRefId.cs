namespace AdventureGuide.UI.Tree;

/// <summary>
/// Stable identifier for one visual occurrence of a canonical plan node in a
/// quest tree session.
/// </summary>
public readonly struct TreeRefId
{
    public string Value { get; }

    public TreeRefId(string value)
    {
        Value = value ?? string.Empty;
    }

    public override string ToString() => Value;

    public override int GetHashCode() => Value.GetHashCode();

    public override bool Equals(object? obj) =>
        obj is TreeRefId other && string.Equals(Value, other.Value, System.StringComparison.Ordinal);

    public static bool operator ==(TreeRefId left, TreeRefId right) => left.Equals(right);
    public static bool operator !=(TreeRefId left, TreeRefId right) => !left.Equals(right);

    public static implicit operator TreeRefId(string value) => new(value);
}