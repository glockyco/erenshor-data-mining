using MapTileCapture.Capture;
using Xunit;

namespace MapTileCapture.Tests.Capture;

public class CleanupStackTests
{
    [Fact]
    public void Dispose_UndoesInReverseOrder()
    {
        var undone = new List<string>();
        var cleanup = new CleanupStack();
        cleanup.Push(() => undone.Add("lights"));
        cleanup.Push(() => undone.Add("camera"));
        cleanup.Push(() => undone.Add("copy"));

        cleanup.Dispose();

        Assert.Equal(["copy", "camera", "lights"], undone);
    }

    [Fact]
    public void Dispose_RunsEveryUndoAfterAFailure()
    {
        var undone = new List<string>();
        var cleanup = new CleanupStack();
        cleanup.Push(() => undone.Add("lights"));
        cleanup.Push(() => throw new InvalidOperationException("camera already gone"));
        cleanup.Push(() => undone.Add("copy"));

        var error = Assert.Throws<AggregateException>(cleanup.Dispose);

        Assert.Equal(["copy", "lights"], undone);
        Assert.Equal("camera already gone", Assert.Single(error.InnerExceptions).Message);
    }

    [Fact]
    public void Dispose_UndoesOnlyOnce()
    {
        int undone = 0;
        var cleanup = new CleanupStack();
        cleanup.Push(() => undone++);

        cleanup.Dispose();
        cleanup.Dispose();

        Assert.Equal(1, undone);
    }
}
