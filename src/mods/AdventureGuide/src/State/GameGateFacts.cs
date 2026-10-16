namespace AdventureGuide.State;

/// <summary>Reads the existing quest, inventory and room mirrors and the live keyring.</summary>
public sealed class GameGateFacts : IGateFacts
{
    private readonly QuestStateTracker _state;

    public GameGateFacts(QuestStateTracker state) => _state = state;

    public bool IsQuestCompleted(string questDbName) => _state.IsGameQuestCompleted(questDbName);

    public int ItemCount(string itemStableKey) => _state.CountItem(itemStableKey);

    public bool IsOnKeyring(string gameId) =>
        GameData.Keyring != null && GameData.Keyring.Contains(gameId);

    public string? FurnitureIn(string slot) => _state.Furnishings.ItemKeyIn(slot);
}
