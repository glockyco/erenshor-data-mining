"""Character/enemy template contexts."""

from __future__ import annotations

import builtins as _b

from pydantic import BaseModel


class CharacterInfoboxContext(BaseModel):
    """Minimal character/NPC infobox context."""

    block_id: _b.str
    name: _b.str
    image: _b.str = ""
    imagecaption: _b.str = ""
    type: _b.str = ""
    faction: _b.str = ""
    zones: _b.str = ""
    level: _b.str = ""
    experience: _b.str = ""


class EnemyInfoboxContext(BaseModel):
    """Enemy infobox context with full stats."""

    block_id: _b.str
    name: _b.str
    image: _b.str = ""
    imagecaption: _b.str = ""
    type: _b.str = ""
    faction: _b.str = ""
    factionChange: _b.str = ""
    zones: _b.str = ""
    coordinates: _b.str = ""
    spawnchance: _b.str = ""
    respawn: _b.str = ""
    guaranteeddrops: _b.str = ""
    droprates: _b.str = ""
    level: _b.str = ""
    experience: _b.str = ""
    health: _b.str = ""
    mana: _b.str = ""
    ac: _b.str = ""
    strength: _b.str = ""
    endurance: _b.str = ""
    dexterity: _b.str = ""
    agility: _b.str = ""
    intelligence: _b.str = ""
    wisdom: _b.str = ""
    charisma: _b.str = ""
    magic: _b.str = ""
    poison: _b.str = ""
    elemental: _b.str = ""
    void: _b.str = ""


__all__ = ["CharacterInfoboxContext", "EnemyInfoboxContext"]
