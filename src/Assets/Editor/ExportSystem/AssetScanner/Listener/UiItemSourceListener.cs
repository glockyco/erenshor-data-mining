#nullable enable

using System;
using System.Collections.Generic;
using SQLite;
using UnityEngine;

/// <summary>Exports native grant slots, their replenishment input, and planning desk access.</summary>
public class UiItemSourceListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly Dictionary<string, UiItemSourceRecord> _sources = new();
    private readonly Dictionary<string, UiItemAccessTargetRecord> _targets = new();
    private readonly Dictionary<string, UiItemAccessActivationRecord> _activations = new();
    private readonly Dictionary<string, List<(string SourceKey, string? ItemKey)>> _hideItems =
        new();

    public UiItemSourceListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _sources.Clear();
        _targets.Clear();
        _activations.Clear();
        _hideItems.Clear();
    }

    public void OnAssetFound(GameObject asset)
    {
        if (asset == null || string.IsNullOrEmpty(asset.scene.name))
            return;

        foreach (var misc in asset.GetComponents<Misc>())
        {
            // code-fact: ui.misc_reference
            if (!_hideItems.TryGetValue(asset.scene.name, out var items))
            {
                items = new List<(string, string?)>();
                _hideItems.Add(asset.scene.name, items);
            }
            items.Add(
                (
                    ComponentKey(misc),
                    misc.TMOGHIDE == null ? null : StableKeyGenerator.ForItem(misc.TMOGHIDE)
                )
            );
        }
        foreach (var source in asset.GetComponents<ReplenishTMOGHide>())
            AddSource(source, nameof(ReplenishTMOGHide.MyIcon), source.MyIcon);
        foreach (var source in asset.GetComponents<PlanningTableUI>())
        {
            // code-fact: ui.planning_reference
            // code-fact: ui.planning_portal_not_reset
            AddSource(source, nameof(PlanningTableUI.Portal), source.Portal);
        }

        // code-fact: ui.planning_desk_open
        if (asset.CompareTag("PlanningDesk"))
            AddTarget(asset);
        foreach (var activator in asset.GetComponents<QuestSpawnListener>())
            AddActivations(activator);
    }

    public void OnScanFinished()
    {
        foreach (var source in _sources.Values)
        {
            if (source.ComponentType != nameof(ReplenishTMOGHide))
                continue;
            if (
                !_hideItems.TryGetValue(source.Scene, out var items)
                || items.Count != 1
                || items[0].ItemKey == null
            )
                throw new InvalidOperationException(
                    $"{source.StableKey} needs exactly one native Misc.TMOGHIDE reference in {source.Scene}"
                );
            // code-fact: ui.hide_slot_replenishment
            source.ReplenishSourceKey = items[0].SourceKey;
            source.ReplenishItemStableKey = items[0].ItemKey;
        }

        _db.CreateTable<UiItemSourceRecord>();
        _db.CreateTable<UiItemAccessTargetRecord>();
        _db.CreateTable<UiItemAccessActivationRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<UiItemAccessActivationRecord>();
            _db.DeleteAll<UiItemAccessTargetRecord>();
            _db.DeleteAll<UiItemSourceRecord>();
            _db.InsertAll(_sources.Values);
            _db.InsertAll(_targets.Values);
            _db.InsertAll(_activations.Values);
        });
    }

    private void AddSource(Component source, string slot, ItemIcon? icon)
    {
        if (icon == null)
            throw new InvalidOperationException($"{ComponentKey(source)} has no {slot} icon");
        var key = ComponentKey(source);
        _sources.Add(
            key,
            new UiItemSourceRecord
            {
                StableKey = key,
                ComponentType = source.GetType().Name,
                Scene = source.gameObject.scene.name,
                HierarchyPath = HierarchyPath(source.transform),
                Slot = slot,
                IconHierarchyPath = HierarchyPath(icon.transform),
                SerializedItemStableKey =
                    icon.MyItem == null ? null : StableKeyGenerator.ForItem(icon.MyItem),
                SerializedQuantity = icon.Quantity,
                // code-fact: ui.item_icon_pickup
                // code-fact: ui.item_icon_pickup_quantity
                // code-fact: ui.item_icon_inventory_transfer
                // code-fact: ui.item_icon_pointer_access
                DisplayOnly = icon.DisplayOnly,
                VendorSlot = icon.VendorSlot,
                LootSlot = icon.LootSlot,
                BankSlot = icon.BankSlot,
                MouseSlot = icon.MouseSlot,
                PlayerOwned = icon.PlayerOwned,
                NotInInventory = icon.NotInInventory,
                SlotType = icon.ThisSlotType.ToString(),
            }
        );
    }

    private string AddTarget(GameObject target)
    {
        var key = StableKeyGenerator.ForUiComponent(
            target.scene.name,
            HierarchyPath(target.transform),
            nameof(GameObject)
        );
        if (!_targets.ContainsKey(key))
        {
            _targets.Add(
                key,
                new UiItemAccessTargetRecord
                {
                    StableKey = key,
                    Scene = target.scene.name,
                    HierarchyPath = HierarchyPath(target.transform),
                    Tag = target.tag,
                    ActiveSelf = target.activeSelf,
                    ActiveInHierarchy = target.activeInHierarchy,
                    X = target.transform.position.x,
                    Y = target.transform.position.y,
                    Z = target.transform.position.z,
                }
            );
        }
        return key;
    }

    private void AddActivations(QuestSpawnListener activator)
    {
        if (activator.EnableOnQuestComplete == null)
            return;
        foreach (var enabled in activator.EnableOnQuestComplete)
        {
            if (enabled == null)
                continue;
            foreach (var child in enabled.GetComponentsInChildren<Transform>(true))
            {
                if (!child.CompareTag("PlanningDesk"))
                    continue;
                if (child.gameObject != enabled && !ActiveUnder(child, enabled.transform))
                    continue;
                var targetKey = AddTarget(child.gameObject);
                var activatorKey = ComponentKey(activator);
                var key = $"{activatorKey}:{targetKey}";
                // code-fact: ui.planning_access_quest
                // code-fact: ui.planning_access_alternative_quest
                // code-fact: ui.planning_access_item
                _activations[key] = new UiItemAccessActivationRecord
                {
                    StableKey = key,
                    TargetStableKey = targetKey,
                    ActivatorStableKey = activatorKey,
                    Scene = activator.gameObject.scene.name,
                    HierarchyPath = HierarchyPath(activator.transform),
                    QuestStableKey =
                        activator.Quest == null
                            ? null
                            : StableKeyGenerator.ForQuest(activator.Quest),
                    AlternativeQuestStableKey =
                        activator.ActiveQuest == null
                            ? null
                            : StableKeyGenerator.ForQuest(activator.ActiveQuest),
                    ItemStableKey =
                        activator.item == null ? null : StableKeyGenerator.ForItem(activator.item),
                };
            }
        }
    }

    private static bool ActiveUnder(Transform child, Transform enabled)
    {
        for (var current = child; current != enabled; current = current.parent)
        {
            if (!current.gameObject.activeSelf)
                return false;
        }
        return true;
    }

    private static string ComponentKey(Component component) =>
        StableKeyGenerator.ForUiComponent(
            component.gameObject.scene.name,
            HierarchyPath(component.transform),
            component.GetType().Name,
            Array.IndexOf(component.gameObject.GetComponents(component.GetType()), component)
        );

    private static string HierarchyPath(Transform transform)
    {
        var parts = new Stack<string>();
        for (var current = transform; current != null; current = current.parent)
            parts.Push($"{current.name}[{current.GetSiblingIndex()}]");
        return string.Join("/", parts);
    }
}
