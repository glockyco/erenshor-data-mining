using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class ArrowCameraTests
{
    [Fact]
    public void Arrow_view_policy_changes_with_camera_mode_without_a_scene_reload()
    {
        Assert.Equal(
            BillboardUpdateTarget.GameCamera,
            BillboardUpdatePolicy.Select(true, false, false)
        );
        Assert.Equal(
            BillboardUpdateTarget.FirstPersonCamera,
            BillboardUpdatePolicy.Select(true, true, false)
        );
        Assert.Equal(
            BillboardUpdateTarget.DroneCamera,
            BillboardUpdatePolicy.Select(true, false, true)
        );
        Assert.Equal(
            BillboardUpdateTarget.GameCamera,
            BillboardUpdatePolicy.Select(true, false, false)
        );
        Assert.Equal(BillboardUpdateTarget.None, BillboardUpdatePolicy.Select(false, true, true));
    }
}
