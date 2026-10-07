namespace AdventureGuide.Navigation;

public static class ZoneLineText
{
    public static string Format(string destination, bool locked, string? requiredQuest)
    {
        var text = $"To: {destination}";
        if (!locked)
            return text;
        return string.IsNullOrWhiteSpace(requiredQuest)
            ? text + "\nRoute locked"
            : text + $"\nRequires: Complete \"{requiredQuest}\"";
    }
}
