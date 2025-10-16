"""Mapping models (Pydantic) and helpers (scaffold)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field

__all__ = [
    "MappingFile",
    "MappingMetadata",
    "Rule",
    "load_mapping_file",
    "save_mapping_file",
]


MappingType = Literal["custom", "merge", "exclude"]


class Rule(BaseModel):
    wiki_page_name: Optional[str] = None
    display_name: Optional[str] = None
    image_name: Optional[str] = None
    mapping_type: MappingType = "custom"
    reason: Optional[str] = None


class MappingMetadata(BaseModel):
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_rules: int = 0


class MappingFile(BaseModel):
    metadata: MappingMetadata = Field(default_factory=MappingMetadata)
    rules: Dict[str, Rule] = Field(default_factory=dict)

    def add(self, key: str, rule: Rule) -> None:
        self.rules[key] = rule
        self.metadata.total_rules = len(self.rules)
        self.metadata.updated_at = datetime.now(timezone.utc)


def load_mapping_file(path: str | Path) -> MappingFile:
    p = Path(path)
    if not p.exists():
        return MappingFile()
    data = json.loads(p.read_text(encoding="utf-8"))
    return MappingFile.model_validate(data)


def save_mapping_file(mapping: MappingFile, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(mapping.model_dump_json(indent=2), encoding="utf-8")
