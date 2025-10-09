SELECT
    WikiUrl,
    Type,
    Name,
    Tier,
    CASE
        WHEN CurrentWikiString = '' THEN 'Object is missing from the wiki.'
        ELSE ComparisonResult
        END AS ComparisonResult,
    CurrentWikiString,
    SuggestedWikiString,
    ComparisonTimestamp
FROM WikiComparison
ORDER BY Type, Name, Tier;
