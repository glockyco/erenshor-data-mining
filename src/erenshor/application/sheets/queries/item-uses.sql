-- Conditions are keyed by use_key in the conditions tab, and locations by location_source_key in the locations tab.
SELECT u.*, i.display_name AS item_name
FROM item_uses u
LEFT JOIN items i ON i.stable_key = u.item_stable_key
ORDER BY u.item_stable_key, u.use_key;
