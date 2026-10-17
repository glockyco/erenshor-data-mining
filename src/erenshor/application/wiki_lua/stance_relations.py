"""Publish exact stance activation relations without changing live entity schemas."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from erenshor.application.wiki_lua.links import link_refs
from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.application.wiki_lua.stances import StanceDataRepository, build_stances_data

if TYPE_CHECKING:
    from erenshor.domain.entities.stance import Stance
    from erenshor.domain.value_objects.wiki_link import AbilityLink


class StanceActivationRepository(Protocol):
    """Canonical activation query used by articles and tooltips."""

    def get_skills_using_stance(self, stance_stable_key: str) -> list[AbilityLink]: ...


def build_stance_relations_data(stances: Iterable[Stance], skill_repo: StanceActivationRepository) -> dict[str, object]:
    """Return every visible activator and only an unambiguous tooltip identity."""
    rows: dict[str, object] = {}
    stance_rows = cast("dict[str, object]", build_stances_data(stances)["stances"])
    for key in sorted(stance_rows):
        activators = skill_repo.get_skills_using_stance(key)
        identities: dict[str, AbilityLink] = {}
        for activator in activators:
            skill_key = activator.stable_key
            if not skill_key or not skill_key.startswith("skill:"):
                raise ValueError(f"{key}: activating skill has no exact skill identity")
            previous = identities.get(skill_key)
            if previous is not None and previous != activator:
                raise ValueError(f"{key}: conflicting activation references for {skill_key}")
            identities[skill_key] = activator
        refs = link_refs((identities[key] for key in sorted(identities)), "ability")
        record: dict[str, object] = {"activatedBy": refs}
        # Hidden activators still disprove uniqueness. Visibility controls links,
        # not which native skill the stance belongs to.
        if len(identities) == 1 and len(refs) == 1:
            record["tooltipSkillStableKey"] = next(iter(identities))
        rows[key] = record
    return {"stances": rows}


def generate_stance_relations_module(stance_repo: StanceDataRepository, skill_repo: StanceActivationRepository) -> str:
    """Generate the narrow immutable stance relation supplement."""
    return module_text(build_stance_relations_data(stance_repo.get_all(), skill_repo))


def write_stance_relations_module(
    stance_repo: StanceDataRepository, skill_repo: StanceActivationRepository, output_root: Path
) -> Path:
    """Write Module:Erenshor/Data/StanceRelations through native generation."""
    path = output_root / "Erenshor" / "Data" / "StanceRelations.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_stance_relations_module(stance_repo, skill_repo), encoding="utf-8")
    return path
