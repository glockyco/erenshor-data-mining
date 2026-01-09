SELECT
    StableKey,
    ActivationWords,
    Responses,
    RelevantScenes,
    RequiredLevelToKnow,
    ResourceName
FROM GuildTopics
ORDER BY RequiredLevelToKnow, ResourceName;
