namespace MapTileCapture.Protocol;

/// <summary>
/// The camera, light, and framing of a portrait capture. A request names the
/// preset that it expects, so captures of different presets never mix in one
/// review. Change <see cref="Name"/> together with any value here.
/// </summary>
public static class PortraitPreset
{
    public const string Name = "portrait-1";

    /// <summary>Width and height of each render, in pixels.</summary>
    public const int RenderSize = 1024;

    /// <summary>
    /// The layer that only the portrait camera renders. The game names layers
    /// 0 to 14, so the last layer is free.
    /// </summary>
    public const int StudioLayer = 31;

    /// <summary>Vertical field of view of the perspective camera, in degrees.</summary>
    public const float FieldOfView = 25f;

    /// <summary>
    /// Camera direction from the subject: turned from its front toward its
    /// right and raised above it, in degrees.
    /// </summary>
    public const float CameraYaw = -25f;
    public const float CameraPitch = -12f;

    /// <summary>
    /// Space around the subject once the second render frames it, as a
    /// factor of the subject's larger side.
    /// </summary>
    public const float FrameMargin = 1.08f;

    public const float KeyLightIntensity = 1.0f;
    public const float KeyLightPitch = 35f;
    public const float KeyLightYaw = 40f;
    public const float FillLightIntensity = 0.35f;
    public const float FillLightPitch = 10f;
    public const float FillLightYaw = -60f;
    public const float AmbientLevel = 0.45f;

    /// <summary>Seconds that looping effects run before the render.</summary>
    public const float EffectSeconds = 1.5f;

    /// <summary>Alpha above which a pixel belongs to the subject's box.</summary>
    public const byte SubjectAlpha = 32;

    /// <summary>Transparent pixels kept around the subject in the output.</summary>
    public const int CropMargin = 16;
}
