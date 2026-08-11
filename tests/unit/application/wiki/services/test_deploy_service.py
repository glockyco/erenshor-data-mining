"""Focused tests for generated-page deploy preflight selection."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from erenshor.application.wiki.services.deploy_service import WikiDeployService
from erenshor.application.wiki.services.storage import PageMetadata


def _metadata(title: str, *, deployable: bool = True) -> PageMetadata:
    return PageMetadata(
        page_title=title,
        stable_keys=[],
        entity_names=[],
        generated_at="2025-01-02T00:00:00",
        generated_hash=f"generated-{title}",
        deployed_hash=None if deployable else f"generated-{title}",
    )


def _service(
    metadata: dict[str, PageMetadata],
    content: dict[str, str | None],
) -> tuple[WikiDeployService, MagicMock, MagicMock]:
    wiki_client = MagicMock()
    storage = MagicMock()
    storage._load_metadata.return_value = metadata
    storage.read_generated_by_title.side_effect = content.__getitem__
    return WikiDeployService(wiki_client, storage), wiki_client, storage


def test_preflight_gets_filtered_limited_content_and_total_considered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filtering, metadata/content skips, and limit happen before the hook."""
    service, wiki_client, storage = _service(
        {
            "A Skipped": _metadata("A Skipped", deployable=False),
            "B First": _metadata("B First"),
            "C Second": _metadata("C Second"),
            "D Untouched": _metadata("D Untouched"),
            "Z NotRequested": _metadata("Z NotRequested"),
        },
        {
            "A Skipped": "ignored",
            "B First": "first bytes",
            "C Second": "second bytes",
            "D Untouched": "untouched",
            "Z NotRequested": "not requested",
        },
    )
    monkeypatch.setattr("erenshor.application.wiki.services.deploy_service.time.sleep", lambda _: None)
    seen: list[Mapping[str, str]] = []

    result = service.deploy_all(
        page_titles=["D Untouched", "A Skipped", "B First", "C Second"],
        limit=2,
        preflight=seen.append,
    )

    assert len(seen) == 1
    assert list(seen[0].items()) == [("B First", "first bytes"), ("C Second", "second bytes")]
    with pytest.raises(TypeError):
        seen[0]["New"] = "not allowed"  # type: ignore[index]
    assert result.total == 3  # skipped row + two selected rows; limit leaves one untouched
    assert result.skipped == 1
    assert [call.kwargs["title"] for call in wiki_client.edit_page.call_args_list] == ["B First", "C Second"]
    assert storage.read_generated_by_title.call_count == 2


def test_preflight_runs_before_login_and_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    """The callback is invoked before authentication and upload operations."""
    service, wiki_client, _ = _service({"Page": _metadata("Page")}, {"Page": "bytes"})
    monkeypatch.setattr("erenshor.application.wiki.services.deploy_service.time.sleep", lambda _: None)
    events: list[str] = []
    wiki_client.login.side_effect = lambda: events.append("login")
    wiki_client.edit_page.side_effect = lambda **_: events.append("edit")

    service.deploy_all(preflight=lambda _: events.append("preflight"))

    assert events == ["preflight", "login", "edit"]


def test_preflight_runs_in_dry_run_without_login_or_edit() -> None:
    """Dry-run still audits the selected bytes and performs no wiki calls."""
    service, wiki_client, _ = _service({"Page": _metadata("Page")}, {"Page": "bytes"})
    seen: list[Mapping[str, str]] = []

    result = service.deploy_all(dry_run=True, preflight=seen.append)

    assert result.succeeded == 1
    assert dict(seen[0]) == {"Page": "bytes"}
    wiki_client.login.assert_not_called()
    wiki_client.edit_page.assert_not_called()


def test_preflight_exception_prevents_login_and_edit() -> None:
    """A failed audit propagates without authenticating or mutating deployment state."""
    service, wiki_client, storage = _service({"Page": _metadata("Page")}, {"Page": "bytes"})

    def fail(_: Mapping[str, str]) -> None:
        raise RuntimeError("audit failed")

    with pytest.raises(RuntimeError, match="audit failed"):
        service.deploy_all(preflight=fail)

    wiki_client.login.assert_not_called()
    wiki_client.edit_page.assert_not_called()
    storage.update_deployed.assert_not_called()


def test_upload_uses_snapshot_when_storage_changes_after_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing storage after the callback cannot change the upload payload."""
    service, wiki_client, storage = _service({"Page": _metadata("Page")}, {"Page": "original bytes"})
    monkeypatch.setattr("erenshor.application.wiki.services.deploy_service.time.sleep", lambda _: None)

    def mutate_storage(_: Mapping[str, str]) -> None:
        storage.read_generated_by_title.return_value = "changed bytes"

    service.deploy_all(preflight=mutate_storage)

    assert wiki_client.edit_page.call_args.kwargs["content"] == "original bytes"
    storage.update_deployed.assert_called_once_with("Page", "original bytes")


def test_deploy_from_dir_does_not_run_generated_preflight(tmp_path: Path) -> None:
    """Legacy directory deployment remains independent of generated-page hooks."""
    page = tmp_path / "Page.txt"
    page.write_text("legacy bytes", encoding="utf-8")
    service, wiki_client, _ = _service({}, {})

    service.deploy_from_dir(tmp_path, dry_run=True)

    wiki_client.login.assert_not_called()
    wiki_client.edit_page.assert_not_called()


def test_deploy_from_dir_filters_titles_before_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Only requested directory pages count toward the deployment limit."""
    (tmp_path / "A_Page.txt").write_text("a", encoding="utf-8")
    (tmp_path / "B_Page.txt").write_text("b", encoding="utf-8")
    (tmp_path / "C_Page.txt").write_text("c", encoding="utf-8")
    service, wiki_client, _ = _service({}, {})
    monkeypatch.setattr("erenshor.application.wiki.services.deploy_service.time.sleep", lambda _: None)

    result = service.deploy_from_dir(
        tmp_path,
        page_titles=["B Page", "C Page"],
        limit=1,
    )

    assert result.total == 1
    assert result.succeeded == 1
    wiki_client.edit_page.assert_called_once_with(
        title="B Page",
        content="b",
        summary="Manual wiki update",
    )
