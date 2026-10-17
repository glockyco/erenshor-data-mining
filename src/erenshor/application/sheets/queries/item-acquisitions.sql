-- Child facts are keyed by acquisition_key in the conditions, locations and evidence tabs.
SELECT a.*, i.display_name AS item_name
FROM item_acquisitions a
LEFT JOIN items i ON i.stable_key = a.item_stable_key
ORDER BY a.item_stable_key, a.acquisition_key;
