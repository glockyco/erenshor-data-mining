import { beforeAll } from 'vitest';
import fs from 'fs';
import path from 'path';

const DB_SYMLINK_PATH = path.resolve('static/db/erenshor.sqlite');
const VARIANT_DB_PATH = path.resolve('../../variants/main/erenshor-main.sqlite');

// Ensure the runtime DB symlink exists for tests. Vitest isolates each test
// file into its own worker, so multiple DB-using files would previously race on
// creating/removing this shared symlink (EEXIST). This is now idempotent: if a
// resolvable symlink/file already exists we leave it untouched; otherwise we
// (best-effort) replace a dangling link and create it, tolerating a concurrent
// creation. We intentionally do not remove it afterward — it is the normal
// runtime artifact the app expects to be present.
beforeAll(() => {
	fs.mkdirSync(path.dirname(DB_SYMLINK_PATH), { recursive: true });

	// existsSync follows the symlink: true only if it resolves to a real file.
	if (fs.existsSync(DB_SYMLINK_PATH)) return;

	// Remove a dangling symlink if one is present, then create a fresh one.
	try {
		fs.lstatSync(DB_SYMLINK_PATH);
		fs.unlinkSync(DB_SYMLINK_PATH);
	} catch {
		// nothing at the path — fine
	}

	try {
		fs.symlinkSync(VARIANT_DB_PATH, DB_SYMLINK_PATH);
	} catch (err) {
		if ((err as NodeJS.ErrnoException).code !== 'EEXIST') throw err;
	}
});
