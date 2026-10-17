namespace AdventureGuide.Navigation;

public sealed class EntityRegistry
{
    private readonly Dictionary<NPC, string> _registered = new();
    public HashSet<NPC> SpawnPointNpcs { get; } = [];

    public bool IsSpawnPointNpc(NPC npc) => SpawnPointNpcs.Contains(npc);

    public static string? DeriveStableKey(NPC npc) => npc.StableKey;

    public void Register(NPC npc, string stableKey) => _registered[npc] = stableKey;
}
