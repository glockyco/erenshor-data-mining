using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class NavigationRuntimePolicyTests
{
    [Fact]
    public void Billboard_without_a_player_has_no_target()
    {
        Assert.Equal(
            BillboardUpdateTarget.None,
            BillboardUpdatePolicy.Select(
                hasPlayer: false,
                firstPersonCameraActive: false,
                droneMode: false
            )
        );
    }

    [Fact]
    public void Billboard_third_person_uses_the_game_camera()
    {
        Assert.Equal(
            BillboardUpdateTarget.GameCamera,
            BillboardUpdatePolicy.Select(
                hasPlayer: true,
                firstPersonCameraActive: false,
                droneMode: false
            )
        );
    }

    [Fact]
    public void Billboard_drone_camera_wins_in_third_person()
    {
        Assert.Equal(
            BillboardUpdateTarget.DroneCamera,
            BillboardUpdatePolicy.Select(
                hasPlayer: true,
                firstPersonCameraActive: false,
                droneMode: true
            )
        );
    }

    [Fact]
    public void Billboard_first_person_wins_over_drone_mode()
    {
        Assert.Equal(
            BillboardUpdateTarget.FirstPersonCamera,
            BillboardUpdatePolicy.Select(
                hasPlayer: true,
                firstPersonCameraActive: true,
                droneMode: true
            )
        );
    }
}
