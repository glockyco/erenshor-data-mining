from __future__ import annotations

import pytest

from erenshor.domain.value_objects.wiki_filename import picture_file_title, picture_subject


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("Aura: Ancient Presence",), "Aura Ancient Presence"),
        (("Blueprint: Stone | Bank",), "Blueprint Stone Bank"),
        (("  Multiple  :  Spaces  ",), "Multiple Spaces"),
        ((None, "", "Copper Sword"), "Copper Sword"),
        ((":|#<>[]{}", "Fallback"), "Fallback"),
        ((None, ""), ""),
    ],
)
def test_a_subject_is_the_first_name_that_survives_the_forbidden_characters(
    names: tuple[str | None, ...], expected: str
) -> None:
    assert picture_subject(*names) == expected


def test_a_title_names_the_subject_and_the_role() -> None:
    assert picture_file_title("icon", "Stance: Aggressive") == "Stance Aggressive icon.png"
    assert picture_file_title("render", "Summoned: Brute") == "Summoned Brute render.png"
    assert picture_file_title("screenshot", "Training Dummy (1000 AC)") == "Training Dummy (1000 AC) screenshot.png"


def test_an_entity_without_a_name_has_no_title() -> None:
    assert picture_file_title("render", None, "") == ""
