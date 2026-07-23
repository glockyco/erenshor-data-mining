const DEFAULT_MAPS_DATABASE_PATH = 'static/db/erenshor.sqlite';
const MAPS_DATABASE_PATH_ENV = 'ERENSHOR_MAPS_DATABASE_PATH';

export function getMapsDatabasePath(
	environment: NodeJS.ProcessEnv = process.env
): string {
	return environment[MAPS_DATABASE_PATH_ENV] ?? DEFAULT_MAPS_DATABASE_PATH;
}
