-- A mechanism's rows hold the conditions that every fact naming it in mechanic shares.
SELECT 'acquisition' AS fact_type, c.* FROM item_acquisition_conditions c
UNION ALL
SELECT 'use' AS fact_type, c.* FROM item_use_conditions c
UNION ALL
SELECT 'mechanism' AS fact_type, c.* FROM item_mechanic_conditions c
ORDER BY fact_type, owner_key, gate_key, group_index, atom_index, scope;
