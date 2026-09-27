## REMOVED Requirements

### Requirement: Commands restore mutable state that they replace

**Reason**: The only command that temporarily replaced repository state was `maps dev`, which linked the clean database into `src/maps/static/db/`. After this change, `maps dev` and `maps build` pass the database path through `ERENSHOR_MAPS_DATABASE_PATH` and do not change files in the repository.

**Migration**: None is necessary. The `map-site-data` capability requires that `maps build` and `maps dev` leave the maps source directory unchanged. A stale `src/maps/static/db/erenshor.sqlite` link from an earlier version has no effect and can be deleted.
