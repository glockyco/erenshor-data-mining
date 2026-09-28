## REMOVED Requirements

### Requirement: Commands restore mutable state that they replace

**Reason**: The only command that temporarily replaced repository state was `maps dev`, which linked the clean database into `src/maps/static/db/`. After this change, `maps dev` and `maps build` pass the database path through `ERENSHOR_MAPS_DATABASE_PATH`, a prerendered route publishes the database, and no command changes files in the repository.

**Migration**: Delete a stale `src/maps/static/db/erenshor.sqlite` link from an earlier version. The `map-site-data` capability makes `maps build` fail and name that path until it is deleted.
