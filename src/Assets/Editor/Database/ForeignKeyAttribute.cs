using System;

/// <summary>
/// Marks a property as a foreign key reference to another table.
/// Used by TableCreator to generate proper REFERENCES clauses in CREATE TABLE statements.
/// </summary>
[AttributeUsage(AttributeTargets.Property)]
public class ForeignKeyAttribute : Attribute
{
    public Type ReferenceType { get; set; }
    public string ReferenceProperty { get; set; }

    public ForeignKeyAttribute(Type referenceType, string referenceProperty)
    {
        ReferenceType = referenceType;
        ReferenceProperty = referenceProperty;
    }
}
