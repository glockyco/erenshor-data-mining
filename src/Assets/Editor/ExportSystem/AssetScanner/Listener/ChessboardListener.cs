#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Exports the Item fields of each placed Chessboard. The board consumes a
/// figurine to summon its game piece, and gives the ReplaceStatue item back for
/// the Candlekeeper figurine. The rule itself is pinned by code facts.
/// </summary>
public class ChessboardListener : IAssetScanListener<Chessboard>
{
    private readonly SQLiteConnection _db;
    private readonly List<ChessboardItemRecord> _records = new();

    public ChessboardListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<ChessboardItemRecord>();
        _db.DeleteAll<ChessboardItemRecord>();
        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);
        _records.Clear();
    }

    public void OnAssetFound(Chessboard board)
    {
        // The scan exports placed copies from scenes; a prefab asset has no scene.
        var scene = board.gameObject.scene.name;
        if (string.IsNullOrEmpty(scene))
        {
            return;
        }

        Add(scene, nameof(Chessboard.ReplaceStatue), board.ReplaceStatue);
        Add(scene, nameof(Chessboard.Peon), board.Peon);
        Add(scene, nameof(Chessboard.Ember), board.Ember);
        Add(scene, nameof(Chessboard.Blaze), board.Blaze);
        Add(scene, nameof(Chessboard.Monarch), board.Monarch);
        Add(scene, nameof(Chessboard.Candlekeeper), board.Candlekeeper);
        Add(scene, nameof(Chessboard.Kingsman), board.Kingsman);
        Add(scene, nameof(Chessboard.Faceless), board.Faceless);
    }

    private void Add(string scene, string field, Item? item)
    {
        _records.Add(
            new ChessboardItemRecord
            {
                Scene = scene,
                Field = field,
                ItemStableKey = item == null ? null : StableKeyGenerator.ForItem(item),
            }
        );
    }
}
