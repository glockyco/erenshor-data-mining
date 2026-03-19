using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace MapTileCapture.Capture;

/// <summary>
/// Rule for excluding specific renderers from the capture by name or position.
/// Deserialized from the capture_zone message.
/// </summary>
public sealed class ExclusionRule
{
    public string? NameExact { get; set; }
    public string? NameContains { get; set; }
    public float? PositionAbove { get; set; }
}

/// <summary>
/// Suppresses visual noise (characters, particles, UI, fog, etc.) for map tile captures.
/// Snapshots all original state on construction and restores it on Dispose.
/// </summary>
internal sealed class GeometrySuppressor : IDisposable
{
    // --- Snapshot storage ---
    private readonly float _origTimeScale;
    private readonly bool _origFog;
    private readonly int _origLodBias; // stored as raw bits to avoid float comparison issues
    private readonly int _origMaxLodLevel;
    private readonly CameraClearFlags _origClearFlags;
    private readonly Color _origBackgroundColor;
    private readonly int _origCullingMask;
    private readonly bool _hideRoofs;

    private readonly Camera _camera;

    // WorldFogController
    private readonly GameObject? _fogControllerGo;
    private readonly bool _origFogControllerActive;

    // Per-object snapshots
    private readonly List<(GameObject go, bool wasActive)> _deactivatedObjects = new();
    private readonly List<(Renderer renderer, bool wasEnabled)> _disabledRenderers = new();
    private readonly List<(Canvas canvas, bool wasEnabled)> _disabledCanvases = new();

    public GeometrySuppressor(Camera camera, bool hideRoofs, ExclusionRule[]? exclusionRules)
    {
        _camera = camera;
        _hideRoofs = hideRoofs;

        // --- Global state snapshots ---
        _origTimeScale = Time.timeScale;
        Time.timeScale = 0f;

        _origFog = RenderSettings.fog;
        RenderSettings.fog = false;

        _origLodBias = BitConverter.ToInt32(BitConverter.GetBytes(QualitySettings.lodBias), 0);
        QualitySettings.lodBias = float.MaxValue;

        _origMaxLodLevel = QualitySettings.maximumLODLevel;
        QualitySettings.maximumLODLevel = 0;

        _origClearFlags = camera.clearFlags;
        camera.clearFlags = CameraClearFlags.SolidColor;

        _origBackgroundColor = camera.backgroundColor;
        camera.backgroundColor = new Color(0f, 0f, 0f, 0f);

        _origCullingMask = camera.cullingMask;
        if (hideRoofs)
            camera.cullingMask &= ~(1 << LayerMask.NameToLayer("Roof"));

        // --- WorldFogController ---
        var fogController = UnityEngine.Object.FindObjectOfType<WorldFogController>();
        if (fogController != null)
        {
            _fogControllerGo = fogController.gameObject;
            _origFogControllerActive = _fogControllerGo.activeSelf;
            _fogControllerGo.SetActive(false);
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

        // WorldFogController
        if (_fogControllerGo != null)
            _fogControllerGo.SetActive(_origFogControllerActive);

        // Camera
        _camera.clearFlags = _origClearFlags;
        _camera.backgroundColor = _origBackgroundColor;
        if (_hideRoofs)
            _camera.cullingMask = _origCullingMask;

        // Global state
        QualitySettings.maximumLODLevel = _origMaxLodLevel;
        QualitySettings.lodBias = BitConverter.ToSingle(BitConverter.GetBytes(_origLodBias), 0);
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

        if (rule.NameContains != null && goName.IndexOf(rule.NameContains, StringComparison.Ordinal) < 0)
            return false;

        if (rule.PositionAbove.HasValue && renderer.transform.position.y <= rule.PositionAbove.Value)
            return false;

        // At least one predicate must be specified; if all are null, don't match anything.
        return rule.NameExact != null || rule.NameContains != null || rule.PositionAbove.HasValue;
    }
}
