using MapTileCapture.Protocol;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

namespace MapTileCapture.Capture;

/// <summary>A capture that cannot produce a portrait, with the reason for the review.</summary>
internal sealed class PortraitException : Exception
{
    public PortraitException(string message)
        : base(message) { }
}

/// <summary>What a portrait capture produced.</summary>
internal sealed class PortraitResult
{
    public string ObjectName { get; set; } = "";
    public int Width { get; set; }
    public int Height { get; set; }
    public int Renderers { get; set; }

    /// <summary>The subject reached the edge of the framing render, so the frame may cut it off.</summary>
    public bool Clipped { get; set; }

    public double MeanLuminance { get; set; }
}

/// <summary>
/// Renders one character alone, as the player's camera shows it, to a PNG with
/// a transparent background (design D3 of restore-missing-wiki-images).
///
/// A copy of the subject goes on a layer that only a temporary camera renders,
/// so the scene, the player, other characters, and the UI never appear, and
/// nothing in the scene needs hiding. Scene lights stop lighting that layer
/// while two lights of the preset and a flat ambient light the copy. Every
/// change to game state is undone, and every temporary object destroyed, when
/// the capture ends, whether it succeeds or fails.
/// </summary>
internal static class PortraitStudio
{
    private static readonly Vector3 StudioPosition = new(0f, 5000f, 0f);

    public static PortraitResult Capture(
        GameObject source,
        int playerCullingMask,
        string outputPath
    )
    {
        using var cleanup = new CleanupStack();

        // Instantiated under an inactive parent, the copy runs no Awake or Start.
        var studio = new GameObject("PortraitStudio");
        cleanup.Push(() => Object.Destroy(studio));
        studio.SetActive(false);
        studio.transform.position = StudioPosition;
        var subject = Object.Instantiate(source, studio.transform);
        subject.transform.localPosition = Vector3.zero;
        subject.transform.localRotation = Quaternion.identity;
        // A character that its scene keeps off until an event, or a disabled
        // duplicate of one, is captured as the game shows it once it is on.
        subject.SetActive(true);

        ShowAsGameStartsIt(subject);
        RemoveBehaviour(subject);
        KeepWhatThePlayerSees(subject, playerCullingMask);

        LightOnlyWithPreset(cleanup);
        studio.SetActive(true);
        Pose(subject);

        var meshes = new List<Renderer>();
        var effects = new List<Renderer>();
        foreach (var renderer in subject.GetComponentsInChildren<Renderer>())
        {
            if (!renderer.enabled)
                continue;
            if (renderer is ParticleSystemRenderer)
                effects.Add(renderer);
            else
                meshes.Add(renderer);
        }
        if (meshes.Count == 0 && effects.Count == 0)
            throw new PortraitException(
                "The subject has no renderer that the player's camera shows."
            );

        // The first frame holds the bounds of the meshes, or of the effects
        // when the subject has no mesh.
        var framing = meshes.Count > 0 ? meshes : effects;
        var bounds = framing[0].bounds;
        foreach (var renderer in framing)
            bounds.Encapsulate(renderer.bounds);

        var direction =
            subject.transform.rotation
            * Quaternion.Euler(PortraitPreset.CameraPitch, PortraitPreset.CameraYaw, 0f)
            * Vector3.forward;
        var camera = CreateCamera(cleanup, bounds, direction);
        CreateLight(
            cleanup,
            direction,
            PortraitPreset.KeyLightIntensity,
            PortraitPreset.KeyLightPitch,
            PortraitPreset.KeyLightYaw
        );
        CreateLight(
            cleanup,
            direction,
            PortraitPreset.FillLightIntensity,
            PortraitPreset.FillLightPitch,
            PortraitPreset.FillLightYaw
        );

        int size = PortraitPreset.RenderSize;
        var target = new RenderTexture(size, size, 24, RenderTextureFormat.ARGB32)
        {
            antiAliasing = 4,
        };
        cleanup.Push(() =>
        {
            target.Release();
            Object.Destroy(target);
        });
        var readback = new Texture2D(size, size, TextureFormat.RGBA32, false);
        cleanup.Push(() => Object.Destroy(readback));
        camera.targetTexture = target;

        // The first render finds the subject in a frame that holds its bounds.
        // Each effect joins the framing when it alone stays close to the
        // meshes, such as a burning head or a sword's flame. It is measured in
        // a frame with room for that growth on any one side, so the frame's
        // edge cannot cut it short. Effects that spread far, such as a light
        // beam or a field of sparkles, show only within the crop, like a photo
        // crop. Each further render aims the camera at the framed subject and
        // narrows the view to fill the frame, until the subject leaves the
        // crop margin on every side; perspective makes one correction fall
        // slightly short.
        foreach (var effect in effects)
            effect.enabled = meshes.Count == 0;
        var subjectBox = RenderSubject(camera, target, readback, size);
        bool clipped = PortraitImage.TouchesBorder(subjectBox, size, size);
        if (meshes.Count > 0 && effects.Count > 0)
        {
            AimAt(
                camera,
                subjectBox,
                size,
                PortraitPreset.FrameMargin * ((2f * PortraitPreset.EffectFramingGrowth) - 1f)
            );
            var meshBox = RenderSubject(camera, target, readback, size);
            var close = new List<Renderer>();
            foreach (var effect in effects)
            {
                effect.enabled = true;
                var withEffect = RenderSubject(camera, target, readback, size);
                effect.enabled = false;
                if (
                    !PortraitImage.TouchesBorder(withEffect, size, size)
                    && PortraitImage.StaysClose(
                        withEffect,
                        meshBox,
                        PortraitPreset.EffectFramingGrowth
                    )
                )
                    close.Add(effect);
            }
            foreach (var effect in close)
                effect.enabled = true;
            subjectBox = RenderSubject(camera, target, readback, size);
        }
        for (int aim = 0; aim < PortraitPreset.MaxAims; aim++)
        {
            AimAt(camera, subjectBox, size, PortraitPreset.FrameMargin);
            subjectBox = RenderSubject(camera, target, readback, size);
            if (PortraitImage.HasMargin(subjectBox, Margin(subjectBox), size, size))
                break;
        }
        clipped |= PortraitImage.TouchesBorder(subjectBox, size, size);

        foreach (var effect in effects)
            effect.enabled = true;
        var portrait = PortraitImage.Matte(
            Render(camera, target, readback, Color.black),
            Render(camera, target, readback, Color.white)
        );
        var crop = PortraitImage.MarginCrop(subjectBox, Margin(subjectBox), size, size);
        var pixels = PortraitImage.Crop(portrait, size, size, crop);

        var output = new Texture2D(crop.Width, crop.Height, TextureFormat.RGBA32, false);
        cleanup.Push(() => Object.Destroy(output));
        output.LoadRawTextureData(pixels);
        output.Apply(false);
        var directory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrEmpty(directory))
            Directory.CreateDirectory(directory);
        File.WriteAllBytes(outputPath, output.EncodeToPNG());

