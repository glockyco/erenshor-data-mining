namespace AdventureGuide.Navigation;

/// <summary>
/// Formats respawn timers for world markers. Markers compare whole
/// display seconds between frames and format a label only when that value
/// changes, so a running timer allocates once per second instead of per frame.
/// </summary>
internal static class RespawnTimerText
{
    /// <summary>Whole seconds a respawn timer shows. Zero means the respawn is due.</summary>
    public static int DisplaySeconds(float seconds) =>
        seconds > 0f ? (int)System.Math.Ceiling(seconds) : 0;

    /// <summary>"~M:SS" below an hour, "~H:MM:SS" from an hour on.</summary>
    public static string Format(int displaySeconds)
    {
        if (displaySeconds < 0)
            displaySeconds = 0;
        int hours = displaySeconds / 3600;
        int minutes = displaySeconds / 60 % 60;
        int seconds = displaySeconds % 60;
        return hours > 0 ? $"~{hours}:{minutes:D2}:{seconds:D2}" : $"~{minutes}:{seconds:D2}";
    }

    /// <summary>Respawn timer label, or <paramref name="dueText"/> once it reaches zero.</summary>
    public static string Timer(int displaySeconds, string dueText) =>
        displaySeconds > 0 ? Format(displaySeconds) : dueText;

    /// <summary>Marker sub-text: the name line, when known, above the status line.</summary>
    public static string WithName(string? name, string status) =>
        string.IsNullOrEmpty(name) ? status : name + "\n" + status;

    /// <summary>Night-only status with the current game time.</summary>
    public static string NightOnly(int hour, int minute) =>
        $"Night only (23:00-04:00)\nNow: {hour}:{minute:D2}";
}
