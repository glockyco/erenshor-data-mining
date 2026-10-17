#nullable enable

using System;
using SQLite;

public sealed class GameManagerItemBindingListener : IAssetScanListener<GameManager>
{
    public const string PlanarShardBinding =
        nameof(GameManager) + "." + nameof(GameManager.PlanarShard);
    private readonly SQLiteConnection _db;
    private NativeItemBindingRecord? _binding;
    private int _sourceCount;
    private bool _written;

    public GameManagerItemBindingListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _binding = null;
        _sourceCount = 0;
        _written = false;
    }

    public void OnAssetFound(GameManager manager)
    {
        _sourceCount++;
        if (_sourceCount != 1)
            throw new InvalidOperationException(
                "Native item bindings require exactly one GameManager component"
            );
        // code-fact: smithing.blessing_outputs
        _binding = new NativeItemBindingRecord
        {
            BindingKey = PlanarShardBinding,
            SourceComponentKey =
                ActivationTargetResolver.ObjectKey(manager.gameObject) + ":script:GameManager:0",
            ItemStableKey =
                manager.PlanarShard != null
                    ? StableKeyGenerator.ForItem(manager.PlanarShard)
                    : null,
        };
    }

    public void OnScanFinished()
    {
        if (_written)
            return;
        if (_sourceCount != 1)
            throw new InvalidOperationException(
                $"Native item bindings require exactly one GameManager component, found {_sourceCount}"
            );
        var binding =
            _binding
            ?? throw new InvalidOperationException("Native item binding snapshot is missing");
        if (binding.ItemStableKey != null)
            _db.Get<ItemRecord>(binding.ItemStableKey);
        _db.CreateTable<NativeItemBindingRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<NativeItemBindingRecord>();
            _db.Insert(binding);
        });
        _written = true;
        _binding = null;
    }
}
