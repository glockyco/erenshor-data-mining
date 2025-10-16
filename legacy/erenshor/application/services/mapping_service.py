from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import Engine

from erenshor.domain.mapping import MappingFile, load_mapping_file
from erenshor.application.services.mapping_validation import (
    scan_conflicts,
    validate_completeness,
    validate_existence,
)
from erenshor.infrastructure.config.paths import get_path_resolver

__all__ = ["MappingService"]


@dataclass
class MappingService:
    mapping: MappingFile
    path: Path

    @classmethod
    def load(cls) -> "MappingService":
        """Load mapping from project root using PathResolver."""
        resolver = get_path_resolver()
        mapping_path = resolver.mapping_file
        return cls(mapping=load_mapping_file(mapping_path), path=mapping_path)

    def validate(self, engine: Engine) -> tuple[list[str], list[str]]:
        conflicts = scan_conflicts(engine)
        missing = validate_completeness(self.mapping, conflicts)
        existence_errors = validate_existence(self.mapping, engine)
        return missing, existence_errors

    def is_push_allowed(self, engine: Engine) -> bool:
        missing, existence_errors = self.validate(engine)
        return not missing and not existence_errors
