"""Spell repository for specialized spell queries."""

from loguru import logger

from erenshor.domain.entities.spell import Spell
from erenshor.domain.value_objects.wiki_link import AbilityLink, StandardLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

# All spell scalar columns, prefixed for JOIN queries.
# The str/end/int columns match Spell field aliases.
_SPELL_COLUMNS = """
    s.stable_key,
    s.spell_name,
    s.display_name,
    s.wiki_page_name,
    s.image_name,
    s.spell_desc,
    s.special_descriptor,
    s.type,
    s.line,
    s.required_level,
    s.mana_cost,
    s.sim_usable,
    s.aggro,
    s.spell_charge_time,
    s.cooldown,
    s.spell_duration_in_ticks,
    s.unstable_duration,
    s.instant_effect,
    s.spell_range,
    s.self_only,
    s.max_level_target,
    s.group_effect,
    s.can_hit_players,
    s.apply_to_caster,
    s.inflict_on_self,
    s.target_damage,
    s.target_healing,
    s.caster_healing,
    s.shielding_amt,
    s.lifetap,
    s.damage_type,
    s.resist_modifier,
    s.add_proc_stable_key,
    s.add_proc_chance,
    s.hp,
    s.ac,
    s.mana,
    s.percent_mana_restoration,
    s.movement_speed,
    s.str,
    s.dex,
    s.end,
    s.agi,
    s.wis,
    s.int,
    s.cha,
    s.mr,
    s.er,
    s.pr,
    s.vr,
    s.damage_shield,
    s.haste,
    s.percent_lifesteal,
    s.atk_roll_modifier,
    s.bleed_damage_percent,
    s.root_target,
    s.stun_target,
    s.charm_target,
    s.fear_target,
    s.crowd_control_spell,
    s.break_on_damage,
    s.break_on_any_action,
    s.taunt_spell,
    s.pet_to_summon_stable_key,
    s.status_effect_to_apply_stable_key,
    s.reap_and_renew,
    s.resonate_chance,
    s.xp_bonus,
    s.automate_attack,
    s.worn_effect,
    s.spell_charge_fx_index,
    s.spell_resolve_fx_index,
    s.spell_icon_name,
    s.shake_dur,
    s.shake_amp,
    s.color_r,
    s.color_g,
    s.color_b,
    s.color_a,
    s.status_effect_message_on_player,
    s.status_effect_message_on_npc,
    -- add_proc link columns (from self-JOIN)
    ap.display_name  AS add_proc_display_name,
    ap.wiki_page_name AS add_proc_wiki_page_name,
    ap.image_name    AS add_proc_image_name,
    -- status_effect link columns (from self-JOIN)
    se.display_name  AS status_effect_display_name,
    se.wiki_page_name AS status_effect_wiki_page_name,
    se.image_name    AS status_effect_image_name
""".strip()

_SPELL_JOINS = """
    LEFT JOIN spells ap ON ap.stable_key = s.add_proc_stable_key
    LEFT JOIN spells se ON se.stable_key = s.status_effect_to_apply_stable_key
"""


def _spell_from_row(row: object) -> Spell:
    """Build a Spell entity from a joined query row, populating pre-built link fields."""
    d = dict(row)  # type: ignore[call-overload]

    # Extract and remove link columns from dict before Pydantic validation
    add_proc_display = d.pop("add_proc_display_name", None)
    add_proc_wiki = d.pop("add_proc_wiki_page_name", None)
    d.pop("add_proc_image_name", None)
    se_display = d.pop("status_effect_display_name", None)
    se_wiki = d.pop("status_effect_wiki_page_name", None)
    d.pop("status_effect_image_name", None)

    spell = Spell.model_validate(d)

    if add_proc_display is not None:
        spell.add_proc_link = AbilityLink(
            page_title=str(add_proc_wiki) if add_proc_wiki else None,
            display_name=str(add_proc_display),
        )

    if se_display is not None:
        spell.status_effect_link = StandardLink(
            page_title=str(se_wiki) if se_wiki else None,
            display_name=str(se_display),
        )

    return spell


