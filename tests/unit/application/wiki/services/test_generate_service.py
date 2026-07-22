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
from erenshor.application.wiki.services.wiki_service import WikiService


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


def test_wiki_service_forwards_generation_preflight_callback() -> None:
    service = WikiService.__new__(WikiService)
    service._generate_service = MagicMock()
    callback = MagicMock()
    expected = object()
    service._generate_service.generate_all.return_value = expected

    result = service.generate_all(preflight=callback)

    assert result is expected
    service._generate_service.generate_all.assert_called_once_with(
        dry_run=False,
        limit=None,
        page_titles=None,
        generator_names=None,
        preflight=callback,
    )
