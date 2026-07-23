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

    [Theory]
    [InlineData((int)DirectPlacementGateState.Absent, false)]
    [InlineData((int)DirectPlacementGateState.Unresolved, true)]
    [InlineData((int)DirectPlacementGateState.Incomplete, true)]
    [InlineData((int)DirectPlacementGateState.Completed, false)]
    public void Direct_placement_gate_state_controls_respawn_marker(
        int gateState,
        bool expectedSuppression
    )
    {
        Assert.Equal(
            expectedSuppression,
            DirectPlacementPolicy.ShouldSuppressRespawn(
                characterUnlockIsAmbiguous: false,
                hasSourceScript: false,
                (DirectPlacementGateState)gateState
            )
        );
    }

    [Fact]
    public void Character_unlock_ambiguity_suppresses_even_without_a_gate()
    {
        Assert.True(
            DirectPlacementPolicy.ShouldSuppressRespawn(
                characterUnlockIsAmbiguous: true,
                hasSourceScript: false,
                DirectPlacementGateState.Absent
            )
        );
    }

    [Fact]
    public void Character_unlock_ambiguity_suppresses_even_after_gate_completion()
    {
        Assert.True(
            DirectPlacementPolicy.ShouldSuppressRespawn(
                characterUnlockIsAmbiguous: true,
                hasSourceScript: false,
                DirectPlacementGateState.Completed
            )
        );
    }

    [Fact]
    public void Source_script_suppresses_even_without_a_gate()
    {
        Assert.True(
            DirectPlacementPolicy.ShouldSuppressRespawn(
                characterUnlockIsAmbiguous: false,
                hasSourceScript: true,
                DirectPlacementGateState.Absent
            )
        );
    }

    [Fact]
    public void Source_script_suppresses_even_after_gate_completion()
    {
        Assert.True(
            DirectPlacementPolicy.ShouldSuppressRespawn(
                characterUnlockIsAmbiguous: false,
                hasSourceScript: true,
                DirectPlacementGateState.Completed
            )
        );
    }
}
