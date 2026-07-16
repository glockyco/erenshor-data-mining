namespace Sprint.Config;

/// <summary>
/// Loader-neutral settings consumed by the shared sprint lifecycle.
/// </summary>
internal interface ISprintSettings
{
    bool Enabled { get; }

    bool ToggleMode { get; }

    float Multiplier { get; }
}
