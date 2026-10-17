using AdventureGuide.Data;

namespace AdventureGuide.State;

/// <summary>Indexes positive initialization rules, never their live truth values.</summary>
public sealed class EncounterProjection
{
    private readonly Dictionary<string, Source[]> _questSources = new(
        StringComparer.OrdinalIgnoreCase
    );
    private readonly Dictionary<string, Source[]> _accountSources = new(StringComparer.Ordinal);

    internal EncounterProjection(GuideData data, EncounterContext context)
    {
        var reverse =
            new Dictionary<(string Scope, string Key), HashSet<(string Scope, string Key)>>();
        foreach (var row in context.Completions)
        {
            var target = AddState(row.StateScope, row.StateKey);
            if (row.EventKind == "host_death")
                continue;

            foreach (var guard in context.EventConditions)
                if (guard.EncounterKey == row.EncounterKey && guard.EventKind == row.EventKind)
                    reverse[target].Add(AddState(guard.StateScope, guard.StateKey));
        }

        foreach (var state in reverse.Keys)
        {
            var reachable = new HashSet<(string Scope, string Key)>();
            var pending = new Stack<(string Scope, string Key)>();
            pending.Push(state);
            while (pending.Count > 0)
            {
                var source = pending.Pop();
                if (!reachable.Add(source))
                    continue;
                foreach (var predecessor in reverse[source])
                    pending.Push(predecessor);
            }
            var sources = new Source[reachable.Count];
            int index = 0;
            foreach (var source in reachable)
                sources[index++] = new Source(
                    source.Scope == "account",
                    source.Scope == "account" ? source.Key : data.GetByStableKey(source.Key)!.DBName
                );
            if (state.Scope == "account")
                _accountSources.Add(state.Key, sources);
            else
                _questSources.Add(data.GetByStableKey(state.Key)!.DBName, sources);
        }

        (string Scope, string Key) AddState(string scope, string key)
        {
            var state = (scope, key);
            if (!reverse.ContainsKey(state))
                reverse.Add(state, new HashSet<(string Scope, string Key)>());
            return state;
        }
    }

    public bool IsBoundQuest(string dbName) => _questSources.ContainsKey(dbName);

    public bool IsQuestCompleted(string dbName, IGateFacts facts) =>
        _questSources.TryGetValue(dbName, out var sources)
            ? Any(sources, facts)
            : facts.IsQuestCompleted(dbName);

    public bool ReadAccountState(string key, IGateFacts facts)
    {
        if (key != EncounterStateKeys.ReliquaryClaimed)
            throw new ArgumentException($"Unknown account state {key}", nameof(key));
        return _accountSources.TryGetValue(key, out var sources)
            ? Any(sources, facts)
            : facts.ReadAccountState(key);
    }

    private static bool Any(Source[] sources, IGateFacts facts)
    {
        for (int i = 0; i < sources.Length; i++)
            if (
                sources[i].IsAccount
                    ? facts.ReadAccountState(sources[i].Key)
                    : facts.IsQuestCompleted(sources[i].Key)
            )
                return true;
        return false;
    }

    private readonly struct Source
    {
        public readonly bool IsAccount;
        public readonly string Key;

        public Source(bool isAccount, string key)
        {
            IsAccount = isAccount;
            Key = key;
        }
    }
}
