"""Unit tests for targeted image uploads."""

from unittest.mock import MagicMock

import pytest

from erenshor.cli.commands.images import _deployment_list_for_stable_keys


def test_deployment_list_selects_only_requested_stable_keys() -> None:
    registry = MagicMock()
    fit = MagicMock(image_name="Fit of Brilliance")
    other = MagicMock(image_name="Other Spell")
    registry.get_image_metadata.side_effect = {
        "spell:none - fit of resonance": fit,
        "spell:other": other,
    }.get

    selected = _deployment_list_for_stable_keys(registry, ["spell:none - fit of resonance"])

    assert selected == {"Fit of Brilliance": fit}
    registry.get_image_metadata.assert_called_once_with("spell:none - fit of resonance")


def test_deployment_list_rejects_unknown_stable_keys() -> None:
    registry = MagicMock()
    registry.get_image_metadata.return_value = None

    with pytest.raises(ValueError, match=r"Unknown image stable key.*spell:missing"):
        _deployment_list_for_stable_keys(registry, ["spell:missing"])
