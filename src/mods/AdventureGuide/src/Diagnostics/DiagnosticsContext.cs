namespace AdventureGuide.Diagnostics;

internal readonly struct DiagnosticsContext
{
    public DiagnosticsContext(DiagnosticTrigger trigger, int correlationId, int parentSpanId)
    {
        Trigger = trigger;
        CorrelationId = correlationId;
        ParentSpanId = parentSpanId;
    }

    public DiagnosticTrigger Trigger { get; }

    public int CorrelationId { get; }

    public int ParentSpanId { get; }

    public static DiagnosticsContext Root(DiagnosticTrigger trigger, int correlationId = 0)
    {
        return new DiagnosticsContext(trigger, correlationId, parentSpanId: 0);
    }

    public DiagnosticsContext Child(int parentSpanId)
    {
        return new DiagnosticsContext(Trigger, CorrelationId, parentSpanId);
    }
}
