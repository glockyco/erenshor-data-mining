using UnityEngine;

namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Production implementation that classifies Characters based on game state.
/// Respects dynamic faction reputation changes.
/// </summary>
public sealed class EntityClassifier : IEntityClassifier
{
    public EntityType? Classify(Character character)
    {
        if (character == null)
            return null;

        // Exclude mining nodes - they're static and not interesting for live tracking
        if (character.MiningNode)
            return null;

        // Exclude treasure chests - also static
        if (character.MyNPC?.TreasureChest == true)
            return null;

        // Player - identified via GameData.PlayerControl
        if (GameData.PlayerControl?.Myself == character)
            return EntityType.Player;

        // Pet - has a master
        if (character.Master != null)
            return EntityType.Pet;

        // SimPlayer - AI companion, has SimPlayer component
        if (character.GetComponent<SimPlayer>() != null)
            return EntityType.SimPlayer;

        // NPC - determine friendly/hostile based on current faction reputation
        if (IsHostileToPlayer(character))
            return EntityType.NpcEnemy;

        return EntityType.NpcFriendly;
    }

    /// <summary>
    /// Determines if an NPC is currently hostile to the player.
    /// This is dynamic and can change based on faction reputation.
    /// </summary>
    private static bool IsHostileToPlayer(Character character)
    {
        // Check if explicitly aggressive toward player factions
        if (character.AggressiveTowards != null)
        {
            if (character.AggressiveTowards.Contains(Character.Faction.Player) ||
                character.AggressiveTowards.Contains(Character.Faction.PC))
            {
                return true;
            }
        }

        // Check world faction reputation - negative value means hostile
        if (character.MyWorldFaction != null &&
            character.MyWorldFaction.FactionValue <= 0f)
        {
            return true;
        }

        return false;
    }
}
