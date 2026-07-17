using TMPro;
using UnityEngine;

namespace JusticeForF7;

/// <summary>
/// Core logic for hiding and restoring world-space UI elements when F7 toggles
/// the main Canvas. Uses Renderer-based toggling to avoid fighting the game's
/// own per-frame visibility management of TextMeshPro.enabled. Settings and
/// logging are supplied through loader-neutral interfaces. Configuration
/// values live in the loader-specific adapter.
/// </summary>
internal sealed class WorldUIHider
{
    private readonly IModLogger _log;
    private readonly IJusticeSettings _settings;

    private readonly HashSet<Renderer> _disabledRenderers = new();
    private readonly HashSet<GameObject> _disabledGameObjects = new();

    private int _framesSinceLastScan;

    /// <summary>Whether the world UI is currently hidden.</summary>
    public bool IsHidden { get; private set; }

    /// <summary>
    /// Whether creation of transient elements (damage pops, XP orbs) should
    /// be suppressed. Checked by Harmony prefix patches.
    /// </summary>
    public bool SuppressDamageNumbers => IsHidden && _settings.HideDamageNumbers;
    public bool SuppressXPOrbs => IsHidden && _settings.HideXPOrbs;

    public WorldUIHider(IModLogger log, IJusticeSettings settings)
    {
        _log = log;
        _settings = settings;
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

        var interval = _settings.RescanInterval;
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

    /// <summary>
    /// Re-hides the target indicator after NamePlate.Update may reactivate it.
    /// </summary>
    internal void EnforceTargetIndicatorHidden(NamePlate? plate)
    {
        if (!IsHidden || !_settings.HideNameplates || plate == null)
            return;

        HideGameObject(plate.TargetInd);
    }

    /// <summary>
    /// Re-hides an NPC health bar after NPC.HandleNameTag may reactivate it.
    /// </summary>
    internal void EnforceHealthBarHidden(NamePlate? plate)
    {
        if (!IsHidden || !_settings.HideNameplates || plate == null)
            return;

        HideGameObject(plate.Lifebar);
    }

    private void ScanAndHide()
    {
        int count = 0;

        if (_settings.HideNameplates)
            count += HideNameplates();

        if (_settings.HideDamageNumbers)
            count += HideDamageNumbers();

        if (_settings.HideTargetRings)
            count += HideTargetRings();

        if (_settings.HideXPOrbs)
            count += HideXPOrbs();

        if (_settings.HideCastBars)
            count += HideCastBars();

        if (_settings.HideOtherWorldText)
            count += HideOtherWorldText();

        if (_settings.EnableLogging)
            _log.LogDebug($"Scan complete: {count} elements hidden");
    }

    private int HideNameplates()
    {
        int count = 0;
        foreach (var plate in UnityEngine.Object.FindObjectsOfType<NamePlate>())
            count += HideNameplateElements(plate);

        return count;
    }

    private int HideNameplateElements(NamePlate plate)
    {
        if (plate == null)
            return 0;

        int count = 0;

        var renderer = plate.GetComponent<Renderer>();
        if (renderer != null && renderer.enabled)
        {
            renderer.enabled = false;
            _disabledRenderers.Add(renderer);
            count++;
        }

        count += HideGameObject(plate.Lifebar);
        count += HideGameObject(plate.TargetInd);
        return count;
    }

    private int HideGameObject(GameObject gameObject)
    {
        if (gameObject == null || !gameObject.activeSelf)
            return 0;

        gameObject.SetActive(false);
        _disabledGameObjects.Add(gameObject);
        return 1;
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

        if (_settings.EnableLogging)
            _log.LogDebug($"Restored {rendererCount} renderers, {gameObjectCount} game objects");
    }
}
