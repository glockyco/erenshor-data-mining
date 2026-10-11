using MapTileCapture.Protocol;
using UnityEngine;
using Object = UnityEngine.Object;

namespace MapTileCapture.Capture;

/// <summary>
/// The game objects that show an item's model, and how a copy of them shows
/// the item by itself (design D2 of show-item-pictures-by-role).
///
/// Equipping an item turns on the parts of the player's body whose name is the
/// item's <c>EquipmentToActivate</c>, among all descendants of the slot
/// transforms that <c>ModularParts.UpdatePlayerVisuals</c> fills, colours them
/// from the item, and turns on the trims of chests, legs, and bracers
/// (<c>UpdateSlot</c>, <c>UpdateTrimSlot</c>). A copy of the player keeps the
/// skeleton and its pose, shows those parts of the requested body in the item's
/// colours, and hides every other renderer, so the item appears without the
/// body. Skin that a part draws takes the first colour of the game's skin
/// palette, <c>SimPlayerMngr.SkinColors</c>, so a render does not depend on the
/// character that captures it. A furnishing is the child of a planning table
/// slot that a furniture set turns on, copied by itself.
/// </summary>
internal static class ItemModels
{
    private static readonly string[] HeadFields = { "HeadCover", "FullHeadHelm", "HatWithHair" };

    /// <summary>The player, whose copy the studio turns into the item's model with <see cref="ShowOnBody"/>.</summary>
    public static GameObject Player() =>
        GameData.PlayerControl != null
            ? GameData.PlayerControl.gameObject
            : throw new PortraitException("The player is not in the world.");

    /// <summary>The furnishing named <paramref name="part"/> under a slot of the loaded scene's planning table.</summary>
    public static GameObject Furnishing(string part)
    {
        var table =
            Object.FindObjectOfType<PlanningTable>(true)
            ?? throw new PortraitException("The loaded scene has no planning table.");
        var slots = new[]
        {
            table.L1,
            table.L2,
            table.L3,
            table.L4,
            table.R1,
            table.R2,
            table.R3,
            table.R4,
            table.StatueFR,
            table.StatueFL,
            table.StatueBR,
            table.StatueBL,
        };
        foreach (var slot in slots)
        {
            if (slot == null)
                continue;
            for (int i = 0; i < slot.childCount; i++)
            {
                var child = slot.GetChild(i);
                if (child.name == part)
                    return child.gameObject;
            }
        }
        throw new PortraitException($"The planning table has no furnishing named {part}.");
    }

    /// <summary>
    /// Shows the item's parts on the copy of the player and hides every other
    /// renderer. Runs before the studio removes the copy's scripts, because it
    /// reads the copy's <c>ModularPar</c>.
    /// </summary>
    public static void ShowOnBody(GameObject copy, ItemModelSource source)
    {
        var item =
            GameData.ItemDB?.GetItemByID(source.Id)
            ?? throw new PortraitException($"The game has no item with the ID {source.Id}.");
        if (item.EquipmentToActivate != source.Part)
            throw new PortraitException(
                $"The item {item.ItemName} switches on {item.EquipmentToActivate}, not {source.Part}."
            );
        var modular =
            copy.GetComponentInChildren<ModularPar>(true)
            ?? throw new PortraitException("The player has no modular body.");
        var body =
            (source.Body == "female" ? modular.Female : modular.Male)
            ?? throw new PortraitException($"The player has no {source.Body ?? "male"} body.");

        var shown = new List<GameObject>();
        if (source.Kind == "mask")
        {
            var masks = body.HalloweenMasks ?? new List<GameObject>();
            var mask =
                masks.FirstOrDefault(candidate =>
                    candidate != null && candidate.name == source.Part
                )
                ?? throw new PortraitException(
                    $"The {source.Body ?? "male"} body has no mask named {source.Part}."
                );
            // SetHalloweenMask also turns on the first entry, which every mask wears.
            if (masks.Count > 0 && masks[0] != null)
                shown.Add(masks[0]);
            shown.Add(mask);
        }
        else
        {
            foreach (var slot in SlotTransforms(body, item))
                shown.AddRange(PartsNamed(slot, item.EquipmentToActivate));
            if (shown.Count == 0)
                throw new PortraitException(
                    $"The {source.Body} body has no part named {source.Part}."
                );
            var skin = GameData.SimMngr?.SkinColors is { Count: > 0 } palette
                ? palette[0]
                : throw new PortraitException("The game's skin palette is not loaded.");
            // UpdateSlot gives the dark metal of a part the item's primary colour,
            // and UpdateTrimSlot gives a trim the item's dark metal colour.
            foreach (var part in shown)
                Colour(part, item, skin, item.ItemPrimaryColor);
            foreach (var (slot, name) in Trims(body, item))
            {
                foreach (var trim in PartsNamed(slot, name))
                {
                    Colour(trim, item, skin, item.ItemMetalDark);
                    shown.Add(trim);
                }
            }
            foreach (var part in shown.ToList())
            {
                var remote = part.GetComponent<ActivateRemoteMesh>();
                if (remote != null && remote.RemoteMesh != null)
                    shown.Add(remote.RemoteMesh);
            }
        }

        foreach (var part in shown)
        {
            for (
                var current = part.transform;
                current != null && current != copy.transform;
                current = current.parent
            )
                current.gameObject.SetActive(true);
            for (int i = 0; i < part.transform.childCount; i++)
                part.transform.GetChild(i).gameObject.SetActive(true);
        }
        var kept = new HashSet<Renderer>(
            shown.SelectMany(part => part.GetComponentsInChildren<Renderer>(true))
        );
        foreach (var renderer in copy.GetComponentsInChildren<Renderer>(true))
            renderer.enabled = kept.Contains(renderer);
        // The copy's camera, listener, and canvases would show on the screen.
        foreach (var camera in copy.GetComponentsInChildren<Camera>(true))
            Object.DestroyImmediate(camera);
        foreach (var listener in copy.GetComponentsInChildren<AudioListener>(true))
            Object.DestroyImmediate(listener);
        foreach (var canvas in copy.GetComponentsInChildren<Canvas>(true))
            Object.DestroyImmediate(canvas.gameObject);
    }

