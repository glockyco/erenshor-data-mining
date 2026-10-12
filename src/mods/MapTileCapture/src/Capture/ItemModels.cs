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

    /// <summary>
    /// The furnishing named <paramref name="part"/> under a slot of the loaded
    /// scene's planning table, and the direction, in the furnishing's own
    /// frame, from which players see it. A room set opens onto the hall, so
    /// players see it from across the hall, from the opposite room slot; a
    /// statue faces the hall with its front, its local back. The room sets
    /// themselves face various ways, so their own forward says nothing about
    /// where players stand.
    /// </summary>
    public static (GameObject Furnishing, Vector3 Facing) Furnishing(string part)
    {
        var table =
            Object.FindObjectOfType<PlanningTable>(true)
            ?? throw new PortraitException("The loaded scene has no planning table.");
        var left = new[] { table.L1, table.L2, table.L3, table.L4 };
        var right = new[] { table.R1, table.R2, table.R3, table.R4 };
        var statues = new[] { table.StatueFR, table.StatueFL, table.StatueBR, table.StatueBL };
        if (left.Concat(right).Concat(statues).Any(slot => slot == null))
            throw new PortraitException("The planning table lacks one of its slots.");
        var rooms = left.Concat(right).ToArray();

        for (int index = 0; index < rooms.Length + statues.Length; index++)
        {
            var slot = index < rooms.Length ? rooms[index] : statues[index - rooms.Length];
            var furnishing = Children(slot).FirstOrDefault(child => child.name == part);
            if (furnishing == null)
                continue;
            // A statue model faces its local back; the Reliquary turns each one
            // to face the hall that way.
            if (index >= rooms.Length)
                return (furnishing.gameObject, Vector3.back);
            var viewpoint = rooms[(index + left.Length) % rooms.Length].position;
            var toViewer = viewpoint - furnishing.position;
            toViewer.y = 0f;
            if (toViewer.sqrMagnitude < 1e-4f)
                throw new PortraitException(
                    $"The furnishing {part} stands where players see it from."
                );
            var facing = furnishing.InverseTransformDirection(toViewer.normalized);
            facing.y = 0f;
            return (furnishing.gameObject, facing.normalized);
        }
        throw new PortraitException($"The planning table has no furnishing named {part}.");
    }

    /// <summary>
    /// Shows the item's parts on the copy of the player, hides every other
    /// renderer, and returns the name of the item's part as the copy holds it.
    /// Runs before the studio removes the copy's scripts, because it reads the
    /// copy's <c>ModularPar</c>.
    /// </summary>
    public static string ShowOnBody(GameObject copy, ItemModelSource source)
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
        string partName;
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
            partName = mask.name;
        }
        else
        {
            foreach (var slot in SlotTransforms(body, item))
                shown.AddRange(PartsNamed(slot, item.EquipmentToActivate));
            if (shown.Count == 0)
                throw new PortraitException(
                    $"The {source.Body} body has no part named {source.Part}."
                );
            partName = shown[0].name;
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
        foreach (var skinned in kept.OfType<SkinnedMeshRenderer>())
        {
            TakeLostMaterials(skinned, copy.transform, Player().transform);
            BoundInBindPose(skinned);
        }
        // The copy's camera, listener, and canvases would show on the screen.
        foreach (var camera in copy.GetComponentsInChildren<Camera>(true))
            Object.DestroyImmediate(camera);
        foreach (var listener in copy.GetComponentsInChildren<AudioListener>(true))
            Object.DestroyImmediate(listener);
        foreach (var canvas in copy.GetComponentsInChildren<Canvas>(true))
            Object.DestroyImmediate(canvas.gameObject);
        return partName;
    }

    /// <summary>
    /// Gives a skinned part of the copy the materials of the player's own part
    /// when the copy lost them. Cape2, the model of four capes, also carries a
    /// MeshRenderer without a material or a mesh filter; Unity drops it from a
    /// copy and leaves the copy's SkinnedMeshRenderer with its empty material,
    /// which the studio drew in error magenta, while the game draws the cape
    /// with its own material.
    /// </summary>
    private static void TakeLostMaterials(
        SkinnedMeshRenderer skinned,
        Transform copyRoot,
        Transform playerRoot
    )
    {
        if (skinned.sharedMaterials.All(material => material != null))
            return;
        // The studio removed objects from the copy, such as its target ring,
        // so a child is found by its name and its rank among same-named siblings.
        var path = new Stack<(string Name, int Rank)>();
        for (var current = skinned.transform; current != copyRoot; current = current.parent)
            path.Push((current.name, SameNamedRank(current)));
        var original = playerRoot;
        while (path.Count > 0)
        {
            var (name, rank) = path.Pop();
            original =
                Children(original).Where(child => child.name == name).ElementAtOrDefault(rank)
                ?? throw new PortraitException($"The player has no {name} where the copy has one.");
        }
        var source =
            original.GetComponent<SkinnedMeshRenderer>()
            ?? throw new PortraitException(
                $"The player's {skinned.name} has no skinned mesh to take materials from."
            );
        if (source.sharedMaterials.Any(material => material == null))
            throw new PortraitException($"The player's {skinned.name} lacks a material too.");
        skinned.sharedMaterials = source.sharedMaterials;
    }

    private static IEnumerable<Transform> Children(Transform parent)
    {
        for (int i = 0; i < parent.childCount; i++)
            yield return parent.GetChild(i);
    }

    private static int SameNamedRank(Transform child) =>
        Children(child.parent)
            .TakeWhile(sibling => sibling != child)
            .Count(sibling => sibling.name == child.name);

    /// <summary>
    /// Gives a skinned part the bounds of its mesh in the bind pose, in the
    /// space of its root bone. The studio frames the part by its bounds, and two
    /// capes, <c>NarrowCape</c> and <c>ClothCloak</c>, carry bounds a hundred
    /// times too small, which put the cape behind the studio camera's far plane.
    /// Every other part's authored bounds agree with these on build 24405256.
    /// </summary>
    private static void BoundInBindPose(SkinnedMeshRenderer skinned)
    {
        var mesh = skinned.sharedMesh;
        if (mesh == null || skinned.rootBone == null)
            return;
        int root = Array.IndexOf(skinned.bones, skinned.rootBone);
        var bindposes = mesh.bindposes;
        if (root < 0 || root >= bindposes.Length)
            return;
        var toRoot = bindposes[root];
        var meshBounds = mesh.bounds;
        var bounds = new Bounds(toRoot.MultiplyPoint3x4(meshBounds.min), Vector3.zero);
        for (int corner = 0; corner < 8; corner++)
        {
            bounds.Encapsulate(
                toRoot.MultiplyPoint3x4(
                    new Vector3(
                        (corner & 1) == 0 ? meshBounds.min.x : meshBounds.max.x,
                        (corner & 2) == 0 ? meshBounds.min.y : meshBounds.max.y,
                        (corner & 4) == 0 ? meshBounds.min.z : meshBounds.max.z
                    )
                )
            );
        }
        skinned.localBounds = bounds;
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
