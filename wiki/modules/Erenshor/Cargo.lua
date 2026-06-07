-- Module:Erenshor/Cargo
--
-- Centralized Cargo row storage for the Erenshor entity modules.
--
-- wiki.gg disables the native Lua `mw.ext.cargo.store`/`declare`, so rows are written
-- through the `#cargo_store` parser function via `frame:callParserFunction`. Passing
-- every value as a discrete named argument means Cargo receives field values verbatim:
-- no manual escaping of `|`, `=`, newlines, or `{{ }}`/`[[ ]]`, and no re-parse of
-- values as wikitext (which `frame:preprocess` of a hand-built string would do).
--   * Native Lua store disabled: https://support.wiki.gg/wiki/Cargo/troubleshooting
--   * Production pattern:        https://www.poewiki.net/wiki/Module:Cargo
--
-- A page may store any number of rows across any number of tables: call `store` once
-- per row (loop for junction rows). Registering those tables for Cargo's
-- recreate-discovery is the template's job, not this module's: the template
-- `#cargo_declare`s the table it owns and `#cargo_attach`es the rest — directly, or via
-- a zero-output attach-only helper template (the "attach trick") when it writes more
-- than two tables. https://support.wiki.gg/wiki/Cargo/attaching_tables

local Cargo = {}

-- Cast one Lua value to the string Cargo expects.
--  * nil      -> nil   (the field is omitted from the row)
--  * boolean  -> "yes"/"no" (accepted by Cargo `Boolean` columns)
--  * other    -> tostring(value)
local function cast(value)
	if value == nil then
		return nil
	end
	if type(value) == "boolean" then
		if value then
			return "yes"
		end
		return "no"
	end
	return tostring(value)
end

-- Build the cast `{ _table = …, Field = value, … }` argument map for one row (pure).
--
-- `fields` is an ordered list of `{ name, value }` pairs; nil-valued fields are
-- omitted (stored as NULL, which queries back as ""), booleans become "yes"/"no".
-- Exposed so callers can unit-test the exact values a row will store without storing.
function Cargo.buildArgs(tableName, fields)
	local args = { ["_table"] = tableName }
	for _, field in ipairs(fields) do
		local value = cast(field[2])
		if value ~= nil then
			args[field[1]] = value
		end
	end
	return args
end

-- Store one row in Cargo table `tableName` (side-effect). `fields` is as in buildArgs.
-- Returns the parser-function result (empty for `#cargo_store`), so callers can return
-- it straight from a `{{#invoke:…|cargoStore}}` entry point.
function Cargo.store(tableName, fields)
	return mw.getCurrentFrame()
		:callParserFunction("#cargo_store:", Cargo.buildArgs(tableName, fields))
end

return Cargo
