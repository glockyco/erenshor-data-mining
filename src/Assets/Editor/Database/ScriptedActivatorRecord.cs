#nullable enable

using SQLite;

[Table("ScriptedActivators")]
public sealed class ScriptedActivatorRecord
{
    [PrimaryKey]
    public string SourceKey { get; set; } = "";
    public string RuleId { get; set; } = "";
    public string Script { get; set; } = "";
    public string ObjectKey { get; set; } = "";
    public string? SourceScene { get; set; }
    public string SourceObjectName { get; set; } = "";
    public float? X { get; set; }
    public float? Y { get; set; }
    public float? Z { get; set; }
    public bool IsEnabled { get; set; }
    public bool ComponentIsEnabled { get; set; }
    public string? HostCharacterStableKey { get; set; }
}

[Table("ScriptedActivatorReferences")]
public sealed class ScriptedActivatorReferenceRecord
{
    [PrimaryKey]
    public string ReferenceId { get; set; } = "";
    public string SourceKey { get; set; } = "";
    public string Field { get; set; } = "";
    public int ReferenceIndex { get; set; }
    public string ReferenceKind { get; set; } = "";
    public string? ReferenceKey { get; set; }
    public bool? BoolValue { get; set; }
}

[Table("ScriptedActivatorTargets")]
public sealed class ScriptedActivatorTargetRecord
{
    [PrimaryKey]
    public string TargetId { get; set; } = "";
    public string ReferenceId { get; set; } = "";
    public string ResolutionMode { get; set; } = "";
    public string Kind { get; set; } = "";
    public string Key { get; set; } = "";
    public string ObjectKey { get; set; } = "";
    public string Scene { get; set; } = "";
    public string ObjectName { get; set; } = "";
    public bool IsEnabled { get; set; }
}
