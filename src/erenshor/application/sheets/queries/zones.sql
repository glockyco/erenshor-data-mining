SELECT
    z.scene_name AS 'Zone:SceneName',
    z.zone_name AS 'Zone:ZoneName',
    z.is_dungeon AS 'Zone:IsDungeon',
    z.achievement AS 'Zone:Achievement',
    z.complete_quest_on_enter_stable_key AS 'Zone:CompleteQuestOnEnter',
    z.complete_second_quest_on_enter_stable_key AS 'Zone:CompleteSecondQuestOnEnter',
    z.assign_quest_on_enter_stable_key AS 'Zone:AssignQuestOnEnter',
    zae.atlas_index AS 'Atlas:Index',
    zae.id AS 'Atlas:Id',
    zae.zone_name AS 'Atlas:ZoneName',
    zae.level_range_low AS 'Atlas:LevelRangeLow',
    zae.level_range_high AS 'Atlas:LevelRangeHigh',
    zae.dungeon AS 'Atlas:Dungeon',
    (SELECT GROUP_CONCAT(neighbor_zone_stable_key, ', ')
     FROM zone_atlas_neighbors zan
     WHERE zan.zone_atlas_id = zae.id) AS 'Atlas:NeighboringZones',
    zae.resource_name AS 'Atlas:ResourceName'
FROM zones z
LEFT JOIN zone_atlas_entries zae ON
    zae.zone_name = z.scene_name
    OR (z.scene_name = 'PrielPlateau' AND zae.zone_name = 'PrielPlateau')
    OR (z.scene_name LIKE 'Undercity' AND zae.resource_name = 'Undercity')
ORDER BY z.scene_name;
