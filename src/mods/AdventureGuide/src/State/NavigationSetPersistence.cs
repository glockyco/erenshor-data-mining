using AdventureGuide.Config;
using AdventureGuide.Frontier;
using BepInEx.Configuration;

namespace AdventureGuide.State;

/// <summary>
/// Persists the player's selected navigation target set per character slot.
///
/// User-driven selection changes must reach disk immediately so hot reloads,
/// crashes, and scene teardown cannot silently discard the latest choice.
/// Runtime-only clears (for example when leaving gameplay) go through
/// <see cref="UnloadCurrentCharacter"/> so the saved selection survives.
/// </summary>
public sealed class NavigationSetPersistence : IDisposable
{
    private readonly NavigationSet _navSet;
    private readonly GuideConfig _config;

    private ConfigEntry<string>? _entry;
    private int _boundSlotIndex = -1;
    private bool _suppressWrites;

    public NavigationSetPersistence(NavigationSet navSet, GuideConfig config)
    {
        _navSet = navSet;
        _config = config;
        _navSet.Changed += OnNavigationSetChanged;
    }

    public void Dispose() => _navSet.Changed -= OnNavigationSetChanged;

    /// <summary>
    /// Bind to the current character slot and restore its saved selection.
    /// Rebinding saves the outgoing slot first so cross-character switches do
    /// not lose pending in-memory changes.
    /// </summary>
    public void OnCharacterLoaded(CompiledGuide.CompiledGuide guide)
    {
        var slot = GameData.CurrentCharacterSlot;
        if (slot == null) return;
        if (slot.index == _boundSlotIndex) return;

        SaveCurrentSelection();

        _boundSlotIndex = slot.index;
        _entry = _config.BindPerCharacter(slot.index, "NavigationTargets", "");

        var keys = ParseStoredKeys(_entry.Value, guide);
        ApplyWithoutPersist(() => _navSet.Load(keys));
    }

    /// <summary>
    /// Persist the current selection, then clear only the runtime copy.
    /// Use when leaving gameplay or unloading the current character.
    /// </summary>
    public void UnloadCurrentCharacter()
    {
        SaveCurrentSelection();
        _entry = null;
        _boundSlotIndex = -1;
        ApplyWithoutPersist(() => _navSet.Clear());
    }

    public void SaveCurrentSelection()
    {
        if (_entry == null) return;
        _entry.Value = string.Join(";", _navSet.Keys);
    }

    private void OnNavigationSetChanged()
    {
        if (_suppressWrites) return;
        SaveCurrentSelection();
    }

    private void ApplyWithoutPersist(Action action)
    {
        _suppressWrites = true;
        try
        {
            action();
        }
        finally
        {
            _suppressWrites = false;
        }
    }

    private static List<string> ParseStoredKeys(string raw, CompiledGuide.CompiledGuide guide)
    {
        var keys = new List<string>();
        if (string.IsNullOrEmpty(raw))
            return keys;

        foreach (var part in raw.Split(';'))
        {
            var trimmed = part.Trim();
            if (trimmed.Length > 0 && guide.TryGetNodeId(trimmed, out _))
                keys.Add(trimmed);
        }

        return keys;
    }
}
