-- The conditions tab keys conditions by acquisition_key, and the shared ones of a mechanism by mechanic.
-- The locations tab keys locations by location_source_key.
SELECT a.*, i.display_name AS item_name
FROM item_acquisitions a
LEFT JOIN items i ON i.stable_key = a.item_stable_key
ORDER BY a.item_stable_key, a.acquisition_key;
