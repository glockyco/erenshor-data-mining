#nullable enable

using SQLite;

[Table("ObjectHierarchy")]
public sealed class ObjectHierarchyRecord
{
    [PrimaryKey]
    public string ObjectKey { get; set; } = "";
    public string? ParentObjectKey { get; set; }
    public string Scene { get; set; } = "";
    public bool ActiveSelf { get; set; }
    public bool IsSceneObject { get; set; }
}