    /// <summary>The slot transforms that UpdatePlayerVisuals fills for the item's slot.</summary>
    private static IEnumerable<Transform> SlotTransforms(ModularParts body, Item item)
    {
        var slots = item.RequiredSlot switch
        {
            Item.SlotType.Head => HeadFields.Select(field =>
                (Transform)typeof(ModularParts).GetField(field).GetValue(body)
            ),
            Item.SlotType.Chest => new[] { body.Chest },
            Item.SlotType.Leg => new[] { body.Pants },
            Item.SlotType.Arm => new[] { body.ArmL, body.ArmR },
            Item.SlotType.Foot => new[] { body.BootsL, body.BootsR },
            Item.SlotType.Hand => new[] { body.GloveL, body.GloveR },
            Item.SlotType.Bracer => new[] { body.BracerL, body.BracerR },
            Item.SlotType.Back => new[] { body.Cloak },
            Item.SlotType.Primary => new[] { item.IsBow ? body.WeaponL : body.WeaponR },
            Item.SlotType.Secondary => new[] { body.WeaponL },
            Item.SlotType.PrimaryOrSecondary => new[] { body.WeaponR },
            _ => throw new PortraitException(
                $"The slot {item.RequiredSlot} shows no model on the body."
            ),
        };
        return slots.Where(slot => slot != null);
    }

    /// <summary>The trims that UpdatePlayerVisuals turns on next to a chest, legs, or bracers.</summary>
    private static IEnumerable<(Transform Slot, string Name)> Trims(ModularParts body, Item item)
    {
        var trims = item.RequiredSlot switch
        {
            Item.SlotType.Chest => new[]
            {
                (body.ShoulderL, "Shoulder" + item.ShoulderTrimL),
                (body.ShoulderR, "Shoulder" + item.ShoulderTrimR),
            },
            Item.SlotType.Leg => new[]
            {
                (body.KneeL, "Knee" + item.KneeTrimL),
                (body.KneeR, "Knee" + item.KneeTrimR),
            },
            Item.SlotType.Bracer => new[]
            {
                (body.ElbowL, "Elbow" + item.ElbowTrimL),
                (body.ElbowR, "Elbow" + item.ElbowTrimR),
            },
            _ => Array.Empty<(Transform, string)>(),
        };
        return trims.Where(trim => trim.Item1 != null);
    }

    /// <summary>The descendants of <paramref name="slot"/> named <paramref name="name"/>, as GetCachedTransforms finds them.</summary>
    private static IEnumerable<GameObject> PartsNamed(Transform slot, string name) =>
        slot.GetComponentsInChildren<Transform>(true)
            .Where(part => part != slot && part.name == name && name != "DEFAULT")
            .Select(part => part.gameObject);

    /// <summary>Colours a part's skinned mesh from the item, as UpdateSlot and UpdateTrimSlot do.</summary>
    private static void Colour(GameObject part, Item item, Color skin, Color metalDark)
    {
        var renderer = part.GetComponent<SkinnedMeshRenderer>();
        if (renderer == null || part.CompareTag("Bow"))
            return;
        renderer.enabled = true;
        var block = new MaterialPropertyBlock();
        renderer.GetPropertyBlock(block);
        block.SetColor("_Color_Primary", item.ItemPrimaryColor);
        block.SetColor("_Color_Secondary", item.ItemSecondaryColor);
        block.SetColor("_Color_Metal_Primary", item.ItemMetalPrimary);
        block.SetColor("_Color_Leather_Primary", item.ItemLeatherPrimary);
        block.SetColor("_Color_Metal_Dark", metalDark);
        block.SetColor("_Color_Metal_Secondary", item.ItemMetalSecondary);
        block.SetColor("_Color_Skin", skin);
        block.SetColor("_Color_Leather_Secondary", item.ItemLeatherSecondary);
        renderer.SetPropertyBlock(block);
    }
}
