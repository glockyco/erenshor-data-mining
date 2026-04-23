using AdventureGuide.Config;
using AdventureGuide.Diagnostics;
using UnityEngine;

namespace AdventureGuide.Markers;

/// <summary>
/// Renders world-space billboard markers from <see cref="MarkerProjector"/>
/// output using <see cref="MarkerPool"/>.
/// </summary>
internal sealed class MarkerRenderer
{
	private readonly MarkerProjector _projector;
	private readonly MarkerPool _pool;
	private readonly GuideConfig _config;
	private readonly DiagnosticsCore? _diagnostics;

	private bool _enabled;
	private bool _configDirty;
	private string _currentScene = "";
	private MarkerCandidateList? _lastConfiguredCandidates;

	public bool Enabled
	{
		get => _enabled;
		set
		{
			if (_enabled == value)
				return;
			_enabled = value;
			if (!value)
				_pool.DeactivateAll();
		}
	}

	public MarkerRenderer(
		MarkerProjector projector,
		MarkerPool pool,
		GuideConfig config,
		DiagnosticsCore? diagnostics = null)
	{
		_projector = projector;
		_pool = pool;
		_config = config;
		_diagnostics = diagnostics;

		config.MarkerScale.SettingChanged += OnConfigChanged;
		config.IconSize.SettingChanged += OnConfigChanged;
		config.SubTextSize.SettingChanged += OnConfigChanged;
		config.IconYOffset.SettingChanged += OnConfigChanged;
		config.SubTextYOffset.SettingChanged += OnConfigChanged;
	}

	/// <summary>Per-frame render. Reconfigures the pool when the projector's
	/// candidate-list reference changes; otherwise updates rendered instances from
	/// per-frame projector state.</summary>
	public void Render()
	{
		using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.MarkerRendererRender);

		if (!_enabled || GameData.PlayerControl == null || !MarkerFonts.IsReady)
			return;

		var entries = _projector.Markers;
		var candidates = _projector.LastCandidates;
		if (!ReferenceEquals(candidates, _lastConfiguredCandidates) || _configDirty)
		{
			ConfigureMarkers(entries);
			_lastConfiguredCandidates = candidates;
			_configDirty = false;
		}

		UpdateLiveState(entries);
	}

	public void OnSceneChanged(string scene)
	{
		_currentScene = scene;
		_pool.DeactivateAll();
		_lastConfiguredCandidates = null;
	}

	public void Destroy()
	{
		_config.MarkerScale.SettingChanged -= OnConfigChanged;
		_config.IconSize.SettingChanged -= OnConfigChanged;
		_config.SubTextSize.SettingChanged -= OnConfigChanged;
		_config.IconYOffset.SettingChanged -= OnConfigChanged;
		_config.SubTextYOffset.SettingChanged -= OnConfigChanged;
		_pool.Destroy();
	}

	private void OnConfigChanged(object sender, System.EventArgs e) => _configDirty = true;

	private void ConfigureMarkers(IReadOnlyList<MarkerEntry> markers)
	{
		_pool.SetActiveCount(markers.Count);
		for (int i = 0; i < markers.Count; i++)
		{
			var entry = markers[i];
			var instance = _pool.Get(i);
			instance.Configure(
				entry.Type,
				entry.SubText,
				_config.MarkerScale.Value,
				_config.IconSize.Value,
				_config.SubTextSize.Value,
				_config.IconYOffset.Value,
				_config.SubTextYOffset.Value
			);
			instance.SetActive(true);
		}
	}

	private void UpdateLiveState(IReadOnlyList<MarkerEntry> markers)
	{
		var playerPos = GameData.PlayerControl!.transform.position;

		for (int i = 0; i < markers.Count; i++)
		{
			var entry = markers[i];
			var instance = _pool.Get(i);

			if (!string.Equals(entry.Scene, _currentScene, System.StringComparison.OrdinalIgnoreCase))
			{
				instance.SetActive(false);
				continue;
			}

			ReconfigureInstance(entry, instance);

			var pos = new Vector3(entry.X, entry.Y, entry.Z);
			instance.SetPosition(pos);

			float dist = Vector3.Distance(playerPos, pos);
			instance.SetAlpha(dist);
			instance.SetActive(true);
		}
	}

	private void ReconfigureInstance(MarkerEntry entry, MarkerInstance instance)
	{
		instance.Configure(
			entry.Type,
			entry.SubText,
			_config.MarkerScale.Value,
			_config.IconSize.Value,
			_config.SubTextSize.Value,
			_config.IconYOffset.Value,
			_config.SubTextYOffset.Value
		);
	}
}
