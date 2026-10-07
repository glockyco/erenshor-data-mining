namespace AdventureGuide.UI;

internal sealed class ZoneLineAlternativeLabels
{
    private readonly int _stepOrder;
    private readonly List<RowLabels> _rows = new();
    private int _count = -1;
    private string _header = "";

    public ZoneLineAlternativeLabels(int stepOrder) => _stepOrder = stepOrder;

    public string Header(int count)
    {
        if (count != _count)
        {
            _count = count;
            _header = $"{count} zone connections###zl_{_stepOrder}";
        }
        return _header;
    }

    public RowLabels Row(int index, string destination, float distance)
    {
        while (_rows.Count <= index)
            _rows.Add(new RowLabels(_stepOrder, _rows.Count));
        var row = _rows[index];
        row.Update(destination, distance);
        return row;
    }

    internal sealed class RowLabels
    {
        private readonly int _stepOrder;
        private readonly int _index;
        private readonly Dictionary<(string Name, string Key), string> _requirements = new();
        private string? _destination;
        private double _distance;
        public string Text { get; private set; } = "";
        public string Selectable { get; private set; } = "";
        public string Tooltip { get; private set; } = "";

        public RowLabels(int stepOrder, int index)
        {
            _stepOrder = stepOrder;
            _index = index;
        }

        public void Update(string destination, float distance)
        {
            double rounded = Math.Round(distance);
            if (_destination == destination && _distance == rounded)
                return;
            if (_destination != destination)
                Tooltip = $"Route via {destination}";
            _destination = destination;
            _distance = rounded;
            Selectable = ZoneLineLabels.Selectable(destination, (float)rounded, _stepOrder, _index);
            Text = Selectable.Substring(0, Selectable.LastIndexOf("###", StringComparison.Ordinal));
        }

        public string Requirement(string name, string key)
        {
            if (!_requirements.TryGetValue((name, key), out var label))
            {
                label = $"Requires: \"{name}\"##rq_{_stepOrder}_{_index}_{key}";
                _requirements.Add((name, key), label);
            }
            return label;
        }
    }
}
