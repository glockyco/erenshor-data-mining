namespace AdventureGuide.CompiledGuide;

internal static class BinaryFormat
{
    public const uint Magic = 0x47434741; // 'AGCG' little-endian
    public const ushort Version = 1;
}

internal enum SectionId : byte
{
    StringTable = 0,
    NodeTable = 1,
    EdgeTable = 2,
    ForwardAdjacency = 3,
    ReverseAdjacency = 4,
    QuestSpecs = 5,
    ItemSourceIndex = 6,
    UnlockPredicates = 7,
    TopologicalOrder = 8,
    ReverseDeps = 9,
    ZoneConnectivity = 10,
    QuestGiverBlueprints = 11,
    QuestCompletionBlueprints = 12,
    Feasibility = 13,
}

public readonly struct NodeRecord(
    uint keyOffset,
    byte nodeType,
    uint displayNameOffset,
    uint sceneOffset,
    float x,
    float y,
    float z,
    ushort flags,
    ushort level,
    uint zoneKeyOffset,
    uint dbNameOffset)
{
    public uint KeyOffset { get; } = keyOffset;
    public byte NodeType { get; } = nodeType;
    public uint DisplayNameOffset { get; } = displayNameOffset;
    public uint SceneOffset { get; } = sceneOffset;
    public float X { get; } = x;
    public float Y { get; } = y;
    public float Z { get; } = z;
    public ushort Flags { get; } = flags;
    public ushort Level { get; } = level;
    public uint ZoneKeyOffset { get; } = zoneKeyOffset;
    public uint DbNameOffset { get; } = dbNameOffset;
}

public readonly struct EdgeRecord(
    ushort sourceId,
    ushort targetId,
    byte edgeType,
    byte flags,
    uint groupOffset,
    byte ordinal,
    ushort quantity,
    uint keywordOffset,
    ushort chance)
{
    public ushort SourceId { get; } = sourceId;
    public ushort TargetId { get; } = targetId;
    public byte EdgeType { get; } = edgeType;
    public byte Flags { get; } = flags;
    public uint GroupOffset { get; } = groupOffset;
    public byte Ordinal { get; } = ordinal;
    public ushort Quantity { get; } = quantity;
    public uint KeywordOffset { get; } = keywordOffset;
    public ushort Chance { get; } = chance;
}

[System.Flags]
internal enum NodeFlags : ushort
{
    IsFriendly = 1 << 0,
    IsVendor = 1 << 1,
    NightSpawn = 1 << 2,
    Implicit = 1 << 3,
    Repeatable = 1 << 4,
    Disabled = 1 << 5,
    IsDirectlyPlaced = 1 << 6,
    IsEnabled = 1 << 7,
    Invulnerable = 1 << 8,
    IsRare = 1 << 9,
    IsTriggerSpawn = 1 << 10,
}
