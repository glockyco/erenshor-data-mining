const MAPS_DATABASE_PATH_ENV = 'ERENSHOR_MAPS_DATABASE_PATH';

/**
 * The clean database that the build reads. `erenshor maps dev` and
 * `erenshor maps build` set it to the selected variant's database.
 */
export function getMapsDatabasePath(environment: NodeJS.ProcessEnv = process.env): string {
	const databasePath = environment[MAPS_DATABASE_PATH_ENV];
	if (!databasePath) {
		throw new Error(
			`${MAPS_DATABASE_PATH_ENV} is not set. Run the site through \`erenshor maps dev\` or \`erenshor maps build\`.`
		);
	}
	return databasePath;
}
