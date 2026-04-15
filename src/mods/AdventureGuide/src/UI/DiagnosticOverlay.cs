using AdventureGuide.Config;
using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Markers;
using AdventureGuide.State;
using ImGuiNET;
using UnityEngine;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.UI;

/// <summary>
/// Toggleable diagnostic overlay for in-game debugging.
/// Shows status bar with active quest count, marker count, NAV targets, and frame cost.
/// When Left Alt is held, shows marker tooltips with source key and contributing quests.
/// </summary>
internal sealed class DiagnosticOverlay
{
	private readonly QuestStateTracker _questTracker;
	private readonly MarkerComputer _markerComputer;
	private readonly NavigationSet _navSet;
	private readonly GuideConfig _config;
	private readonly CompiledGuideModel _guide;

	/// <summary>Screen-space distance threshold (pixels) for marker hover detection.</summary>
	private const float HoverRadiusPx = 30f;

	internal DiagnosticOverlay(
		QuestStateTracker questTracker,
		MarkerComputer markerComputer,
		NavigationSet navSet,
		GuideConfig config,
		CompiledGuideModel guide)
	{
		_questTracker = questTracker;
		_markerComputer = markerComputer;
		_navSet = navSet;
		_config = config;
		_guide = guide;
	}

	internal void Render()
	{
		if (!_config.DiagnosticOverlay.Value)
			return;

		DrawStatusBar();

		if (Input.GetKey(KeyCode.LeftAlt))
			DrawMarkerTooltip();
	}

	private void DrawStatusBar()
	{
		var display = ImGui.GetIO().DisplaySize;
		float barHeight = 24f * _config.ResolvedUiScale;

		ImGui.SetNextWindowPos(
			new System.Numerics.Vector2(0, display.Y - barHeight),
			ImGuiCond.Always);
		ImGui.SetNextWindowSize(
			new System.Numerics.Vector2(display.X, barHeight),
			ImGuiCond.Always);

		var flags = ImGuiWindowFlags.NoDecoration
			| ImGuiWindowFlags.NoInputs
			| ImGuiWindowFlags.NoNav
			| ImGuiWindowFlags.NoBringToFrontOnFocus
			| ImGuiWindowFlags.NoFocusOnAppearing
			| ImGuiWindowFlags.NoSavedSettings;

		ImGui.PushStyleColor(ImGuiCol.WindowBg, Theme.Background);

		if (ImGui.Begin("###DiagnosticOverlay", flags))
		{
			int activeCount = _questTracker.ActiveQuests.Count;
			int markerCount = _markerComputer.Markers.Count;
			int navCount = _navSet.Count;
			double totalMs = GuideProfiler.TotalLastMs;

			ImGui.TextUnformatted(
				$"AG: {activeCount} active, {markerCount} markers, {navCount} NAV, {totalMs:F1}ms");
		}

		ImGui.End();
		ImGui.PopStyleColor();
	}

	private void DrawMarkerTooltip()
	{
		var cam = Camera.main;
		if (cam == null)
			return;

		var mousePos = ImGui.GetIO().MousePos;
		var markers = _markerComputer.Markers;
		float bestDistSq = HoverRadiusPx * HoverRadiusPx;
		MarkerEntry? closest = null;

		for (int i = 0; i < markers.Count; i++)
		{
			var entry = markers[i];
			var worldPos = new Vector3(entry.X, entry.Y, entry.Z);
			var screenPos = cam.WorldToScreenPoint(worldPos);

			// Behind camera
			if (screenPos.z <= 0)
				continue;

			// Unity screen coords are bottom-left origin; ImGui is top-left
			float sx = screenPos.x;
			float sy = Screen.height - screenPos.y;

			float dx = mousePos.X - sx;
			float dy = mousePos.Y - sy;
			float distSq = dx * dx + dy * dy;

			if (distSq < bestDistSq)
			{
				bestDistSq = distSq;
				closest = entry;
			}
		}

		if (closest == null)
			return;

		ImGui.BeginTooltip();

		ImGui.TextUnformatted($"Node: {closest.NodeKey}");
		ImGui.TextUnformatted($"Type: {closest.Type}");
		ImGui.TextUnformatted($"Quest: {closest.QuestKey}");

		if (closest.SourceNodeKey != null)
			ImGui.TextUnformatted($"Source: {closest.SourceNodeKey}");

		var contributingKeys = _markerComputer.GetContributingQuestKeys(closest.NodeKey);
		if (contributingKeys != null && contributingKeys.Count > 0)
		{
			ImGui.Separator();
			ImGui.TextUnformatted("Contributing quests:");
			foreach (var questKey in contributingKeys)
			{
				var node = _guide.GetNode(questKey);
				string label = node?.DisplayName ?? questKey;
				ImGui.TextUnformatted($"  {label}");
			}
		}

		ImGui.EndTooltip();
	}
}
