#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>
/// Exports the characters that the furnishings of the Reliquary's <c>PlanningTable</c>
/// place. When it starts, the table collects the children of its room and statue slots,
/// and building a slot turns on the child that the slot's furniture item names and turns
/// off the others. A character under such a child stands in the world only while the
/// player's furniture set builds it.
/// </summary>
public class PlanningTableListener : IAssetScanListener<PlanningTable>
{
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly Dictionary<string, PlanningTableCharacterRecord> _records = new();

    public PlanningTableListener(
        SQLiteConnection db,
        CharacterStableKeyResolver characterKeyResolver
    )
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<PlanningTableCharacterRecord>();
        _db.DeleteAll<PlanningTableCharacterRecord>();
        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.RunInTransaction(() => _db.InsertAll(_records.Values));
        _records.Clear();
    }

    public void OnAssetFound(PlanningTable asset)
    {
        if (asset == null)
        {
            return;
        }
        var scene = asset.gameObject.scene.name;
        if (string.IsNullOrEmpty(scene))
        {
            Debug.LogWarning(
                $"[{GetType().Name}] PlanningTable on prefab '{asset.gameObject.name}' has no scene; skipping"
            );
            return;
        }
        // The slots whose children CaptureRoomLayouts collects for CheckRoomAndBuild.
        // code-fact: planning.room_layouts
        var slots = new (string Name, Transform? Transform)[]
        {
            ("L1", asset.L1),
            ("L2", asset.L2),
            ("L3", asset.L3),
            ("L4", asset.L4),
            ("R1", asset.R1),
            ("R2", asset.R2),
            ("R3", asset.R3),
            ("R4", asset.R4),
            ("StatueFR", asset.StatueFR),
            ("StatueFL", asset.StatueFL),
            ("StatueBR", asset.StatueBR),
            ("StatueBL", asset.StatueBL),
        };
        foreach (var (slotName, slot) in slots)
        {
            if (slot == null)
            {
                throw new System.InvalidOperationException(
                    $"{scene} PlanningTable has no {slotName} slot"
                );
            }
            for (var i = 0; i < slot.childCount; i++)
            {
                var furnishing = slot.GetChild(i);
                foreach (var character in furnishing.GetComponentsInChildren<Character>(true))
                {
                    AddCharacter(scene, slotName, furnishing.name, character);
                }
            }
        }
    }

    private void AddCharacter(string scene, string slot, string furnishing, Character character)
    {
        var characterKey = _characterKeyResolver.GetStableKey(character);
        if (_records.TryGetValue(characterKey, out var existing))
        {
            throw new System.InvalidOperationException(
                $"{characterKey} stands in {existing.Slot}/{existing.Furnishing} and {slot}/{furnishing}"
            );
        }
        _records[characterKey] = new PlanningTableCharacterRecord
        {
            CharacterStableKey = characterKey,
            Scene = scene,
            Slot = slot,
            Furnishing = furnishing,
        };
    }
}
