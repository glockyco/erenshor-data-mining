namespace AdventureGuide.State;

/// <summary>Reads raw tracker primitives, quest and inventory mirrors, stored slots and the live keyring.</summary>
public sealed class GameGateFacts : IGateFacts
{
    private readonly QuestStateTracker _state;

    public GameGateFacts(QuestStateTracker state) => _state = state;

    public bool IsQuestCompleted(string questDbName) => _state.IsGameQuestCompleted(questDbName);

    public bool ReadAccountState(string key) => _state.ReadAccountState(key);

    public string? ReadCharacterZoneState(string key) => _state.ReadCharacterZoneState(key);

    public UnityEngine.Vector3? ReadCharacterPositionState(string key) =>
        _state.ReadCharacterPositionState(key);

    public int PlayerLevel => _state.PlayerLevel;

    public int ItemCount(string itemStableKey) => _state.CountItem(itemStableKey);

    public bool IsOnKeyring(string gameId) =>
        GameData.Keyring != null && GameData.Keyring.Contains(gameId);

    public string? StoredItemIn(string slot) => _state.Furnishings.ItemKeyIn(slot);
}
