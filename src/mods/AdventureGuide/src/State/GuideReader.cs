using AdventureGuide.Incremental;

namespace AdventureGuide.State;

/// <summary>Erenshor-specific wrapper over <see cref="Engine{TFactKey}"/> with
/// <see cref="FactKey"/>. Typed accessors record the appropriate fact key on
/// the active <see cref="ReadContext{TFactKey}"/> (for deps) and forward to the
/// underlying tracker (for values). Each tracker implements a narrow interface
/// so the wrapper can be unit-tested with fakes.</summary>
public sealed class GuideReader
{
	private readonly Engine<FactKey> _engine;
	private readonly IInventoryFactSource _inventory;
	private ReadContext<FactKey>? _activeContext;

	public GuideReader(Engine<FactKey> engine, IInventoryFactSource inventory)
	{
		_engine = engine;
		_inventory = inventory;
	}

	public Engine<FactKey> Engine => _engine;

	internal void AttachContext(ReadContext<FactKey> ctx) => _activeContext = ctx;
	internal void DetachContext() => _activeContext = null;

	public int ReadInventoryCount(string itemId)
	{
		RequireContext().RecordFact(new FactKey(FactKind.InventoryItemCount, itemId));
		return _inventory.GetCount(itemId);
	}

	// Additional typed accessors (ReadQuestActive, ReadQuestCompleted, ReadScene,
	// ReadSourceState, ReadUnlockItemPossessed, ReadTimeOfDay) follow the same
	// shape and are added in Task 4 as each query needs them.

	private ReadContext<FactKey> RequireContext() =>
		_activeContext ?? throw new InvalidOperationException(
			"GuideReader.Read* called outside a query compute. Use engine.Read at the top level.");
}

public interface IInventoryFactSource
{
	int GetCount(string itemId);
}
