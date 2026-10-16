namespace AdventureGuide.Navigation;

public static class ZoneLineText
{
    public static string Format(string destination, bool locked, string? requirement)
    {
        var text = $"To: {destination}";
        if (!locked)
            return text;
        return string.IsNullOrWhiteSpace(requirement)
            ? text + "\nRoute locked"
            : text + "\n" + requirement;
    }
}