class SpellRepository(BaseRepository[Spell]):
    """Repository for spell-specific database queries.

    All queries target the clean snake_case database written by ``extract build``.
    """

    def get_spells_for_wiki_generation(self) -> list[Spell]:
        """Get all spells for wiki page generation.

        The clean DB already excludes blank-named spells. add_proc_link and
        status_effect_link are populated via self-JOINs so section generators
        never need a resolver.

        Returns:
            List of Spell entities ordered by display_name.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = f"""
            SELECT {_SPELL_COLUMNS}
            FROM spells s
            {_SPELL_JOINS}
            ORDER BY s.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            spells = [_spell_from_row(row) for row in rows]
            logger.debug(f"Retrieved {len(spells)} spells for wiki generation")
            return spells
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spells for wiki: {e}") from e

    def get_spell_by_stable_key(self, stable_key: str) -> Spell | None:
        """Get single spell by stable key.

        Args:
            stable_key: Spell stable key (format: 'spell:resource_name')

        Returns:
            Spell entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = f"""
            SELECT {_SPELL_COLUMNS}
            FROM spells s
            {_SPELL_JOINS}
            WHERE s.stable_key = ?
            LIMIT 1
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                return None
            return _spell_from_row(rows[0])
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spell by stable_key={stable_key}: {e}") from e

    def get_spell_classes(self, stable_key: str) -> list[str]:
        """Get class restrictions for a spell.

        Args:
            stable_key: Spell stable key (format: 'spell:resource_name')

        Returns:
            List of class names that can use this spell.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT class_name
            FROM spell_classes
            WHERE spell_stable_key = ?
            ORDER BY class_name
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            classes = [str(row["class_name"]) for row in rows]
            logger.debug(f"Retrieved {len(classes)} class restrictions for spell {stable_key}")
            return classes
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spell classes for {stable_key}: {e}") from e

    def get_spells_used_by_character(self, character_stable_key: str) -> list[AbilityLink]:
        """Get spells used by a character (NPC/enemy).

        Returns pre-built AbilityLink objects so section generators can render
        spell links without a resolver.

        Args:
            character_stable_key: Character stable key (format: 'character:resource_name')

        Returns:
            List of AbilityLink objects (sorted alphabetically, deduplicated).

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT s.display_name, s.wiki_page_name, s.image_name
            FROM spells s
            WHERE s.stable_key IN (
                SELECT spell_stable_key FROM character_attack_spells cas
                JOIN character_deduplications d ON d.member_stable_key = cas.character_stable_key
                WHERE d.group_key = (SELECT group_key FROM character_deduplications WHERE member_stable_key = ?)
                UNION
                SELECT spell_stable_key FROM character_buff_spells cbs
                JOIN character_deduplications d ON d.member_stable_key = cbs.character_stable_key
                WHERE d.group_key = (SELECT group_key FROM character_deduplications WHERE member_stable_key = ?)
                UNION
                SELECT spell_stable_key FROM character_heal_spells chs
                JOIN character_deduplications d ON d.member_stable_key = chs.character_stable_key
                WHERE d.group_key = (SELECT group_key FROM character_deduplications WHERE member_stable_key = ?)
                UNION
                SELECT spell_stable_key FROM character_group_heal_spells cghs
                JOIN character_deduplications d ON d.member_stable_key = cghs.character_stable_key
                WHERE d.group_key = (SELECT group_key FROM character_deduplications WHERE member_stable_key = ?)
                UNION
                SELECT spell_stable_key FROM character_cc_spells ccs
                JOIN character_deduplications d ON d.member_stable_key = ccs.character_stable_key
                WHERE d.group_key = (SELECT group_key FROM character_deduplications WHERE member_stable_key = ?)
                UNION
                SELECT spell_stable_key FROM character_taunt_spells cts
                JOIN character_deduplications d ON d.member_stable_key = cts.character_stable_key
                WHERE d.group_key = (SELECT group_key FROM character_deduplications WHERE member_stable_key = ?)
            )
            ORDER BY s.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (character_stable_key,) * 6)
            links = [
                AbilityLink(
                    page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                    display_name=str(row["display_name"]),
                    image_name=str(row["image_name"]) if row["image_name"] else None,
                )
                for row in rows
            ]
            logger.debug(f"Found {len(links)} spells used by character '{character_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spells used by character '{character_stable_key}': {e}") from e
