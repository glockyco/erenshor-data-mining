"""Closed selections and immutable, content-addressed publication records."""

from __future__ import annotations

import hashlib
import json
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PublishError(ValueError):
    """The reviewed publication cannot safely continue."""


class SurfaceUncertainError(RuntimeError):
    """A provider may have accepted a mutation without a conclusive receipt."""

    def __init__(self, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def exact_names(value: list[str]) -> list[str]:
    if any(not name or name != name.strip() or "\n" in name for name in value):
        raise ValueError("Selections require nonempty exact names without surrounding whitespace")
    normalized = [name.replace("_", " ") for name in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate selected names are not allowed")
    return sorted(value, key=lambda name: (name.casefold(), name))


class WikiSelection(ClosedModel):
    article_titles: list[str] = Field(default_factory=list)
    repo_titles: list[str] = Field(default_factory=list)
    data_titles: list[str] = Field(default_factory=list)
    include_templates: bool = False
    include_content_pages: bool = False
    render_check: bool = True
    accept_drift: list[str] = Field(default_factory=list)
    page_edits_file: str | None = None
    prose_review_sha256: str | None = None

    _names = field_validator("article_titles", "repo_titles", "data_titles", "accept_drift")(exact_names)

    @model_validator(mode="after")
    def bounded(self) -> WikiSelection:
        groups = [self.article_titles, self.repo_titles, self.data_titles]
        all_titles = [title.replace("_", " ") for group in groups for title in group]
        if len(all_titles) != len(set(all_titles)):
            raise ValueError("A wiki title cannot have multiple publication owners")
        if any(not title.startswith("Module:Erenshor/Data/") for title in self.data_titles):
            raise ValueError("data_titles must name exact bot-owned data modules")
        if any(title.startswith("Module:Erenshor/Data/") for title in self.repo_titles):
            raise ValueError("Bot-owned data modules belong in data_titles")
        if any(title.startswith("Template:") for title in self.repo_titles) and not self.include_templates:
            raise ValueError("Selected templates require include_templates = true")
        if (
            any(not title.startswith(("Module:", "Template:", "Category:")) for title in self.repo_titles)
            and not self.include_content_pages
        ):
            raise ValueError("Selected content pages require include_content_pages = true")
        if set(self.accept_drift) - set(self.repo_titles + self.data_titles):
            raise ValueError("accept_drift must be bounded by selected repository/data titles")
        if bool(self.page_edits_file) != bool(self.prose_review_sha256):
            raise ValueError("Prose edits require a separate prose_review_sha256 declaration")
        if self.prose_review_sha256 is not None:
            digest = self.prose_review_sha256.removeprefix("sha256:")
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("prose_review_sha256 must be a SHA-256 digest")
            self.prose_review_sha256 = digest
        return self


class MapsSelection(ClosedModel):
    targets: list[Literal["canonical", "legacy"]] = Field(default_factory=list)

    @field_validator("targets")
    @classmethod
    def targets_unique(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Duplicate map targets are not allowed")
        return sorted(values, key=lambda value: (value != "canonical", value))


class SheetsSelection(ClosedModel):
    tabs: list[str] = Field(default_factory=list)
    _names = field_validator("tabs")(exact_names)


class PublishSelection(ClosedModel):
    schema_version: Literal[1]
    summary: str
    wiki: WikiSelection | None = None
    maps: MapsSelection | None = None
    sheets: SheetsSelection | None = None

    @model_validator(mode="after")
    def nonempty(self) -> PublishSelection:
        if not self.summary.strip():
            raise ValueError("A publication summary is required")
        wiki = self.wiki
        if wiki and not (wiki.article_titles or wiki.repo_titles or wiki.data_titles or wiki.page_edits_file):
            self.wiki = None
        if self.maps and not self.maps.targets:
            self.maps = None
        if self.sheets and not self.sheets.tabs:
            self.sheets = None
        selected = bool(self.wiki or self.maps or self.sheets)
        if not selected:
            raise ValueError("Select exact wiki titles, map targets, or sheet tabs")
        return self


def load_selection(path: Path) -> PublishSelection:
    return PublishSelection.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


class OperationKind(StrEnum):
    WIKI_REPO = "wiki_repo"
    WIKI_PROSE = "wiki_prose"
    WIKI_ARTICLE = "wiki_article"
    MAP = "map"
    SHEET = "sheet"


class Operation(ClosedModel):
    id: str
    kind: OperationKind
    target: str
    dependencies: list[str]
    dependency_reasons: dict[str, str] = Field(default_factory=dict)
    payload_path: str
    payload_sha256: str
    expected_base: dict[str, Any]
    recovery: str
    inputs: dict[str, str]
    destination: dict[str, Any]


class PreparedPublishPlan(ClosedModel):
    schema_version: Literal[1] = 1
    variant: str
    game_build_id: str
    selection: dict[str, Any]
    selection_path: str | None = None
    configuration: dict[str, Any]
    inputs: dict[str, str]
    operations: list[Operation]
    digest: str = ""

    def immutable(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"digest"})

    def approval_digest(self) -> str:
        return "sha256:" + sha256(canonical(self.immutable()))

    def validate_digest(self) -> None:
        if self.digest != self.approval_digest():
            raise PublishError("Plan digest mismatch. Prepare and review a new plan")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def order_operations(operations: list[Operation]) -> list[Operation]:
    by_id = {operation.id: operation for operation in operations}
    if len(by_id) != len(operations):
        raise PublishError("Duplicate operation IDs")
    rank = {kind: index for index, kind in enumerate(OperationKind)}
    pending = set(by_id)
    result: list[Operation] = []
    while pending:
        ready = [by_id[key] for key in pending if not (set(by_id[key].dependencies) & pending)]
        for operation in ready:
            missing = set(operation.dependencies) - set(by_id)
            if missing:
                raise PublishError(f"{operation.id} requires explicitly selected operations: {sorted(missing)}")
        if not ready:
            raise PublishError(f"Cyclic publication dependencies: {sorted(pending)}")
        operation = min(
            ready,
            key=lambda item: (
                rank[item.kind],
                item.target != "canonical" if item.kind == OperationKind.MAP else False,
                item.target.casefold(),
                item.target,
                item.id,
            ),
        )
        result.append(operation)
        pending.remove(operation.id)
    return result
