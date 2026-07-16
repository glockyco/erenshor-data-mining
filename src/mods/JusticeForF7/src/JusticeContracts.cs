namespace JusticeForF7;

/// <summary>Loader-neutral Justice settings consumed by the shared runtime.</summary>
public interface IJusticeSettings
{
    bool Enabled { get; }
    bool EnableLogging { get; }
    int RescanInterval { get; }
    bool HideNameplates { get; }
    bool HideDamageNumbers { get; }
    bool HideTargetRings { get; }
    bool HideXPOrbs { get; }
    bool HideCastBars { get; }
    bool HideOtherWorldText { get; }
}

public interface IModLogger
{
    void LogInfo(string message);
    void LogDebug(string message);
}
