"""Authored live-vs-local parity contract.

This file is committed. It declares *which* components, elements, and rendered
properties the parity gate checks. It contains no values captured from the live
wiki; the expected values live in the gitignored ``baseline.json`` produced by
``parity_check.py --capture``.

Property keys are interpreted by ``extract.py``:

- a plain CSS property name (``color``, ``border-bottom-width``) reads
  ``getComputedStyle(el).getPropertyValue(prop)``;
- ``@class:NAME`` resolves to ``"true"``/``"false"`` for ``el.classList``.

Each page names a live reference path and the local fixture title that exercises
the same components, so unrelated page content never affects the comparison.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    """One rendered element and the properties to capture from it."""

    name: str
    selector: str
    properties: tuple[str, ...]


@dataclass(frozen=True)
class ParityPage:
    """A live reference page paired with the local fixture that mirrors it."""

    name: str
    live_path: str
    local_title: str
    targets: tuple[Target, ...]


# Shared infobox surface that every entity template must render. Proves the
# template emits a real PortableInfobox (not a plain table) with a styled title
# and bordered data rows, independent of the entity's content.
ENTITY_INFOBOX_TARGETS: tuple[Target, ...] = (
    Target(
        name="shell",
        selector=".portable-infobox",
        properties=("display", "float", "background-color"),
    ),
    Target(
        name="title",
        selector=".portable-infobox .pi-title",
        properties=("font-weight", "color"),
    ),
    Target(
        name="data-row",
        selector=".portable-infobox .pi-data",
        properties=("display", "border-bottom-width", "border-bottom-style"),
    ),
)

PAGES: tuple[ParityPage, ...] = (
    ParityPage(
        name="infobox",
        live_path="/wiki/A_Hermit",
        local_title="Captain_Rowan",
        targets=(
            Target(
                name="shell",
                selector=".portable-infobox",
                properties=("display", "float", "background-color"),
            ),
            Target(
                name="title",
                selector=".portable-infobox .pi-title",
                properties=("font-weight", "color"),
            ),
            Target(
                name="data-row",
                selector=".portable-infobox .pi-data",
                properties=("display", "border-bottom-width", "border-bottom-style"),
            ),
            Target(
                name="section-group",
                selector=".portable-infobox .pi-group",
                properties=("border-bottom-width", "border-bottom-style", "border-bottom-color"),
            ),
            Target(
                name="header",
                selector=".portable-infobox .pi-header",
                properties=("background-color", "color", "font-weight"),
            ),
            Target(
                name="horizontal-divider",
                selector=".portable-infobox .pi-horizontal-group-item:not(:first-child)",
                properties=("border-left-width", "border-left-style", "border-left-color"),
            ),
        ),
    ),
    ParityPage(
        name="item",
        live_path="/wiki/Abyssal_Plate",
        local_title="Abyssal_Plate",
        targets=ENTITY_INFOBOX_TARGETS,
    ),
    ParityPage(
        name="quest",
        live_path="/wiki/A_Magical_Sword_in_Port_Azure",
        local_title="A_Magical_Sword_in_Port_Azure",
        targets=ENTITY_INFOBOX_TARGETS,
    ),
    ParityPage(
        name="zone",
        live_path="/wiki/Port_Azure",
        local_title="Port_Azure",
        targets=ENTITY_INFOBOX_TARGETS,
    ),
    ParityPage(
        name="stance",
        live_path="/wiki/Aggressive",
        local_title="Aggressive",
        targets=ENTITY_INFOBOX_TARGETS,
    ),
    ParityPage(
        name="spell",
        live_path="/wiki/Minor_Lightning",
        local_title="Minor_Lightning",
        targets=ENTITY_INFOBOX_TARGETS,
    ),
    ParityPage(
        name="skill",
        live_path="/wiki/Backstab",
        local_title="Backstab",
        targets=ENTITY_INFOBOX_TARGETS,
    ),
)
