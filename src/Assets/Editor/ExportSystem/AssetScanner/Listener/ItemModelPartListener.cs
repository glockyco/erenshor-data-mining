#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Exports the parts of the player's male and female bodies that items switch on.
/// <c>ModularParts.UpdateSlot</c> turns on the child of a slot transform whose name is
/// the equipped item's <c>EquipmentToActivate</c>, and <c>Inventory.SetHalloweenMask</c>
/// turns on the mask object of that name. The player's <c>ModularPar</c> in LoadScene
/// holds both bodies; its <c>Awake</c> picks it by its parent's name, as this listener does.
/// The meshes of each part tell the picture capture whether the two bodies draw an
/// item alike.
/// </summary>
public class ItemModelPartListener : IAssetScanListener<ModularPar>
{
    // The slot transforms that UpdatePlayerVisuals fills from items, which every body has.
    private static readonly string[] SlotFields =
    {
        "HeadCover",
        "FullHeadHelm",
        "HatWithHair",
        "Cloak",
        "WeaponR",
        "WeaponL",
        "Chest",
        "ArmL",
        "ArmR",
        "BracerL",
        "BracerR",
        "GloveL",
        "GloveR",
        "Pants",
        "BootsL",
        "BootsR",
    };

    // The trim slots that UpdateTrimSlot fills next to a chest, legs, or bracers.
    // GetCachedTransforms gives a body that leaves one unassigned no part there.
    private static readonly string[] TrimFields =
    {
        "ShoulderL",
        "ShoulderR",
        "KneeL",
        "KneeR",
        "ElbowL",
        "ElbowR",
    };

    private readonly SQLiteConnection _db;
    private readonly List<ItemModelPartRecord> _records = new();
    private int _players;

    public ItemModelPartListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _records.Clear();
        _players = 0;
    }

    public void OnAssetFound(ModularPar asset)
    {
        if (asset == null || string.IsNullOrEmpty(asset.gameObject.scene.name))
        {
            return;
        }
        var parent = asset.transform.parent;
        if (parent == null || parent.name != "Player")
        {
            return;
        }
        _players++;
        AddBody("Male", asset.Male);
        AddBody("Female", asset.Female);
    }

    public void OnScanFinished()
    {
        if (_players != 1)
        {
            throw new InvalidOperationException(
                $"Expected exactly one player ModularPar, found {_players}"
            );
        }
        _db.CreateTable<ItemModelPartRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ItemModelPartRecord>();
            _db.InsertAll(_records);
        });
        Debug.Log($"[{GetType().Name}] Wrote {_records.Count} body parts");
        _records.Clear();
    }

    private void AddBody(string body, ModularParts? parts)
    {
        if (parts == null)
        {
            throw new InvalidOperationException($"The player's ModularPar has no {body} body");
        }
        foreach (var field in SlotFields.Concat(TrimFields))
        {
            var slot = (Transform?)typeof(ModularParts).GetField(field).GetValue(parts);
            if (slot == null)
            {
                if (TrimFields.Contains(field))
                {
                    continue;
                }
                throw new InvalidOperationException(
                    $"The player's {body} body has no {field} slot"
                );
            }
            // UpdateSlot and UpdateTrimSlot match the item's name against every
            // descendant of the slot (GetCachedTransforms), not only its children.
            var descendants = slot.GetComponentsInChildren<Transform>(true);
            for (var i = 0; i < descendants.Length; i++)
            {
                var part = descendants[i];
                if (part == slot)
                {
                    continue;
                }
                _records.Add(
                    new ItemModelPartRecord
                    {
                        Body = body,
                        Slot = field,
                        Position = i,
                        Part = part.name,
                        Meshes = MeshesOf(part.gameObject),
                    }
                );
            }
        }
        var masks = parts.HalloweenMasks ?? new List<GameObject>();
        for (var i = 0; i < masks.Count; i++)
        {
            if (masks[i] == null)
            {
                continue;
            }
            _records.Add(
                new ItemModelPartRecord
                {
                    Body = body,
                    Slot = "HalloweenMasks",
                    Position = i,
                    Part = masks[i].name,
                    Meshes = MeshesOf(masks[i]),
                }
            );
        }
    }

    private static string MeshesOf(GameObject part)
    {
        var meshes = new SortedSet<string>(StringComparer.Ordinal);
        foreach (var renderer in part.GetComponentsInChildren<Renderer>(true))
        {
            Mesh? mesh = renderer switch
            {
                SkinnedMeshRenderer skinned => skinned.sharedMesh,
                MeshRenderer => renderer.TryGetComponent<MeshFilter>(out var filter)
                    ? filter.sharedMesh
                    : null,
                _ => null,
            };
            if (mesh != null)
            {
                meshes.Add($"{AssetDatabase.GetAssetPath(mesh)}:{mesh.name}");
            }
        }
        return string.Join("|", meshes.ToArray());
    }
}
