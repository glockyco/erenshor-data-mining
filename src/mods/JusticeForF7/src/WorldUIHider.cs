using BepInEx.Configuration;
using BepInEx.Logging;
using TMPro;
using UnityEngine;

namespace JusticeForF7;

/// <summary>
/// Core logic for hiding and restoring world-space UI elements when F7 toggles
/// the main Canvas. Uses Renderer-based toggling to avoid fighting the game's
/// own per-frame visibility management of TextMeshPro.enabled.
/// </summary>
internal sealed class WorldUIHider
{
    private readonly ManualLogSource _log;
    private readonly ConfigEntry<bool> _enableLogging;
    private readonly ConfigEntry<bool> _hideNameplates;
    private readonly ConfigEntry<bool> _hideDamageNumbers;
    private readonly ConfigEntry<bool> _hideTargetRings;
    private readonly ConfigEntry<bool> _hideXPOrbs;
    private readonly ConfigEntry<bool> _hideCastBars;
    private readonly ConfigEntry<bool> _hideOtherWorldText;
    private readonly ConfigEntry<int> _rescanInterval;

    private readonly HashSet<Renderer> _disabledRenderers = new();
    private readonly HashSet<GameObject> _disabledGameObjects = new();

    private int _framesSinceLastScan;

    /// <summary>Whether the world UI is currently hidden.</summary>
    public bool IsHidden { get; private set; }

    /// <summary>
    /// Whether creation of transient elements (damage pops, XP orbs) should
    /// be suppressed. Checked by Harmony prefix patches.
    /// </summary>
    public bool SuppressDamageNumbers => IsHidden && _hideDamageNumbers.Value;
    public bool SuppressXPOrbs => IsHidden && _hideXPOrbs.Value;

    public WorldUIHider(
        ManualLogSource log,
        ConfigEntry<bool> enableLogging,
        ConfigEntry<bool> hideNameplates,
        ConfigEntry<bool> hideDamageNumbers,
        ConfigEntry<bool> hideTargetRings,
        ConfigEntry<bool> hideXPOrbs,
        ConfigEntry<bool> hideCastBars,
        ConfigEntry<bool> hideOtherWorldText,
        ConfigEntry<int> rescanInterval)
    {
        _log = log;
        _enableLogging = enableLogging;
        _hideNameplates = hideNameplates;
        _hideDamageNumbers = hideDamageNumbers;
        _hideTargetRings = hideTargetRings;
        _hideXPOrbs = hideXPOrbs;
        _hideCastBars = hideCastBars;
        _hideOtherWorldText = hideOtherWorldText;
        _rescanInterval = rescanInterval;
    }

    /// <summary>
    /// Called when F7 hides the Canvas. Finds and hides all world-space UI.
    /// </summary>
    public void OnUIHidden()
    {
        IsHidden = true;
        _framesSinceLastScan = 0;
        ScanAndHide();
    }

    /// <summary>
    /// Called when F7 restores the Canvas. Re-enables everything we hid.
    /// </summary>
    public void OnUIShown()
    {
        IsHidden = false;
        RestoreAll();
    }

    /// <summary>
    /// Called every frame while UI is hidden. Runs periodic re-scan to catch
    /// newly spawned elements.
    /// </summary>
    public void Tick()
    {
        if (!IsHidden)
            return;

        var interval = _rescanInterval.Value;
        if (interval <= 0)
            return;

        _framesSinceLastScan++;
        if (_framesSinceLastScan >= interval)
        {
            _framesSinceLastScan = 0;
            ScanAndHide();
        }
    }

    /// <summary>
    /// Called on scene change. Clears tracking state and re-hides if needed.
    /// </summary>
    public void OnSceneLoaded()
    {
        // Old objects are destroyed, clear references
        _disabledRenderers.Clear();
        _disabledGameObjects.Clear();

        if (IsHidden)
        {
            _framesSinceLastScan = 0;
            ScanAndHide();
        }
    }

