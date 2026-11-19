"""Service for mapping internal class names to user-facing display names."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.infrastructure.database.connection import DatabaseConnection


class ClassDisplayNameService:
    """Maps internal ClassName to user-facing DisplayName for wiki generation.

    The classes table maps internal names to user-facing names. Load that
    mapping once and reject missing names rather than publishing internal labels.
    """

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db
        self._mapping: dict[str, str] | None = None

    def get_display_name(self, class_name: str) -> str:
        """Map a single internal class name to its display name."""
        mapping = self._get_mapping()
        if class_name not in mapping:
            raise ValueError(f"Class {class_name} has no display name in classes")
        return mapping[class_name]

    def map_class_list(self, class_names: list[str]) -> list[str]:
        """Map internal class names to display names, sorted alphabetically."""
        display_names = [self.get_display_name(name) for name in class_names]
        return sorted(display_names)

    def get_all_display_names(self) -> list[str]:
        """Get all known display names, sorted alphabetically."""
        mapping = self._get_mapping()
        return sorted(mapping.values())

    def get_all_internal_names(self) -> list[str]:
        """Get all known internal class names, sorted alphabetically."""
        mapping = self._get_mapping()
        return sorted(mapping.keys())

    def _get_mapping(self) -> dict[str, str]:
        if self._mapping is None:
            self._mapping = self._load_mapping()
        return self._mapping

    def _load_mapping(self) -> dict[str, str]:
        """Load ClassName -> DisplayName mapping from the Classes table.

        Raises:
            ValueError: If classes or their display names are missing.
        """
        query = """
            SELECT class_name, display_name
            FROM classes
            WHERE class_name != 'Default'
        """
        try:
            with self._db.connect() as conn:
                cursor = conn.execute(query)
                rows = cursor.fetchall()
        except Exception as e:
            raise ValueError(f"Failed to load class display names from classes: {e}") from e

        mapping = {}
        for row in rows:
            class_name = row["class_name"]
            display_name = row["display_name"]
            if not display_name or not display_name.strip():
                raise ValueError(f"Class {class_name} has no display name")
            mapping[class_name] = display_name
        if not mapping:
            raise ValueError("Classes table is empty")
        return mapping
