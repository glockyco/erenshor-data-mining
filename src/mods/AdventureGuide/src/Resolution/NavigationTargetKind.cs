namespace AdventureGuide.Resolution;

public enum NavigationTargetKind
{
    Unknown,
    Character,
    Enemy,
    Item,
    Quest,
    Zone,
    ZoneLine,
    Object,
    // RotChest game object spawned at a previous corpse position on zone reentry.
    LootChest,
}
