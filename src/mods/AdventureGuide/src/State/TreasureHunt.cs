using UnityEngine;

namespace AdventureGuide.State;

/// <summary>Cache the manager component; sample its fields without per-frame allocations.</summary>
internal sealed class TreasureHunt
{
    private Component? _manager;
    private TreasureHunting? _hunting;
    public TreasureHuntState State { get; } = new();

    public TreasureHuntChange Poll(string currentScene)
    {
        var manager = GameData.GM;
        if (manager != _manager)
        {
            _manager = manager;
            _hunting = manager != null ? manager.GetComponent<TreasureHunting>() : null;
        }
        if (currentScene is "Menu" or "LoadScene" || _hunting == null)
            return State.Observe("", 0, 0, 0);
        var loc = _hunting.TreasureLoc;
        return State.Observe(_hunting.TreasureZone, loc.x, loc.y, loc.z);
    }

    public void Clear()
    {
        _manager = null;
        _hunting = null;
        State.Observe("", 0, 0, 0);
    }
}
