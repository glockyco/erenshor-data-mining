namespace AdventureGuide.State;

/// <summary>
/// Tracks fact dependencies for maintained derived guide views.
/// Evaluation of a derived node runs under a dependency collection scope; any
/// fact reads during that scope become reverse-dependency subscriptions.
/// </summary>
public sealed class GuideDependencyEngine
{
    private readonly Dictionary<GuideDerivedKey, HashSet<FactKey>> _factsByDerived = new();
    private readonly Dictionary<FactKey, HashSet<GuideDerivedKey>> _derivedByFact = new();
    private readonly Stack<Collector> _stack = new();

    public IDisposable BeginCollection(GuideDerivedKey derivedKey)
    {
        _stack.Push(new Collector(derivedKey));
        return new Scope(this);
    }

    public void RecordFact(FactKey factKey)
    {
        if (_stack.Count == 0)
            return;

        _stack.Peek().Facts.Add(factKey);
    }

    public IReadOnlyCollection<GuideDerivedKey> InvalidateFacts(IEnumerable<FactKey> factKeys)
    {
        var affected = new HashSet<GuideDerivedKey>();
        foreach (var factKey in factKeys)
        {
            if (_derivedByFact.TryGetValue(factKey, out var dependents))
                affected.UnionWith(dependents);
        }

        foreach (var derivedKey in affected)
            RemoveDerivedSubscriptions(derivedKey);

        return affected;
    }

    public void Clear()
    {
        _factsByDerived.Clear();
        _derivedByFact.Clear();
        _stack.Clear();
    }

    private void EndCollection()
    {
        var collector = _stack.Pop();
        RemoveDerivedSubscriptions(collector.DerivedKey);
        if (collector.Facts.Count == 0)
            return;

        _factsByDerived[collector.DerivedKey] = collector.Facts;
        foreach (var factKey in collector.Facts)
        {
            if (!_derivedByFact.TryGetValue(factKey, out var dependents))
            {
                dependents = new HashSet<GuideDerivedKey>();
                _derivedByFact[factKey] = dependents;
            }

            dependents.Add(collector.DerivedKey);
        }
    }

    private void RemoveDerivedSubscriptions(GuideDerivedKey derivedKey)
    {
        if (!_factsByDerived.TryGetValue(derivedKey, out var facts))
            return;

        foreach (var factKey in facts)
        {
            if (!_derivedByFact.TryGetValue(factKey, out var dependents))
                continue;

            dependents.Remove(derivedKey);
            if (dependents.Count == 0)
                _derivedByFact.Remove(factKey);
        }

        _factsByDerived.Remove(derivedKey);
    }

    private sealed class Scope : IDisposable
    {
        private readonly GuideDependencyEngine _owner;
        private bool _disposed;

        public Scope(GuideDependencyEngine owner) => _owner = owner;

        public void Dispose()
        {
            if (_disposed)
                return;

            _disposed = true;
            _owner.EndCollection();
        }
    }

    private sealed class Collector
    {
        public GuideDerivedKey DerivedKey { get; }
        public HashSet<FactKey> Facts { get; }

        public Collector(GuideDerivedKey derivedKey)
        {
            DerivedKey = derivedKey;
            Facts = new HashSet<FactKey>();
        }
    }
}
