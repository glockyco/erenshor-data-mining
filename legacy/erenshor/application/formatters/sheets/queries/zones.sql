SELECT
    za.SceneName AS 'Zone:SceneName',
    za.ZoneName AS 'Zone:ZoneName',
    za.IsDungeon AS 'Zone:IsDungeon',
    za.Achievement AS 'Zone:Achievement',
    za.CompleteQuestOnEnter AS 'Zone:CompleteQuestOnEnter',
    za.CompleteSecondQuestOnEnter AS 'Zone:CompleteSecondQuestOnEnter',
    za.AssignQuestOnEnter AS 'Zone:AssignQuestOnEnter',
    zae.AtlasIndex AS 'Atlas:Index',
    zae.Id AS 'Atlas:Id',
    zae.ZoneName AS 'Atlas:ZoneName',
    zae.LevelRangeLow AS 'Atlas:LevelRangeLow',
    zae.LevelRangeHigh AS 'Atlas:LevelRangeHigh',
    zae.Dungeon AS 'Atlas:Dungeon',
    zae.NeighboringZones AS 'Atlas:NeighboringZones',
    zae.ResourceName AS 'Atlas:ResourceName'
FROM ZoneAnnounces za
LEFT JOIN ZoneAtlasEntries zae ON
    zae.ZoneName = za.SceneName
    OR (za.SceneName = 'PrielPlateau' AND zae.ZoneName = 'PrielianPlateau')
    OR (za.SceneName LIKE 'Undercity' AND zae.ResourceName = 'Undercity')
UNION
SELECT za.*, zae.*
FROM ZoneAtlasEntries zae
LEFT JOIN ZoneAnnounces za ON
    zae.ZoneName = za.SceneName
    OR (za.SceneName = 'PrielPlateau' AND zae.ZoneName = 'PrielianPlateau')
    OR (za.SceneName LIKE 'Undercity' AND zae.ResourceName = 'Undercity');
