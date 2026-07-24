"""MediaWiki API reader for production template inventory."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from erenshor.infrastructure.wiki.rate_limit import MediaWikiRequestor

JsonObject = dict[str, Any]
Transport = Callable[[dict[str, str]], JsonObject]


class WikiInventoryError(RuntimeError):
    """Raised when production wiki inventory cannot be read."""


@dataclass(frozen=True)
class EmbeddedInSummary:
    """Summary of pages that transclude a template."""

    title: str
    total: int
    continued: bool
    examples: list[str]


class MediaWikiInventoryClient:
    """Read template inventory data from a MediaWiki API endpoint."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        requestor: MediaWikiRequestor | None = None,
    ) -> None:
        if (transport is None) == (requestor is None):
            raise ValueError("exactly one inventory transport is required")
        self._transport = transport
        self._requestor = requestor

    def list_templates(self) -> list[str]:
        pages = self._paginate(
            {
                "action": "query",
                "list": "allpages",
                "apnamespace": "10",
                "aplimit": "max",
            },
            list_name="allpages",
        )
        return [str(page["title"]) for page in pages]

    def embeddedin_summary(self, title: str) -> EmbeddedInSummary:
        pages: list[JsonObject] = []
        continued = False
        continuation: dict[str, str] = {}

        while True:
            payload = self._request(
                {
                    "action": "query",
                    "list": "embeddedin",
                    "eititle": title,
                    "einamespace": "0|10",
                    "eilimit": "max",
                    **continuation,
                }
            )
            pages.extend(cast("list[JsonObject]", payload.get("query", {}).get("embeddedin", [])))
            next_continue = self._continuation(payload)
            if next_continue is None:
                break
            continued = True
            continuation = next_continue

        return EmbeddedInSummary(
            title=title,
            total=len(pages),
            continued=continued,
            examples=[str(page["title"]) for page in pages[:10]],
        )

    def raw_page(self, title: str) -> str | None:
        payload = self._request(
            {
                "action": "query",
                "prop": "revisions",
                "titles": title,
                "rvprop": "content",
                "rvslots": "main",
            }
        )
        pages = cast("list[JsonObject]", payload.get("query", {}).get("pages", []))
        if not pages:
            return None
        page = pages[0]
        if page.get("missing") is True:
            return None
        revisions = cast("list[JsonObject]", page.get("revisions", []))
        if not revisions:
            return None
        slots = cast("dict[str, JsonObject]", revisions[0].get("slots", {}))
        main = slots.get("main", {})
        return cast("str | None", main.get("content"))

    def _paginate(self, params: dict[str, str], *, list_name: str) -> list[JsonObject]:
        rows: list[JsonObject] = []
        continuation: dict[str, str] = {}
        while True:
            payload = self._request({**params, **continuation})
            rows.extend(cast("list[JsonObject]", payload.get("query", {}).get(list_name, [])))
            next_continue = self._continuation(payload)
            if next_continue is None:
                return rows
            continuation = next_continue

    def _request(self, params: dict[str, str]) -> JsonObject:
        if self._transport is not None:
            return self._transport({"format": "json", "formatversion": "2", **params})
        if self._requestor is None:
            raise WikiInventoryError("MediaWiki inventory client has no request transport")
        return self._requestor.get(params)

    @staticmethod
    def _continuation(payload: JsonObject) -> dict[str, str] | None:
        continuation = payload.get("continue")
        if not isinstance(continuation, dict):
            return None
        return {str(key): str(value) for key, value in continuation.items() if key != "continue"}


class FixtureDirectoryTransport:
    """Transport that replays recorded MediaWiki API fixture files."""

    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = fixture_dir

    def __call__(self, params: dict[str, str]) -> JsonObject:
        path = self._fixture_path(params)
        return cast("JsonObject", json.loads(path.read_text(encoding="utf-8")))

    def _fixture_path(self, params: dict[str, str]) -> Path:
        if params.get("list") == "allpages":
            suffix = "page2" if "apcontinue" in params else "page1"
            return self.fixture_dir / f"allpages-{suffix}.json"
        if params.get("list") == "embeddedin":
            title = params["eititle"]
            slug = _template_slug(title)
            suffix = "page2" if "eicontinue" in params else "page1"
            return self.fixture_dir / f"embeddedin-{slug}-{suffix}.json"
        raise WikiInventoryError(f"No fixture mapping for request: {params}")


def _template_slug(title: str) -> str:
    stem = title.removeprefix("Template:").lower()
    chars = [char if char.isalnum() else "-" for char in stem]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug
