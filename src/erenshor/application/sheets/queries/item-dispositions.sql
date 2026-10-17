SELECT d.*, i.display_name AS item_name
FROM item_dispositions d
LEFT JOIN items i ON i.stable_key = d.item_stable_key
ORDER BY d.item_stable_key;
