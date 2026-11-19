import importlib

import pytest


@pytest.fixture
def parity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend("wiki-dev")
    return importlib.import_module("tooltip_parity")


def test_missing_wiki_key_is_named(parity) -> None:
    root = parity._build_dom('<div class="erenshor-ability-tooltip" data-erenshor-key="spell:spark"></div>')
    with pytest.raises(ValueError, match=r"Missing keys:.*spell:lightning"):
        parity.eligible_wiki_roots(root, ["spell:spark", "spell:lightning"], "")


def test_duplicate_standard_card_fails_even_with_other_qualities(parity) -> None:
    root = parity._build_dom(
        "".join(f'<div data-erenshor-quality="{label}"></div>' for label in ("Standard", "Standard", "Blessed"))
    )
    with pytest.raises(ValueError, match="Duplicate rendered quality card: Standard"):
        parity.quality_cards(root, (1, 2))


def test_wrong_quality_card_is_not_paired_by_order(parity) -> None:
    root = parity._build_dom('<div data-erenshor-quality="Standard"></div><div data-erenshor-quality="Ascended"></div>')
    with pytest.raises(ValueError, match=r"Expected quality cards.*Blessed.*Ascended"):
        parity.quality_cards(root, (1, 2))
