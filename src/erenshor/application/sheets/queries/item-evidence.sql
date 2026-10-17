-- Contributing outcomes remain evidence, not additional named acquisition sources.
SELECT owner_key, input_relation, input_primary_key
FROM item_provenance_evidence
ORDER BY owner_key, input_relation, input_primary_key;
