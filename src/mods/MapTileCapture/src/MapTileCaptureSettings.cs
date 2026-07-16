namespace MapTileCapture;

/// <summary>Runtime-tunable capture settings shared by both loader adapters.</summary>
internal static class MapTileCaptureSettings
{
    public static float IndoorDirectionalIntensity = 0.7f;
    public static float IndoorAmbientIntensity = 0.45f;
    public static float IndoorDirectionalPitch = 50f;
    public static float IndoorDirectionalYaw = -30f;

    public static float BackgroundR = 0.06f;
    public static float BackgroundG = 0.07f;
    public static float BackgroundB = 0.10f;

    public static int DefaultStabilityFrames = 10;
    public static float DefaultSceneLoadTimeoutSecs = 30f;
}
