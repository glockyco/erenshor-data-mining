using System.Diagnostics;
using System.Text;

namespace AdventureGuide.Diagnostics;

/// <summary>
/// Per-frame ring-buffer profiler for the hot path in Plugin.Update().
/// All ring buffers are allocated once at startup; Record() is allocation-free.
///
/// Call pattern at each instrumented site:
///   long pt = Stopwatch.GetTimestamp();
///   SomeExpensiveCall();
///   GuideProfiler.SomeSlot.Record(pt);
/// </summary>
internal static class GuideProfiler
{
    // Label width is fixed at 15 chars for column-aligned report output.
    internal static readonly ProfileSlot LiveState       = new("LiveState      ");
    internal static readonly ProfileSlot MarkerApply     = new("MarkerApply    ");
    internal static readonly ProfileSlot MarkerRecompute = new("MarkerRecompute");
    internal static readonly ProfileSlot SelectorTick    = new("SelectorTick   ");
    internal static readonly ProfileSlot NavUpdate       = new("NavUpdate      ");
    internal static readonly ProfileSlot GroundPath      = new("GroundPath     ");
    internal static readonly ProfileSlot MarkerSysUpdate = new("MarkerSysUpdate");

    private static readonly ProfileSlot[] AllSlots =
    {
        LiveState, MarkerApply, MarkerRecompute,
        SelectorTick, NavUpdate, GroundPath, MarkerSysUpdate,
    };

    /// <summary>
    /// Build a formatted report of all slots. Allocates for display only —
    /// never called from the hot path.
    /// </summary>
    internal static string DumpReport()
    {
        var sb = new StringBuilder();
        sb.AppendLine("Per-frame profiler (last 512 samples per slot):");
        sb.AppendLine();
        foreach (var slot in AllSlots)
            sb.AppendLine(slot.Summarize());
        return sb.ToString();
    }

    /// <summary>Zero all ring buffers so the next report reflects fresh data.</summary>
    internal static void ResetAll()
    {
        foreach (var slot in AllSlots)
            slot.Reset();
    }
}

/// <summary>
/// Single named profiling slot backed by a 512-entry power-of-two ring buffer.
/// The hot path (Record) performs one subtraction, two integer arithmetic ops,
/// and one array write — no heap allocation.
/// </summary>
internal sealed class ProfileSlot
{
    private const int Capacity = 512; // power of two
    private const int Mask     = Capacity - 1;

    // Computed once; valid for the lifetime of the process.
    private static readonly double TicksPerMs = Stopwatch.Frequency / 1000.0;

    private readonly string _label;
    private readonly long[] _samples = new long[Capacity];
    private int _head;
    private int _count;

    internal ProfileSlot(string label) => _label = label;

    /// <summary>
    /// Record elapsed time since <paramref name="startTick"/>.
    /// <paramref name="startTick"/> must come from Stopwatch.GetTimestamp()
    /// captured immediately before the measured block.
    /// </summary>
    internal void Record(long startTick)
    {
        _samples[_head] = Stopwatch.GetTimestamp() - startTick;
        _head           = (_head + 1) & Mask;
        if (_count < Capacity) _count++;
    }

    internal void Reset()
    {
        _head  = 0;
        _count = 0;
    }

    /// <summary>
    /// Build a one-line summary: avg / p50 / p99 / max / sample count.
    /// Allocates a temp copy for sorting; call only from diagnostic code.
    /// </summary>
    internal string Summarize()
    {
        if (_count == 0)
            return $"{_label}  (no samples)";

        // Copy the active portion of the ring buffer into a temp array for
        // an in-place sort. _count <= 512, so this is negligible.
        var buf   = new long[_count];
        int start = (_head - _count + Capacity) & Mask;
        for (int i = 0; i < _count; i++)
            buf[i] = _samples[(start + i) & Mask];
        Array.Sort(buf);

        double sum = 0;
        for (int i = 0; i < buf.Length; i++) sum += buf[i];
        double avg = sum / buf.Length;

        double ToMs(long t)   => t / TicksPerMs;
        double AvgMs()        => avg / TicksPerMs;
        double Pct(double p)  => ToMs(buf[(int)(p * (buf.Length - 1))]);

        return $"{_label}  avg={AvgMs():F3}ms  p50={Pct(0.50):F3}ms  "
             + $"p99={Pct(0.99):F3}ms  max={ToMs(buf[buf.Length - 1]):F3}ms  "
             + $"n={_count}";
    }
}
