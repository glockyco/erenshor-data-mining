import { beforeAll, afterAll } from 'vitest';
import fs from 'fs';
import path from 'path';

const DB_SYMLINK_PATH = path.resolve('static/db/erenshor.sqlite');
const VARIANT_DB_PATH = path.resolve('../../variants/main/erenshor-main.sqlite');

beforeAll(() => {
	// Create symlink to variant database for tests
	// Remove existing file/symlink if present
	if (fs.existsSync(DB_SYMLINK_PATH)) {
		fs.unlinkSync(DB_SYMLINK_PATH);
	}

	// Ensure directory exists
	const dbDir = path.dirname(DB_SYMLINK_PATH);
	if (!fs.existsSync(dbDir)) {
		fs.mkdirSync(dbDir, { recursive: true });
	}

	// Create symlink to variant database
	fs.symlinkSync(VARIANT_DB_PATH, DB_SYMLINK_PATH);
	console.log(`Created symlink: ${DB_SYMLINK_PATH} -> ${VARIANT_DB_PATH}`);
});

afterAll(() => {
	// Clean up symlink after tests
	if (fs.existsSync(DB_SYMLINK_PATH) && fs.lstatSync(DB_SYMLINK_PATH).isSymbolicLink()) {
		fs.unlinkSync(DB_SYMLINK_PATH);
		console.log(`Removed symlink: ${DB_SYMLINK_PATH}`);
	}
});
