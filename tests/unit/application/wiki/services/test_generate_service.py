"""Focused tests for generated-page audit preflight selection."""

from __future__ import annotations

from collections.abc import Mapping
from io import StringIO
from typing import cast
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from erenshor.application.wiki.generators.base import GeneratedPage, PageMetadata
from erenshor.application.wiki.services.generate_service import WikiGenerateService


def _service() -> tuple[WikiGenerateService, MagicMock, MagicMock]:
    service = WikiGenerateService.__new__(WikiGenerateService)
    storage = MagicMock()
    storage.read_fetched_by_title.return_value = None
    normalizer = MagicMock()
    normalizer.normalize.side_effect = lambda content: f"normalized:{content}"
    service._storage = storage
    service._page_normalizer = normalizer
    service._console = Console(file=StringIO())
    return service, storage, normalizer


def _page(title: str, content: str) -> GeneratedPage:
    return GeneratedPage(
        title=title,
        content=content,
        metadata=PageMetadata(summary="test"),
        stable_keys=[f"key:{title}"],
    )


def test_generation_preflight_gets_exact_immutable_processed_pages() -> None:
    service, storage, _ = _service()
    seen: list[Mapping[str, str]] = []

    result = service._process_generated_pages(
        [_page("Z page", "z"), _page("A page", "a")],
        dry_run=True,
        preflight=seen.append,
    )

    assert result.succeeded == 2
    assert list(seen[0].items()) == [
        ("A page", "normalized:a"),
        ("Z page", "normalized:z"),
    ]
    with pytest.raises(TypeError):
        cast("dict[str, str]", seen[0])["Other"] = "not allowed"
    storage.save_generated_by_title.assert_not_called()


def test_generation_preflight_runs_only_after_all_pages_process() -> None:
    service, _, normalizer = _service()
    events: list[str] = []
    normalizer.normalize.side_effect = lambda content: events.append(content) or content

    service._process_generated_pages(
        [_page("A", "first"), _page("B", "second")],
        dry_run=True,
        preflight=lambda _: events.append("preflight"),
    )

    assert events == ["first", "second", "preflight"]


def test_regenerated_stance_page_takes_new_data_and_keeps_the_editor_image() -> None:
    fetched = (
        "{{Stance\n|title=Aggressive\n|image=[[File:Editor Aggressive.png|thumb]]\n|damage_mod=1.2\n}}\n\n"
        "Editor notes.\n"
    )
    generated = (
        "{{Stance\n|title=Aggressive\n|image=[[File:Aggressive.png|thumb]]\n|imagecaption=\n|damage_mod=1.4\n}}\n"
    )
    context = MagicMock()
    context.storage.read_fetched_by_title.return_value = fetched
    service = WikiGenerateService(context=context, link_catalog=(), console=Console(file=StringIO()))
    seen: list[Mapping[str, str]] = []

    service._process_generated_pages([_page("Aggressive", generated)], dry_run=True, preflight=seen.append)

    page = seen[0]["Aggressive"]
    assert "|damage_mod=1.4\n" in page
    assert "|image=[[File:Editor Aggressive.png|thumb]]\n" in page
    assert "Editor notes." in page


def test_regenerated_zone_page_keeps_the_live_article_and_fills_blank_fields() -> None:
    fetched = (
        "[[Category:Soluna's Landing]]\n"
        "{{Zone\n|title=Soluna's Landing\n|image=[[File:Solunas Landing.png|thumb]]\n|imagecaption=\n|type=Zone\n"
        "|level=25-33\n|maplink=\n|connects=[[Loomingwood Forest]]\n}}\n"
        "Soluna's Landing lies in the north of [[Erenshor]].\n\n"
        '{| class="wikitable"\n|+Soluna\'s Landing\n!NPCs\n|-\n|[[Illian Asboth]]\n|}\n\n'
        "{{Zone Navbox}}\n"
    )
    generated = (
        "{{Zone\n|title=Soluna's Landing\n|image=\n|imagecaption=\n|type=Zone\n|level=\n"
        "|maplink={{MapLink|zone=Soluna}}\n|connects=[[Loomingwood Forest]], [[Malaroth's Nesting Grounds]]\n}}\n\n"
        "{{Zone Navbox}}\n"
    )
    context = MagicMock()
    context.storage.read_fetched_by_title.return_value = fetched
    service = WikiGenerateService(context=context, link_catalog=(), console=Console(file=StringIO()))
    seen: list[Mapping[str, str]] = []

    service._process_generated_pages([_page("Soluna's Landing", generated)], dry_run=True, preflight=seen.append)

    page = seen[0]["Soluna's Landing"]
    assert "|maplink={{MapLink|zone=Soluna}}\n" in page
    assert "|connects=[[Loomingwood Forest]]\n" in page
    assert "|level=25-33\n" in page
    assert "|image=[[File:Solunas Landing.png|thumb]]\n" in page
    assert "Soluna's Landing lies in the north of [[Erenshor]].\n" in page
    assert "|[[Illian Asboth]]\n" in page
    assert page.count("{{Zone Navbox}}") == 1
    assert "[[Category:Soluna's Landing]]" in page