    private void ScanAndHide()
    {
        int count = 0;

        if (_hideNameplates.Value)
            count += HideNameplates();

        if (_hideDamageNumbers.Value)
            count += HideDamageNumbers();

        if (_hideTargetRings.Value)
            count += HideTargetRings();

        if (_hideXPOrbs.Value)
            count += HideXPOrbs();

        if (_hideCastBars.Value)
            count += HideCastBars();

        if (_hideOtherWorldText.Value)
            count += HideOtherWorldText();

        if (_enableLogging.Value)
            _log.LogDebug($"Scan complete: {count} elements hidden");
    }

    private int HideNameplates()
    {
        int count = 0;
        foreach (var plate in UnityEngine.Object.FindObjectsOfType<NamePlate>())
        {
            var renderer = plate.GetComponent<Renderer>();
            if (renderer != null && renderer.enabled)
            {
                renderer.enabled = false;
                _disabledRenderers.Add(renderer);
                count++;
            }
        }
        return count;
    }

    private int HideDamageNumbers()
    {
        int count = 0;
        foreach (var pop in UnityEngine.Object.FindObjectsOfType<DmgPop>())
        {
            // DmgPop has a TextMeshPro child component with the Renderer
            var renderer = pop.Num != null ? pop.Num.GetComponent<Renderer>() : null;
            if (renderer != null && renderer.enabled)
            {
                renderer.enabled = false;
                _disabledRenderers.Add(renderer);
                count++;
            }
        }
        return count;
    }

    private int HideTargetRings()
    {
        int count = 0;
        foreach (var character in UnityEngine.Object.FindObjectsOfType<Character>())
        {
            var ring = character.TargetRing;
            if (ring != null && ring.activeSelf)
            {
                ring.SetActive(false);
                _disabledGameObjects.Add(ring);
                count++;
            }
        }
        return count;
    }

    private int HideXPOrbs()
    {
        int count = 0;
        foreach (var orb in UnityEngine.Object.FindObjectsOfType<XPBub>())
        {
            var renderer = orb.GetComponent<Renderer>();
            if (renderer != null && renderer.enabled)
            {
                renderer.enabled = false;
                _disabledRenderers.Add(renderer);
                count++;
            }
        }
        return count;
    }

    private int HideCastBars()
    {
        int count = 0;
        foreach (var flash in UnityEngine.Object.FindObjectsOfType<FlashUIColors>())
        {
            if (flash.CastBar == null)
                continue;

            var renderer = flash.CastBar.GetComponent<Renderer>();
            if (renderer != null && renderer.enabled)
            {
                renderer.enabled = false;
                _disabledRenderers.Add(renderer);
                count++;
            }
        }
        return count;
    }

    private int HideOtherWorldText()
    {
        int count = 0;
        foreach (var tmp in UnityEngine.Object.FindObjectsOfType<TextMeshPro>())
        {
            // Skip objects already handled by other categories
            if (tmp.GetComponent<NamePlate>() != null)
                continue;
            if (tmp.GetComponent<DmgPop>() != null)
                continue;
            if (tmp.GetComponentInParent<DmgPop>() != null)
                continue;

            var renderer = tmp.GetComponent<Renderer>();
            if (renderer != null && renderer.enabled)
            {
                renderer.enabled = false;
                _disabledRenderers.Add(renderer);
                count++;
            }
        }
        return count;
    }

    private void RestoreAll()
    {
        int rendererCount = 0;
        int gameObjectCount = 0;

        // Remove references to destroyed objects (Unity null comparison)
        _disabledRenderers.RemoveWhere(r => r == null);
        _disabledGameObjects.RemoveWhere(go => go == null);

        foreach (var renderer in _disabledRenderers)
        {
            renderer.enabled = true;
            rendererCount++;
        }

        foreach (var go in _disabledGameObjects)
        {
            go.SetActive(true);
            gameObjectCount++;
        }

        _disabledRenderers.Clear();
        _disabledGameObjects.Clear();

        if (_enableLogging.Value)
            _log.LogDebug(
                $"Restored {rendererCount} renderers, {gameObjectCount} game objects");
    }
}
