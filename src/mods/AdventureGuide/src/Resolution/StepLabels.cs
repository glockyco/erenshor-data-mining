namespace AdventureGuide.Resolution;

public static class StepLabels
{
    // Byte constants matching compiler EdgeType ordinals
    public const byte Talk = 2;
    public const byte Kill = 3;
    public const byte Travel = 4;
    public const byte Shout = 5;
    public const byte Read = 6;

    public static string Format(byte stepType, string targetName) =>
        stepType switch
        {
            Talk => $"Talk to {targetName}",
            Kill => $"Kill {targetName}",
            Travel => $"Travel to {targetName}",
            Shout => $"Shout near {targetName}",
            Read => $"Read {targetName}",
            _ => targetName,
        };
}
