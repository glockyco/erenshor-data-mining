"""Generate the wiki data module for the game build."""

from pathlib import Path
from typing import Protocol

from erenshor.application.wiki_lua.lua_writer import module_text


class BuildDataRepository(Protocol):
    """Repository methods needed for the game build module."""

    def get_build_metadata(self) -> tuple[str, str]: ...


def write_build_module(build_repo: BuildDataRepository, output_root: Path) -> Path:
    """Write build provenance as a Scribunto data module."""
    game_build_id, published_at = build_repo.get_build_metadata()
    output_path = output_root / "Erenshor" / "Data" / "Build.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        module_text({"gameBuildId": game_build_id, "publishedAt": published_at}),
        encoding="utf-8",
    )
    return output_path
