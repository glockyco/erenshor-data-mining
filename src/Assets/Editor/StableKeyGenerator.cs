#nullable enable

using System;

/// <summary>
/// Generates stable keys for entity identification.
/// Mirrors the Python implementation in src/erenshor/registry/stable_keys.py
/// </summary>
public static class StableKeyGenerator
{
    /// <summary>
    /// Generate stable key for an item.
    /// Format: "item:resource_name"
    /// </summary>
    public static string ForItem(Item item)
    {
        if (item == null)
            throw new ArgumentNullException(nameof(item));
        if (string.IsNullOrEmpty(item.name))
            throw new ArgumentException("Item.name cannot be null or empty");

        return $"item:{Normalize(item.name)}";
    }

    /// <summary>
    /// Generate stable key for a spell.
    /// Format: "spell:resource_name"
    /// </summary>
    public static string ForSpell(Spell spell)
    {
        if (spell == null)
            throw new ArgumentNullException(nameof(spell));
        if (string.IsNullOrEmpty(spell.name))
            throw new ArgumentException("Spell.name cannot be null or empty");

        return $"spell:{Normalize(spell.name)}";
    }

    /// <summary>
    /// Generate stable key for a skill.
    /// Format: "skill:resource_name"
    /// </summary>
    public static string ForSkill(Skill skill)
    {
        if (skill == null)
            throw new ArgumentNullException(nameof(skill));
        if (string.IsNullOrEmpty(skill.name))
            throw new ArgumentException("Skill.name cannot be null or empty");

        return $"skill:{Normalize(skill.name)}";
    }

    /// <summary>
    /// Generate stable key for a stance.
    /// Format: "stance:resource_name"
    /// </summary>
    public static string ForStance(Stance stance)
    {
        if (stance == null)
            throw new ArgumentNullException(nameof(stance));
        if (string.IsNullOrEmpty(stance.name))
            throw new ArgumentException("Stance.name cannot be null or empty");

        return $"stance:{Normalize(stance.name)}";
    }

    /// <summary>
    /// Generate stable key for a guild topic.
    /// Format: "guildtopic:resource_name"
    /// </summary>
    public static string ForGuildTopic(GuildTopic guildTopic)
    {
        if (guildTopic == null)
            throw new ArgumentNullException(nameof(guildTopic));
        if (string.IsNullOrEmpty(guildTopic.name))
            throw new ArgumentException("GuildTopic.name cannot be null or empty");

        return $"guildtopic:{Normalize(guildTopic.name)}";
    }

    /// <summary>
    /// Generate stable key for an ascension.
    /// Format: "ascension:resource_name"
    /// </summary>
    public static string ForAscension(Ascension ascension)
    {
        if (ascension == null)
            throw new ArgumentNullException(nameof(ascension));
        if (string.IsNullOrEmpty(ascension.name))
            throw new ArgumentException("Ascension.name cannot be null or empty");

        return $"ascension:{Normalize(ascension.name)}";
    }

    /// <summary>
    /// Generate stable key for a quest.
    /// Format: "quest:db_name"
    /// </summary>
    public static string ForQuest(Quest quest)
    {
        if (quest == null)
            throw new ArgumentNullException(nameof(quest));
        if (string.IsNullOrEmpty(quest.DBName))
            throw new ArgumentException("Quest.DBName cannot be null or empty");

        return $"quest:{Normalize(quest.DBName)}";
    }

    /// <summary>
    /// Generate stable key for a faction.
    /// Format: "faction:refname"
    /// </summary>
    public static string ForFaction(WorldFaction faction)
    {
        if (faction == null)
            throw new ArgumentNullException(nameof(faction));
        if (string.IsNullOrEmpty(faction.REFNAME))
            throw new ArgumentException("WorldFaction.REFNAME cannot be null or empty");

        return $"faction:{Normalize(faction.REFNAME)}";
    }

    /// <summary>
    /// Generate stable key for a zone.
    /// Format: "zone:scene"
    /// </summary>
    public static string ForZone(string scene)
    {
        if (string.IsNullOrEmpty(scene))
            throw new ArgumentException("Scene cannot be null or empty", nameof(scene));

        return $"zone:{Normalize(scene)}";
    }

    /// <summary>
    /// Generate stable key for a character.
    /// Prefabs: "character:object_name"
    /// Non-prefabs: "character:object_name:scene:x:y:z"
    /// Variants (duplicates): append ":index" to the key
    /// </summary>
    public static string ForCharacter(Character character, int variantIndex = 0)
    {
        if (character == null)
            throw new ArgumentNullException(nameof(character));
        if (string.IsNullOrEmpty(character.name))
            throw new ArgumentException("Character.name cannot be null or empty");

        var normalizedObjectName = Normalize(character.name);
        string baseKey;

        // Check if prefab by scene name (null for prefabs in AssetRipper projects)
        if (character.gameObject.scene.name == null)
        {
            // Prefab: simple key
            baseKey = $"character:{normalizedObjectName}";
        }
        else
        {
            // Non-prefab: include coordinates
            var normalizedSceneName = Normalize(character.gameObject.scene.name);
            var xStr = FormatCoord(character.transform.position.x);
            var yStr = FormatCoord(character.transform.position.y);
            var zStr = FormatCoord(character.transform.position.z);
            baseKey = $"character:{normalizedObjectName}:{normalizedSceneName}:{xStr}:{yStr}:{zStr}";
        }

        // Append variant index if this is a duplicate
        return variantIndex > 0 ? $"{baseKey}:{variantIndex}" : baseKey;
    }

    /// <summary>
    /// Generate stable key for a quest from DBName string.
    /// Use this when you have the quest DBName but not the Quest object.
    /// Format: "quest:db_name"
    /// </summary>
    public static string ForQuestFromDBName(string questDBName)
    {
        if (string.IsNullOrEmpty(questDBName))
            throw new ArgumentException("questDBName cannot be null or empty");

        return $"quest:{Normalize(questDBName)}";
    }

    /// <summary>
    /// Generate stable key for a zone from scene name string.
    /// Use this when you have the scene name but not the ZoneAnnounce object.
    /// Format: "zone:scene"
    /// </summary>
    public static string ForZoneFromSceneName(string sceneName)
    {
        if (string.IsNullOrEmpty(sceneName))
            throw new ArgumentException("sceneName cannot be null or empty");

        return $"zone:{Normalize(sceneName)}";
    }

    /// <summary>
    /// Generate stable key for an item from resource name string.
    /// Use this when you have the resource name but not the Item object.
    /// Format: "item:resource_name"
    /// </summary>
    public static string ForItemFromResourceName(string resourceName)
    {
        if (string.IsNullOrEmpty(resourceName))
            throw new ArgumentException("resourceName cannot be null or empty");

        return $"item:{Normalize(resourceName)}";
    }

    /// <summary>
    /// Format a coordinate value to 2 decimal places.
    /// </summary>
    private static string FormatCoord(float value)
    {
        return value.ToString("F2");
    }

    /// <summary>
    /// Normalize a resource name to lowercase with trimmed whitespace.
    /// Mirrors normalize_resource_name() in Python.
    /// </summary>
    private static string Normalize(string value)
    {
        return value.Trim().ToLowerInvariant();
    }
}
