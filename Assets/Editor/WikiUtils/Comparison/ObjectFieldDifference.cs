public sealed class ObjectFieldDifference
{
    public string FieldName { get; }
    public object ValueA { get; }
    public object ValueB { get; }

    public ObjectFieldDifference(string fieldName, object valueA, object valueB)
    {
        FieldName = fieldName;
        ValueA = valueA;
        ValueB = valueB;
    }

    public override string ToString() => $"{FieldName}: '{ValueA ?? "null"}' vs '{ValueB ?? "null"}'";
}