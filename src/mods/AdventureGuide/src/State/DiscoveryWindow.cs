namespace AdventureGuide.State;

/// <summary>
/// Schedules a bounded live-entity discovery window. The first attempt is due
/// immediately after scheduling; later attempts are one second apart.
/// </summary>
public sealed class DiscoveryWindow
{
    public const int MaxAttempts = 5;
    public const float AttemptInterval = 1f;

    private float _timer;
    private int _attemptsRemaining;

    public int AttemptsRemaining => _attemptsRemaining;

    public bool IsComplete => _attemptsRemaining == 0;

    public void Schedule()
    {
        _attemptsRemaining = MaxAttempts;
        _timer = 0f;
    }

    public bool Advance(float deltaTime)
    {
        if (_attemptsRemaining <= 0)
            return false;

        _timer -= deltaTime;
        if (_timer > 0f)
            return false;

        _timer = AttemptInterval;
        _attemptsRemaining--;
        return true;
    }
}
