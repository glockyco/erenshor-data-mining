// Interface for steps to report their progress (0.0 to 1.0) and status message
public interface IProgressReporter
{
    void Report(float progress, string message);
}
