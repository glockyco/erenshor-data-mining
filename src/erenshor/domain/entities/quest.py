"""Quest entity model.

This module defines the Quest domain entity representing in-game quests
and their objectives, rewards, and requirements.
"""

from pydantic import Field

from .base import BaseEntity


class Quest(BaseEntity):
    """Domain entity representing an in-game quest.

    Quests are tasks given to players with objectives, requirements, and rewards.
    The DBName field is used as the stable identifier.

    All fields match the Unity export schema from the Quests table.
    """

    # Primary keys and identifiers
    stable_key: str | None = Field(default=None, description="Stable key from database (primary key)")

    # Display fields
    quest_name: str | None = Field(default=None, description="Display name")
    quest_desc: str | None = Field(default=None, description="Quest description")

    # Requirements
    # Required items are stored in QuestRequiredItemRecord junction table

    # Rewards
    xp_on_complete: int | None = Field(default=None, description="XP reward")
    item_on_complete_stable_key: str | None = Field(default=None, description="Item reward ResourceName")
    gold_on_complete: int | None = Field(default=None, description="Gold reward")

    # Quest chains
    assign_new_quest_on_complete_stable_key: str | None = Field(
        default=None,
        description='Quest assigned on completion (format: "QuestName (DBName)" e.g., "Destroying Aragath (Aragath2)")',
    )
    complete_other_quest_db_names: str | None = Field(
        default=None,
        description='Other quests completed (format: "QuestName (DBName)" e.g., "Destroying Aragath (Aragath2)")',
    )

    # Dialog
    dialog_on_success: str | None = Field(default=None, description="Success dialog text")
    dialog_on_partial_success: str | None = Field(default=None, description="Partial success dialog")
    disable_text: str | None = Field(default=None, description="Disabled quest text")

    # Faction effects
    affected_factions: str | None = Field(
        default=None,
        description='Affected faction IDs (comma-separated Factions.REFNAME values e.g., "Fernalla, Sivakayans")',
    )
    affected_faction_amounts: str | None = Field(
        default=None,
        description='Faction change amounts (comma-separated numbers (one per affected_factions entry) e.g., "1, -1")',
    )

    # Quest flags
    assign_this_quest_on_partial_complete: int | None = Field(
        default=None, description="Assign on partial completion (boolean)"
    )
    repeatable: int | None = Field(default=None, description="Is repeatable quest (boolean)")
    disable_quest: int | None = Field(default=None, description="Quest disabled (boolean)")
    kill_turn_in_holder: int | None = Field(default=None, description="Kill turn-in holder (boolean)")
    destroy_turn_in_holder: int | None = Field(default=None, description="Destroy turn-in holder (boolean)")
    drop_invuln_on_holder: int | None = Field(default=None, description="Drop invulnerability (boolean)")
    once_per_spawn_instance: int | None = Field(default=None, description="Once per spawn (boolean)")

    # Achievements
    set_achievement_on_get: str | None = Field(default=None, description="Achievement on quest accept")
    set_achievement_on_finish: str | None = Field(default=None, description="Achievement on completion")
