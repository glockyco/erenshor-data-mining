"""Critical plots describe supported profiles without claiming a closed class roster."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from erenshor.tools.critical_strike_model import CriticalProfile, critical_hit_chance


def test_critical_plot_labels_and_curves_use_explicit_mechanics_profiles() -> None:
    spec = importlib.util.spec_from_file_location(
        "render_spell_scaling_plots", Path("src/tools/render_spell_scaling_plots.py")
    )
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = script
    spec.loader.exec_module(script)

    styles = script.CRITICAL_CLASS_STYLES
    assert [(style.label, style.profile) for style in styles] == [
        ("Ordinary", CriticalProfile.ORDINARY),
        ("Stormcaller", CriticalProfile.STORMCALLER),
        ("Windblade", CriticalProfile.WINDBLADE),
    ]
    curves = script.physical_critical_class_series(35, 12)
    for style, curve in zip(styles, curves, strict=True):
        assert curve.values[100] == 100.0 * critical_hit_chance(35, 100, 12, style.profile)
        assert curve.color == style.color
        assert curve.dash_pattern == style.dash_pattern
