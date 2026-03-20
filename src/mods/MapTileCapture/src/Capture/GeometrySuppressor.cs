using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using MapTileCapture.Protocol;

namespace MapTileCapture.Capture;

/// <summary>
/// Suppresses visual noise (characters, particles, UI, fog, etc.) for map tile captures.
/// Snapshots all original state on construction and restores it on Dispose.
/// </summary>
internal sealed class GeometrySuppressor : IDisposable
{
    // --- Snapshot storage ---
    private readonly float _origTimeScale;
    private readonly bool _origFog;
    private readonly UnityEngine.Rendering.AmbientMode _origAmbientMode;
    private readonly Color _origAmbientLight;
    private readonly CameraClearFlags _origClearFlags;
    private readonly Color _origBackgroundColor;
    private readonly int _origCullingMask;

    private readonly Camera _camera;

    // Post-processing components to disable during capture
    private readonly Behaviour? _ppLayer;
    private readonly Behaviour? _vibrance;

    // Temporary capture light for indoor/no-sun zones (null for outdoor zones)
    private readonly GameObject? _captureLight;

    // Per-object snapshots
    private readonly List<(GameObject go, bool wasActive)> _deactivatedObjects = new();
    private readonly List<(Renderer renderer, bool wasEnabled)> _disabledRenderers = new();
    private readonly List<(Canvas canvas, bool wasEnabled)> _disabledCanvases = new();

    public GeometrySuppressor(Camera camera, bool hideRoofs, bool usingSun, ExclusionRule[]? exclusionRules)
    {
        _camera = camera;

        // --- Post-processing ---
        // Disable PostProcessLayer and VibranceEffect for neutral map colors.
        // These effects add warmth and saturation correct for gameplay but wrong
        // for map tiles. String-based GetComponent avoids assembly-load issues.
        _ppLayer = camera.GetComponent("PostProcessLayer") as Behaviour;
        _vibrance = camera.GetComponent("VibranceEffect") as Behaviour;
        if (_ppLayer != null) _ppLayer.enabled = false;
        if (_vibrance != null) _vibrance.enabled = false;

        // --- Global state snapshots ---
        _origTimeScale = Time.timeScale;
        Time.timeScale = 0f;

        _origFog = RenderSettings.fog;
        RenderSettings.fog = false;

        _origAmbientMode = RenderSettings.ambientMode;
        _origAmbientLight = RenderSettings.ambientLight;
        if (!usingSun)
        {
            // Indoor/cave zones have no sun. Their baked lightmaps are designed for
            // torch-lit gameplay and produce near-black map tiles without real-time
            // light contribution. Add a neutral overhead directional light and boost
            // ambient so the geometry is legible without washing out baked detail.
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = Color.white * 0.6f;

            _captureLight = new GameObject("__MapTileCapture_Light");
            var lt = _captureLight.AddComponent<Light>();
            lt.type = LightType.Directional;
            lt.color = Color.white;
            lt.intensity = 1.0f;
            lt.shadows = LightShadows.None;
            _captureLight.transform.eulerAngles = new Vector3(50f, -30f, 0f);
        }

        // --- Camera ---
        _origClearFlags = camera.clearFlags;
        _origBackgroundColor = camera.backgroundColor;
        _origCullingMask = camera.cullingMask;

        // --- Roof-layer root GameObjects ---
        // Deactivate root GameObjects on the Roof layer, matching the original
        // TileScreenshotter. SetActive(false) kills the entire hierarchy, which
        // also hides children on other layers (e.g. Default). A cullingMask
        // approach would only hide renderers whose own layer is Roof, leaving
        // children on Default visible — producing colored artifacts in captures.
        if (hideRoofs)
        {
            foreach (var rootGo in SceneManager.GetActiveScene().GetRootGameObjects())
            {
                if (rootGo.layer == LayerMask.NameToLayer("Roof") && rootGo.activeSelf)
                {
                    _deactivatedObjects.Add((rootGo, true));
                    rootGo.SetActive(false);
                }
            }
        }

        // --- SpawnPoints (visible gameplay markers, not map content) ---
        foreach (var sp in UnityEngine.Object.FindObjectsOfType<SpawnPoint>())
        {
            var go = sp.gameObject;
            _deactivatedObjects.Add((go, go.activeSelf));
            go.SetActive(false);
        }

        // --- Characters (skip MiningNode/TreasureChest) ---
        foreach (var character in UnityEngine.Object.FindObjectsOfType<Character>())
        {
            if (character.MiningNode)
                continue;
            if (character.MyNPC != null && character.MyNPC.TreasureChest)
                continue;

            var go = character.gameObject;
            _deactivatedObjects.Add((go, go.activeSelf));
            go.SetActive(false);
        }

        // --- ParticleSystemRenderer ---
        foreach (var psr in UnityEngine.Object.FindObjectsOfType<ParticleSystemRenderer>())
        {
            _disabledRenderers.Add((psr, psr.enabled));
            psr.enabled = false;
        }

        // --- Canvas ---
        foreach (var canvas in UnityEngine.Object.FindObjectsOfType<Canvas>())
        {
            _disabledCanvases.Add((canvas, canvas.enabled));
            canvas.enabled = false;
        }

        // --- NamePlate ---
        foreach (var plate in UnityEngine.Object.FindObjectsOfType<NamePlate>())
        {
            var renderer = plate.GetComponent<Renderer>();
            if (renderer != null)
            {
                _disabledRenderers.Add((renderer, renderer.enabled));
                renderer.enabled = false;
            }
        }

        // --- DmgPop.Num ---
        foreach (var pop in UnityEngine.Object.FindObjectsOfType<DmgPop>())
        {
            if (pop.Num == null) continue;
            var renderer = pop.Num.GetComponent<Renderer>();
            if (renderer != null)
            {
                _disabledRenderers.Add((renderer, renderer.enabled));
                renderer.enabled = false;
            }
        }

        // --- Character.TargetRing ---
        // Characters were already deactivated above, but iterate for any remaining
        // (MiningNode/TreasureChest characters that were skipped).
        foreach (var character in UnityEngine.Object.FindObjectsOfType<Character>())
        {
            var ring = character.TargetRing;
            if (ring != null)
            {
                _deactivatedObjects.Add((ring, ring.activeSelf));
                ring.SetActive(false);
            }
        }

        // --- XPBub ---
        foreach (var orb in UnityEngine.Object.FindObjectsOfType<XPBub>())
        {
            var renderer = orb.GetComponent<Renderer>();
            if (renderer != null)
            {
                _disabledRenderers.Add((renderer, renderer.enabled));
                renderer.enabled = false;
            }
        }

        // --- FlashUIColors.CastBar ---
        foreach (var flash in UnityEngine.Object.FindObjectsOfType<FlashUIColors>())
        {
            if (flash.CastBar == null) continue;
            var renderer = flash.CastBar.GetComponent<Renderer>();
            if (renderer != null)
            {
                _disabledRenderers.Add((renderer, renderer.enabled));
                renderer.enabled = false;
            }
        }

        // --- World-space TextMeshPro ---
        foreach (var tmp in UnityEngine.Object.FindObjectsOfType<TextMeshPro>())
        {
            // Skip objects already handled by NamePlate / DmgPop
            if (tmp.GetComponent<NamePlate>() != null) continue;
            if (tmp.GetComponent<DmgPop>() != null) continue;
            if (tmp.GetComponentInParent<DmgPop>() != null) continue;

            var renderer = tmp.GetComponent<Renderer>();
            if (renderer != null)
            {
                _disabledRenderers.Add((renderer, renderer.enabled));
                renderer.enabled = false;
            }
        }

        // --- Per-zone exclusion rules ---
        if (exclusionRules != null)
            ApplyExclusionRules(exclusionRules);
    }

