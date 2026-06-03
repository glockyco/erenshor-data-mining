local p = {}

local TRUE_VALUES = {
	["1"] = true,
	["true"] = true,
	["yes"] = true,
	["y"] = true,
	["on"] = true,
}

local FALSE_VALUES = {
	["0"] = false,
	["false"] = false,
	["no"] = false,
	["n"] = false,
	["off"] = false,
}

function p.trim(value)
	if value == nil then
		return nil
	end

	return tostring(value):match("^%s*(.-)%s*$")
end

function p.isBlank(value)
	local trimmed = p.trim(value)
	return trimmed == nil or trimmed == ""
end

function p.has(args, name)
	return args ~= nil and args[name] ~= nil
end

function p.parentArgs(frame)
	if frame == nil then
		return {}
	end

	local parent = nil
	if type(frame.getParent) == "function" then
		parent = frame:getParent()
	end

	if parent ~= nil then
		return parent.args or {}
	end

	return frame.args or {}
end

function p.resolve(args, name, default, options)
	if not p.has(args, name) then
		return default
	end

	local value = p.trim(args[name])
	if value == "" then
		if options ~= nil and options.blankOverrides == true then
			return ""
		end
		return default
	end

	if value == "-" and (options == nil or options.dashBlank ~= false) then
		return nil
	end

	return value
end

function p.bool(args, name, default, options)
	local value = p.resolve(args, name, default, options)
	if value == nil or type(value) == "boolean" then
		return value
	end

	local normalized = string.lower(tostring(value))
	if TRUE_VALUES[normalized] ~= nil then
		return TRUE_VALUES[normalized]
	end
	if FALSE_VALUES[normalized] ~= nil then
		return FALSE_VALUES[normalized]
	end

	error(string.format("Parameter '%s' must be a boolean value", name), 2)
end

function p.number(args, name, default, options)
	local value = p.resolve(args, name, default, options)
	if value == nil or type(value) == "number" then
		return value
	end

	local parsed = tonumber(value)
	if parsed == nil then
		error(string.format("Parameter '%s' must be numeric", name), 2)
	end

	return parsed
end

return p
