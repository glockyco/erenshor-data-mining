SELECT
    za.SceneName AS 'Zone:SceneName',
    za.ZoneName AS 'Zone:ZoneName',
    za.IsDungeon AS 'Zone:IsDungeon',
    za.Achievement AS 'Zone:Achievement',
    za.CompleteQuestOnEnterStableKey AS 'Zone:CompleteQuestOnEnter',
    za.CompleteSecondQuestOnEnterStableKey AS 'Zone:CompleteSecondQuestOnEnter',
    za.AssignQuestOnEnterStableKey AS 'Zone:AssignQuestOnEnter',
    zae.AtlasIndex AS 'Atlas:Index',
    zae.Id AS 'Atlas:Id',
    zae.ZoneName AS 'Atlas:ZoneName',
    zae.LevelRangeLow AS 'Atlas:LevelRangeLow',
    zae.LevelRangeHigh AS 'Atlas:LevelRangeHigh',
    zae.Dungeon AS 'Atlas:Dungeon',
    (SELECT GROUP_CONCAT(NeighborZoneStableKey, ', ')
     FROM ZoneAtlasNeighbors zan
     WHERE zan.ZoneAtlasId = zae.Id) AS 'Atlas:NeighboringZones',
    zae.ResourceName AS 'Atlas:ResourceName'
FROM Zones za
LEFT JOIN ZoneAtlasEntries zae ON
    zae.ZoneName = za.SceneName
    OR (za.SceneName = 'PrielPlateau' AND zae.ZoneName = 'PrielianPlateau')
    OR (za.SceneName LIKE 'Undercity' AND zae.ResourceName = 'Undercity')
ORDER BY za.SceneName;
