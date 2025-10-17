"""Spawn point entity model.

This module defines the SpawnPoint domain entity representing creature/NPC
spawn locations and their spawn behavior.
"""

from pydantic import Field

from .base import BaseEntity


class SpawnPoint(BaseEntity):
    """Domain entity representing a creature/NPC spawn point.

    SpawnPoints define where creatures spawn in the game world, with configuration
    for spawn timing, patrol behavior, and conditional spawning.

    All fields match the Unity export schema from the SpawnPoints table.
    """

    # Primary key and references
    id: int = Field(description="Database ID (primary key)")
    coordinate_id: int | None = Field(default=None, description="Coordinate reference for location")

    # Spawn state
    is_enabled: int | None = Field(default=None, description="Spawn is active (boolean)")

    # Spawn properties
    rare_npc_chance: int | None = Field(default=None, description="Rare spawn chance percentage")
    level_mod: int | None = Field(default=None, description="Level modifier for spawned NPCs")

    # Spawn timing (supports up to 4 spawn slots)
    # Group size adjustments: spawn delays scale based on group size
    spawn_delay_1: float | None = Field(
        default=None, description="Respawn delay for solo players (group size 1) (seconds)"
    )
    spawn_delay_2: float | None = Field(default=None, description="Respawn delay for groups of 2-3 players (seconds)")
    spawn_delay_3: float | None = Field(default=None, description="Respawn delay for groups of 4 players (seconds)")
    spawn_delay_4: float | None = Field(default=None, description="Respawn delay for groups of 5+ players (seconds)")

    # Spawn behavior
    staggerable: int | None = Field(default=None, description="Stagger spawn timing (boolean)")
    stagger_mod: float | None = Field(default=None, description="Stagger timing modifier")
    night_spawn: int | None = Field(default=None, description="Only spawns at night (boolean)")

    # Patrol behavior
    patrol_points: str | None = Field(default=None, description="Patrol waypoint data")
    loop_patrol: int | None = Field(default=None, description="Loop patrol path (boolean)")
    random_wander_range: float | None = Field(default=None, description="Random wander distance")

    # Conditional spawning
    spawn_upon_quest_complete_db_name: str | None = Field(default=None, description="Spawn when quest is completed")
    stop_if_quest_complete_db_names: str | None = Field(default=None, description="Stop spawning when quests complete")

    # Protection
    protector_name: str | None = Field(default=None, description="Protector character name")

    @property
    def has_patrol(self) -> bool:
        """Check if spawn point has patrol behavior.

        Returns:
            True if patrol points are configured
        """
        return self.patrol_points is not None and len(self.patrol_points.strip()) > 0

    @property
    def has_random_wander(self) -> bool:
        """Check if spawn point has random wander behavior.

        Returns:
            True if random wander range is configured
        """
        return self.random_wander_range is not None and self.random_wander_range > 0
