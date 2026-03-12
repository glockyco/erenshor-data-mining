SELECT
    z.scene_name,
    z.zone_name,
    ROUND(ww.x, 2) AS position_x,
    ROUND(ww.y, 2) AS position_y,
    ROUND(ww.z, 2) AS position_z,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || ww.stable_key AS MapLink
FROM wishing_wells ww
JOIN zones z ON z.scene_name = ww.scene
ORDER BY z.zone_name;
