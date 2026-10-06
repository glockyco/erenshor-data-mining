from __future__ import annotations

import pytest

from erenshor.application.processor.model_images import PageCharacter, model_image_names


def _character(stable_key: str, page: str, name: str, model: str) -> PageCharacter:
    return PageCharacter(stable_key=stable_key, wiki_page_name=page, display_name=name, model_key=model)


def test_a_kind_with_another_model_than_the_base_kind_gets_its_own_image() -> None:
    # The Expert Training Set's dummy has its own mesh and material.
    images = model_image_names(
        [
            _character("wood", "Training Dummy", "Training Dummy", "plain"),
            _character("azure", "Training Dummy", "Training Dummy", "plain"),
            _character("stone", "Training Dummy", "Training Dummy (400 AC)", "plain"),
            _character("expert a", "Training Dummy", "Training Dummy (1000 AC)", "expert"),
            _character("expert b", "Training Dummy", "Training Dummy (1000 AC)", "expert"),
        ]
    )

    assert images == {"expert a": "Training Dummy (1000 AC)", "expert b": "Training Dummy (1000 AC)"}


def test_without_a_base_kind_the_model_of_most_kinds_keeps_the_page_image() -> None:
    # The eighth Vithean chest is golden, the seven others blue.
    rounds = [_character(f"round {n}", "Vithean Chest", f"Vithean Chest (Round {n})", "blue") for n in range(1, 8)]

    images = model_image_names([*rounds, _character("round 8", "Vithean Chest", "Vithean Chest (Round 8)", "gold")])

    assert images == {"round 8": "Vithean Chest (Round 8)"}


def test_kinds_that_share_a_model_and_single_kind_pages_keep_their_image() -> None:
    images = model_image_names(
        [
            _character("bank a", "Summoned: Pocket Bank", "Summoned: Pocket Bank", "rift"),
            _character("bank b", "Summoned: Pocket Bank", "Summoned: Pocket Bank", "rift"),
            # One kind may show several models: the page has one image for it.
            _character("raider a", "A Highwayman Raider", "A Highwayman Raider", "red"),
            _character("raider b", "A Highwayman Raider", "A Highwayman Raider", "green"),
        ]
    )

    assert images == {}


def test_a_kind_of_several_models_on_a_page_of_several_models_stops_the_build() -> None:
    with pytest.raises(ValueError, match="shows 2 models"):
        model_image_names(
            [
                _character("a", "Golem", "Golem", "stone"),
                _character("b", "Golem", "Golem (Iron)", "iron"),
                _character("c", "Golem", "Golem (Iron)", "steel"),
            ]
        )


def test_a_tie_without_a_base_kind_stops_the_build() -> None:
    with pytest.raises(ValueError, match="as many kinds show one model as another"):
        model_image_names(
            [
                _character("a", "Chest", "Chest (Red)", "red"),
                _character("b", "Chest", "Chest (Blue)", "blue"),
            ]
        )
