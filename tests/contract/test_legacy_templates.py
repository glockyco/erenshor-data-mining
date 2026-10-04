from pathlib import Path

import pytest


@pytest.mark.parametrize("template", ("Item", "Character", "Ability", "Stance", "Quest", "Zone", "MapLink"))
def test_legacy_entity_templates_have_no_data_branch(template: str) -> None:
    source = (Path("wiki/templates") / f"{template}.wiki").read_text(encoding="utf-8").lower()

    assert "#invoke" not in source
    assert "{{{lua" not in source
    assert "#cargo_" not in source
