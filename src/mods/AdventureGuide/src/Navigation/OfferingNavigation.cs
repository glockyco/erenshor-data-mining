using AdventureGuide.Data;

namespace AdventureGuide.Navigation;

internal readonly struct OfferingEndpoint
{
    public string? LiveCharacter { get; }
    public string? MissingItem { get; }
    public string? Instruction { get; }
    public string? Warning { get; }
    public float X { get; }
    public float Y { get; }
    public float Z { get; }

    public OfferingEndpoint(
        string? liveCharacter,
        string? missingItem,
        string? instruction,
        float x,
        float y,
        float z,
        string? warning = null
    )
    {
        LiveCharacter = liveCharacter;
        MissingItem = missingItem;
        Instruction = instruction;
        Warning = warning;
        X = x;
        Y = y;
        Z = z;
    }
}

internal static class OfferingNavigation
{
    // code-fact: chessboard.faceless_choices
    public static OfferingEndpoint Resolve(
        GuideData data,
        AdventureGuide.Data.SpawnPoint spawn,
        ActivationReference reference,
        string character,
        string currentScene,
        Func<string, int> countItem,
        Func<string, bool> isLive
    )
    {
        var activation = data.Activations[reference.Key];
        var offering = activation.Offerings[reference.Offering];
        bool here = string.Equals(
            activation.Scene,
            currentScene,
            StringComparison.OrdinalIgnoreCase
        );
        if (here && isLive(character))
            return new OfferingEndpoint(character, null, null, spawn.X, spawn.Y, spawn.Z);
        if (here && reference.Role == "reward")
            foreach (var member in offering.Spawns)
                if (isLive(member.Character))
                    return new OfferingEndpoint(
                        member.Character,
                        null,
                        member.DefeatInstruction,
                        spawn.X,
                        spawn.Y,
                        spawn.Z
                    );
        bool competing = false;
        foreach (var other in activation.Offerings)
            if (other.ItemStableKey != offering.ItemStableKey && countItem(other.ItemStableKey) > 0)
            {
                competing = true;
                break;
            }
        var position = activation.Site.Bounds.Center;
        return new OfferingEndpoint(
            null,
            countItem(offering.ItemStableKey) > 0 ? null : offering.ItemStableKey,
            competing ? reference.WarningInstruction : reference.Instruction,
            position.X,
            position.Y,
            position.Z,
            competing ? offering.Warning : null
        );
    }
}
