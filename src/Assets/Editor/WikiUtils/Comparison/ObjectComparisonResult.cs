using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;

public sealed class ObjectComparisonResult
{
    public bool AreEqual { get; }
    public IReadOnlyList<ObjectFieldDifference> Differences { get; }

    public ObjectComparisonResult(bool areEqual, IEnumerable<ObjectFieldDifference> differences)
    {
        AreEqual = areEqual;
        Differences = new ReadOnlyCollection<ObjectFieldDifference>(differences.ToList());
    }

    public override string ToString()
    {
        if (AreEqual)
        {
            return "Objects are equal.";
        }

        return "Objects differ in the following fields:\n" + string.Join("\n", Differences.Select(d => d.ToString()));
    }
}