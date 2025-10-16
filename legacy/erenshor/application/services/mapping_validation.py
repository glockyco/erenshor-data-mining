"""Conflict scanning and mapping validation (initial scaffold).

Currently scans spells only; other entity types will be added next.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from sqlalchemy.engine import Engine

from erenshor.infrastructure.database.repositories import (
    get_characters,
    get_factions,
    get_items,
    get_skills,
    get_spells,
)

from erenshor.domain.mapping import MappingFile

__all__ = [
    "ConflictGroup",
    "EntityRef",
    "scan_conflicts",
    "validate_completeness",
    "validate_existence",
]


@dataclass
class EntityRef:
    content_type: str  # 'spell', 'item', 'skill', 'character'
    display_name: str
    stable_identifier: str


@dataclass
class ConflictGroup:
    display_name: str
    entities: List[EntityRef]


def scan_conflicts(engine: Engine) -> List[ConflictGroup]:
    groups: Dict[str, List[EntityRef]] = defaultdict(list)
    # Spells
    for s in get_spells(engine, obtainable_only=False):
        ref = EntityRef(
            content_type="spell",
            display_name=s.SpellName,
            stable_identifier=s.ResourceName,
        )
        groups[s.SpellName].append(ref)

    # Items
    for it in get_items(engine, obtainable_only=False):
        ref = EntityRef(
            content_type="item",
            display_name=it.ItemName,
            stable_identifier=it.ResourceName,
        )
        groups[it.ItemName].append(ref)

    # Skills
    for sk in get_skills(engine):
        ref = EntityRef(
            content_type="skill",
            display_name=sk.SkillName,
            stable_identifier=sk.ResourceName,
        )
        groups[sk.SkillName].append(ref)

    # Characters
    for ch in get_characters(engine):
        if ch.IsPrefab and ch.ObjectName:
            stable = ch.ObjectName
        else:
            scene = ch.Scene or "Unknown"
            x = f"{ch.X:.2f}" if ch.X is not None else "0.00"
            y = f"{ch.Y:.2f}" if ch.Y is not None else "0.00"
            z = f"{ch.Z:.2f}" if ch.Z is not None else "0.00"
            stable = f"{ch.ObjectName}|{scene}|{x}|{y}|{z}"
        ref = EntityRef(
            content_type="character",
            display_name=ch.NPCName,
            stable_identifier=stable,
        )
        groups[ch.NPCName].append(ref)

    # Factions
    for faction in get_factions(engine):
        ref = EntityRef(
            content_type="faction",
            display_name=faction.FactionDesc,
            stable_identifier=faction.REFNAME,
        )
        groups[faction.FactionDesc].append(ref)

    conflicts: List[ConflictGroup] = []
    for name, refs in groups.items():
        if len(refs) > 1:
            conflicts.append(
                ConflictGroup(
                    display_name=name,
                    entities=sorted(
                        refs, key=lambda r: (r.content_type, r.stable_identifier)
                    ),
                )
            )
    conflicts.sort(key=lambda g: g.display_name.lower())
    return conflicts


def validate_completeness(
    mapping: MappingFile, conflicts: List[ConflictGroup]
) -> List[str]:
    missing: List[str] = []
    for g in conflicts:
        for e in g.entities:
            key = f"{e.content_type}:{e.stable_identifier}"
            if key not in mapping.rules:
                missing.append(key)
    return missing


def validate_existence(mapping: MappingFile, engine: Engine) -> List[str]:
    """Check that mapping rules reference entities that exist in the DB."""
    # Build a set of existing keys by type
    existing: set[str] = set()
    for s in get_spells(engine, obtainable_only=False):
        existing.add(f"spell:{s.ResourceName}")
    for it in get_items(engine, obtainable_only=False):
        existing.add(f"item:{it.ResourceName}")
    for sk in get_skills(engine):
        existing.add(f"skill:{sk.ResourceName}")
    for ch in get_characters(engine):
        if ch.IsPrefab and ch.ObjectName:
            stable = ch.ObjectName
        else:
            scene = ch.Scene or "Unknown"
            x = f"{ch.X:.2f}" if ch.X is not None else "0.00"
            y = f"{ch.Y:.2f}" if ch.Y is not None else "0.00"
            z = f"{ch.Z:.2f}" if ch.Z is not None else "0.00"
            stable = f"{ch.ObjectName}|{scene}|{x}|{y}|{z}"
        existing.add(f"character:{stable}")

    for faction in get_factions(engine):
        existing.add(f"faction:{faction.REFNAME}")

    errors: list[str] = []
    for key in mapping.rules.keys():
        if key not in existing:
            errors.append(f"Mapping references non-existent entity: {key}")
    return errors
