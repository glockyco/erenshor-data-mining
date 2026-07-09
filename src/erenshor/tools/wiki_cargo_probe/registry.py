from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import ProbeScenario
from .scenarios.lifecycle import build_lifecycle_probe
from .scenarios.multi_entity import build_multi_entity_probe
from .scenarios.recreate_batching import build_recreate_batching_probe
from .scenarios.standard import build_direct_probe, build_lua_nested_probe, build_nested_probe


@dataclass(frozen=True, slots=True)
class ProbeBuildOptions:
    prefix: str
    batch_pages: int


ProbeBuilder = Callable[[ProbeBuildOptions], ProbeScenario]

PROBE_BUILDERS: dict[str, ProbeBuilder] = {
    "direct": lambda options: build_direct_probe(options.prefix),
    "nested": lambda options: build_nested_probe(options.prefix),
    "lua-nested": lambda options: build_lua_nested_probe(options.prefix),
    "lifecycle": lambda options: build_lifecycle_probe(options.prefix),
    "multi-entity": lambda options: build_multi_entity_probe(options.prefix),
    "recreate-batching": lambda options: build_recreate_batching_probe(options.prefix, options.batch_pages),
}


def build_scenarios(prefix: str, choice: str, batch_pages: int) -> list[ProbeScenario]:
    options = ProbeBuildOptions(prefix=prefix, batch_pages=batch_pages)
    if choice == "both":
        return [PROBE_BUILDERS["direct"](options), PROBE_BUILDERS["nested"](options)]
    if choice == "all":
        return [builder(options) for builder in PROBE_BUILDERS.values()]
    return [PROBE_BUILDERS[choice](options)]


def candidate_choices() -> tuple[str, ...]:
    return (*tuple(PROBE_BUILDERS), "both", "all")
