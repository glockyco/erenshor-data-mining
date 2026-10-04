"""Read the clean database game build for wiki data generation."""

from pydantic import BaseModel

from erenshor.infrastructure.database.repository import BaseRepository


class BuildMetadataRepository(BaseRepository[BaseModel]):
    """Read build provenance from the clean database."""

    def get_build_metadata(self) -> tuple[str, str]:
        """Return the build ID and publish time needed by the wiki."""
        rows = self._execute_raw("SELECT game_build_id, game_build_published_at FROM code_facts_meta LIMIT 1")
        if not rows or not rows[0]["game_build_id"] or not rows[0]["game_build_published_at"]:
            raise ValueError("code_facts_meta has no complete game build row. Rebuild with 'erenshor extract build'.")
        return str(rows[0]["game_build_id"]), str(rows[0]["game_build_published_at"])
