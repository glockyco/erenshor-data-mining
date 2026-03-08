SELECT
    stable_key,
    activation_words,
    responses,
    relevant_scenes,
    required_level_to_know,
    resource_name
FROM guild_topics
ORDER BY required_level_to_know, resource_name;