    public void Dispose()
    {
        // Restore in reverse order to unwind nested dependencies correctly.

        // Per-object renderers
        for (int i = _disabledRenderers.Count - 1; i >= 0; i--)
        {
            var (renderer, wasEnabled) = _disabledRenderers[i];
            if (renderer != null) // Unity null check — object may have been destroyed
                renderer.enabled = wasEnabled;
        }

        // Canvases
        for (int i = _disabledCanvases.Count - 1; i >= 0; i--)
        {
            var (canvas, wasEnabled) = _disabledCanvases[i];
            if (canvas != null)
                canvas.enabled = wasEnabled;
        }

        // GameObjects
        for (int i = _deactivatedObjects.Count - 1; i >= 0; i--)
        {
            var (go, wasActive) = _deactivatedObjects[i];
            if (go != null)
                go.SetActive(wasActive);
        }

        // Post-processing
        if (_ppLayer != null) _ppLayer.enabled = true;
        if (_vibrance != null) _vibrance.enabled = true;

        // Camera
        _camera.clearFlags = _origClearFlags;
        _camera.backgroundColor = _origBackgroundColor;
        _camera.cullingMask = _origCullingMask;

        // Temporary capture light
        if (_captureLight != null)
            UnityEngine.Object.Destroy(_captureLight);

        // Global state
        RenderSettings.ambientMode = _origAmbientMode;
        RenderSettings.ambientLight = _origAmbientLight;
        RenderSettings.fog = _origFog;
        Time.timeScale = _origTimeScale;
    }

    private void ApplyExclusionRules(ExclusionRule[] rules)
    {
        foreach (var renderer in UnityEngine.Object.FindObjectsOfType<Renderer>())
        {
            foreach (var rule in rules)
            {
                if (MatchesRule(renderer, rule))
                {
                    _disabledRenderers.Add((renderer, renderer.enabled));
                    renderer.enabled = false;
                    break; // One match is sufficient
                }
            }
        }
    }

    private static bool MatchesRule(Renderer renderer, ExclusionRule rule)
    {
        var goName = renderer.gameObject.name;

        if (rule.NameExact != null && !string.Equals(goName, rule.NameExact, StringComparison.Ordinal))
            return false;

        if (rule.NameContains != null && goName.IndexOf(rule.NameContains, StringComparison.OrdinalIgnoreCase) < 0)
            return false;

        if (rule.PositionAbove.HasValue && renderer.transform.position.y <= rule.PositionAbove.Value)
            return false;

        // At least one predicate must be specified; if all are null, don't match anything.
        return rule.NameExact != null || rule.NameContains != null || rule.PositionAbove.HasValue;
    }
}
