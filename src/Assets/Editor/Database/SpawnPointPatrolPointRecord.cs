#nullable enable

using SQLite;

[Table("SpawnPointPatrolPoints")]
public class SpawnPointPatrolPointRecord
{
    public const string TableName = "SpawnPointPatrolPoints";

    [Indexed(Name = "SpawnPointPatrolPoints_Primary_IDX", Order = 1, Unique = true)]
    public int SpawnPointId { get; set; }

    [Indexed(Name = "SpawnPointPatrolPoints_Primary_IDX", Order = 2, Unique = true)]
    public int SequenceIndex { get; set; }

    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
}