        return new PortraitResult
        {
            ObjectName = source.name,
            Width = crop.Width,
            Height = crop.Height,
            Renderers = meshes.Count + effects.Count,
            Clipped = clipped,
            MeanLuminance = PortraitImage.MeanLuminance(pixels),
        };
    }

    /// <summary>
    /// Applies the changes to the subject's look that the game makes when the
    /// character starts, because the copy runs none of its scripts.
    /// </summary>
    private static void ShowAsGameStartsIt(GameObject subject)
    {
        // Character.Start replaces the TargetRing child with an inactive ring
        // that appears only on the player's target.
        var character = subject.GetComponent<Character>();
        if (character != null)
        {
            var ring =
                character.TargetRing != null
                    ? character.TargetRing.transform
                    : subject.transform.Find("TargetRing");
            if (ring != null)
                Object.DestroyImmediate(ring.gameObject);
        }

        // NPC.Start gives the first active skinned mesh one of the colour
        // variations at random. The first variation keeps captures repeatable.
        var npc = subject.GetComponent<NPC>();
        if (npc != null && npc.Colorvariations is { Count: > 0 })
        {
            var body = subject
                .GetComponentsInChildren<SkinnedMeshRenderer>(true)
                .FirstOrDefault(renderer => ActiveBelow(renderer.transform, subject.transform));
            if (body != null)
                body.sharedMaterial = npc.Colorvariations[0];
        }

        // ModularPar.Update shows the modular body and its gear while the
        // player is near.
        var modular = subject.GetComponentInChildren<ModularPar>(true);
        if (modular != null && modular.Male != null && modular.Male.Cloak != null)
            modular.Male.Cloak.parent.gameObject.SetActive(true);
    }

    /// <summary>Whether every object from <paramref name="part"/> up to, not including, <paramref name="root"/> is active.</summary>
    private static bool ActiveBelow(Transform part, Transform root)
    {
        for (var current = part; current != root; current = current.parent)
        {
            if (!current.gameObject.activeSelf)
                return false;
        }
        return true;
    }

    /// <summary>
    /// Removes the scripts, sounds, navigation, and physics, so the copy only
    /// shows itself. A component that another needs goes in a later pass.
    /// </summary>
    private static void RemoveBehaviour(GameObject subject)
    {
        for (int pass = 0; pass < 8; pass++)
        {
            var scripts = subject.GetComponentsInChildren<MonoBehaviour>(true);
            if (scripts.Length == 0)
                break;
            foreach (var script in scripts)
                Object.DestroyImmediate(script);
        }
        foreach (var audio in subject.GetComponentsInChildren<AudioSource>(true))
            Object.DestroyImmediate(audio);
        foreach (var agent in subject.GetComponentsInChildren<NavMeshAgent>(true))
            Object.DestroyImmediate(agent);
        foreach (var body in subject.GetComponentsInChildren<Rigidbody>(true))
            Object.DestroyImmediate(body);
    }

    /// <summary>
    /// Keeps the renderers on layers that the player's camera shows, such as
    /// the body and its effects, and turns off the others, such as map icons.
    /// The kept renderers take their light from the preset alone.
    /// </summary>
    private static void KeepWhatThePlayerSees(GameObject subject, int playerCullingMask)
    {
        foreach (var renderer in subject.GetComponentsInChildren<Renderer>(true))
        {
            if (((playerCullingMask >> renderer.gameObject.layer) & 1) == 0)
            {
                renderer.enabled = false;
                continue;
            }
            renderer.lightProbeUsage = LightProbeUsage.Off;
            renderer.reflectionProbeUsage = ReflectionProbeUsage.Off;
        }
        foreach (var light in subject.GetComponentsInChildren<Light>(true))
            light.cullingMask = 1 << PortraitPreset.StudioLayer;
        foreach (var part in subject.GetComponentsInChildren<Transform>(true))
            part.gameObject.layer = PortraitPreset.StudioLayer;
    }

    private static void LightOnlyWithPreset(CleanupStack cleanup)
    {
        foreach (var light in Object.FindObjectsOfType<Light>())
        {
            int mask = light.cullingMask;
            light.cullingMask = mask & ~(1 << PortraitPreset.StudioLayer);
            cleanup.Push(() =>
            {
                if (light != null)
                    light.cullingMask = mask;
            });
        }

        var ambientMode = RenderSettings.ambientMode;
        var ambientLight = RenderSettings.ambientLight;
        var ambientIntensity = RenderSettings.ambientIntensity;
        var fog = RenderSettings.fog;
        cleanup.Push(() =>
        {
            RenderSettings.ambientMode = ambientMode;
            RenderSettings.ambientLight = ambientLight;
            RenderSettings.ambientIntensity = ambientIntensity;
            RenderSettings.fog = fog;
        });
        RenderSettings.ambientMode = AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(
            PortraitPreset.AmbientLevel,
            PortraitPreset.AmbientLevel,
            PortraitPreset.AmbientLevel
        );
        RenderSettings.ambientIntensity = 1f;
        RenderSettings.fog = false;
    }

    /// <summary>
    /// Freezes the animation in the first frame of its default state and runs
    /// the looping effects that start with the character. One-off effects,
    /// such as a summoning burst, and effects that only play on an event, stay off.
    /// </summary>
    private static void Pose(GameObject subject)
    {
        foreach (var animator in subject.GetComponentsInChildren<Animator>())
        {
            animator.Rebind();
            animator.Update(0f);
            animator.speed = 0f;
        }
        foreach (var effect in subject.GetComponentsInChildren<ParticleSystem>())
        {
            var main = effect.main;
            if (main.loop && main.playOnAwake)
            {
                effect.Simulate(PortraitPreset.EffectSeconds, false, true);
                effect.Pause(false);
                continue;
            }
            effect.Stop(false, ParticleSystemStopBehavior.StopEmittingAndClear);
            var renderer = effect.GetComponent<ParticleSystemRenderer>();
            if (renderer != null)
                renderer.enabled = false;
        }
    }

    private static Camera CreateCamera(CleanupStack cleanup, Bounds bounds, Vector3 direction)
    {
        var holder = new GameObject("PortraitCamera");
        cleanup.Push(() => Object.Destroy(holder));
        float radius = Mathf.Max(bounds.extents.magnitude, 0.01f);
        float distance =
            radius / Mathf.Sin(PortraitPreset.FieldOfView * 0.5f * Mathf.Deg2Rad) * 1.05f;
        holder.transform.position = bounds.center + (direction * distance);
        holder.transform.LookAt(bounds.center);

        var camera = holder.AddComponent<Camera>();
        camera.enabled = false;
        camera.cullingMask = 1 << PortraitPreset.StudioLayer;
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.fieldOfView = PortraitPreset.FieldOfView;
        camera.nearClipPlane = Mathf.Max(0.01f, distance - (radius * 2f));
        camera.farClipPlane = distance + (radius * 2f);
        camera.allowHDR = false;
        camera.allowMSAA = true;
        return camera;
    }

    private static void CreateLight(
        CleanupStack cleanup,
        Vector3 direction,
        float intensity,
        float pitch,
        float yaw
    )
    {
        var holder = new GameObject("PortraitLight");
        cleanup.Push(() => Object.Destroy(holder));
        holder.transform.rotation =
            Quaternion.LookRotation(-direction) * Quaternion.Euler(pitch, yaw, 0f);
        var light = holder.AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = intensity;
        light.cullingMask = 1 << PortraitPreset.StudioLayer;
        light.shadows = LightShadows.None;
    }

    /// <summary>The crop margin around a subject box: a fraction of its larger side.</summary>
    private static int Margin(PixelBox box) =>
        (int)Math.Round(Math.Max(box.Width, box.Height) * PortraitPreset.CropMarginFraction);

    /// <summary>Renders the subject over black and over white and returns the box of its visible pixels.</summary>
    private static PixelBox RenderSubject(
        Camera camera,
        RenderTexture target,
        Texture2D readback,
        int size
    )
    {
        var matte = PortraitImage.Matte(
            Render(camera, target, readback, Color.black),
            Render(camera, target, readback, Color.white)
        );
        return PortraitImage.AlphaBox(matte, size, size, PortraitPreset.SubjectAlpha)
            ?? throw new PortraitException("The subject left no visible pixel.");
    }

    /// <summary>
    /// Turns the camera toward the middle of the subject's box and sets the
    /// view so that the box, grown by <paramref name="frame"/>, fills the frame.
    /// </summary>
    private static void AimAt(Camera camera, PixelBox box, int size, float frame)
    {
        var centre = new Vector3(
            (box.MinX + box.MaxX + 1) * 0.5f / size,
            (box.MinY + box.MaxY + 1) * 0.5f / size,
            0f
        );
        float extent = Mathf.Max(box.Width, box.Height) / (float)size * frame;
        var ray = camera.ViewportPointToRay(centre);
        camera.transform.rotation = Quaternion.LookRotation(ray.direction, Vector3.up);
        float halfAngle = Mathf.Atan(Mathf.Tan(camera.fieldOfView * 0.5f * Mathf.Deg2Rad) * extent);
        camera.fieldOfView = 2f * halfAngle * Mathf.Rad2Deg;
    }

    private static byte[] Render(
        Camera camera,
        RenderTexture target,
        Texture2D readback,
        Color background
    )
    {
        camera.backgroundColor = background;
        camera.Render();
        var previous = RenderTexture.active;
        RenderTexture.active = target;
        try
        {
            readback.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0);
            readback.Apply(false);
        }
        finally
        {
            RenderTexture.active = previous;
        }
        return readback.GetRawTextureData();
    }
}
