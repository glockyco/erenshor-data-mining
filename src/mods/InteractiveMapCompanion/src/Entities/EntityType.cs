namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Classification of trackable entities in the game world.
/// </summary>
public enum EntityType
{
    /// <summary>
    /// The player character.
    /// </summary>
    Player,

    /// <summary>
    /// AI companion (SimPlayer).
    /// </summary>
    SimPlayer,

    /// <summary>
    /// Player or SimPlayer pet.
    /// </summary>
    Pet,

    /// <summary>
    /// Friendly NPC (positive or neutral faction reputation).
    /// </summary>
    NpcFriendly,

    /// <summary>
    /// Hostile NPC (negative faction reputation or explicitly aggressive).
    /// </summary>
    NpcEnemy,
}
