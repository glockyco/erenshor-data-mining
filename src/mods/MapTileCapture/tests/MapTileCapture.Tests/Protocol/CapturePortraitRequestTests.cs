using MapTileCapture.Protocol;
using Newtonsoft.Json;
using Xunit;

namespace MapTileCapture.Tests.Protocol;

public class CapturePortraitRequestTests
{
    private static CapturePortraitRequest Parse(
        string source,
        string preset = PortraitPreset.Name
    ) =>
        JsonConvert.DeserializeObject<CapturePortraitRequest>(
            $$"""
            {
              "type": "capture_portrait",
              "subject": "Faith",
              "stableKey": "character:faith",
              "preset": "{{preset}}",
              "outputPath": "Z:\\captures\\Faith.png",
              "source": {{source}}
            }
            """
        )!;

    [Fact]
    public void ResourcesSource_IsRunnable()
    {
        var request = Parse("""{"resourcesPath": "npcs/plane of soluna/Zenith"}""");

        Assert.Null(request.Problem());
        Assert.Equal("npcs/plane of soluna/Zenith", request.Source!.ResourcesPath);
    }

    [Fact]
    public void PlacedSceneSource_IsRunnable()
    {
        var request = Parse(
            """{"scene": "Duskenlight", "objectName": "SM_Prop_Brazier_01 (1)", "npcName": "Ceremonial Brazier", "position": [485.82, 65.42, 397.38], "landing": [485.82, 65.42, 397.38]}"""
        );

        Assert.Null(request.Problem());
        Assert.Equal("Ceremonial Brazier", request.Source!.NpcName);
        Assert.Equal(new[] { 485.82f, 65.42f, 397.38f }, request.Source.Position);
    }

    [Fact]
    public void ScenePrefabSource_IsRunnableWithoutPosition()
    {
        var request = Parse(
            """{"scene": "PlaneOfSoluna", "objectName": "Faith", "landing": [275.6, 327.1, 1346.7]}"""
        );

        Assert.Null(request.Problem());
    }

    [Theory]
    [InlineData("""{}""")]
    [InlineData(
        """{"resourcesPath": "npcs/Zenith", "scene": "Azure", "objectName": "Zenith", "landing": [0, 0, 0]}"""
    )]
    public void Source_MustNameExactlyOneOrigin(string source)
    {
        Assert.Equal(
            "The source must name either a resources path or a scene.",
            Parse(source).Problem()
        );
    }

    [Fact]
    public void SceneSource_NeedsALandingForThePlayer()
    {
        var request = Parse(
            """{"scene": "Reliquary", "objectName": "D", "position": [268.68, -2.12, 339.01]}"""
        );

        Assert.Equal("A scene source must give a landing of three coordinates.", request.Problem());
    }

    [Fact]
    public void SceneSource_RejectsAShortPosition()
    {
        var request = Parse(
            """{"scene": "Reliquary", "objectName": "D", "position": [1, 2], "landing": [0, 0, 0]}"""
        );

        Assert.Equal("A position must have three coordinates.", request.Problem());
    }

    [Fact]
    public void ResourcesSource_TakesNoSceneDetails()
    {
        var request = Parse("""{"resourcesPath": "npcs/Zenith", "landing": [0, 0, 0]}""");

        Assert.Equal(
            "A resources source takes no object name, NPC name, position, or landing.",
            request.Problem()
        );
    }

    [Fact]
    public void Request_OfAnotherPreset_IsRefused()
    {
        var request = Parse("""{"resourcesPath": "npcs/Zenith"}""", preset: "portrait-0");

        Assert.Equal(
            $"The mod captures with preset {PortraitPreset.Name}, not portrait-0.",
            request.Problem()
        );
    }

    [Fact]
    public void Request_WithoutOutputPath_IsRefused()
    {
        var request = Parse("""{"resourcesPath": "npcs/Zenith"}""");
        request.OutputPath = "";

        Assert.Equal("The request names no output path.", request.Problem());
    }
}
