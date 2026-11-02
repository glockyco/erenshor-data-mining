-- The conditions tab keys conditions by use_key, and the shared ones of a mechanism by mechanic.
-- The locations tab keys locations by location_source_key.
SELECT u.*, i.display_name AS item_name
FROM item_uses u
LEFT JOIN items i ON i.stable_key = u.item_stable_key
ORDER BY u.item_stable_key, u.use_key;
