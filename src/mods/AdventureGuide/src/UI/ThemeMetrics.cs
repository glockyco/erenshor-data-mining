namespace AdventureGuide.UI;

internal readonly struct ThemeMetrics
{
    private readonly float _scale;

    private ThemeMetrics(float scale) => _scale = scale;

    public static ThemeMetrics For(float scale) => new(scale);

    public float FramePaddingX => 4f * _scale;
    public float FramePaddingY => 3f * _scale;
    public float ItemSpacingX => 8f * _scale;
    public float ItemSpacingY => 4f * _scale;
    public float IndentSpacing => 16f * _scale;
    public float TabRounding => 4f * _scale;
    public float ChildBorderSize => _scale;
}
