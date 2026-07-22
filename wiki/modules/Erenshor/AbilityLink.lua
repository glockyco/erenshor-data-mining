local Args = require("Module:Erenshor/Args")
local Link = require("Module:Erenshor/Link")

local p = {}

local function copyTable(value)
	local out = {}
	if value == nil then
		return out
	end
	for key, item in pairs(value) do
		if type(item) == "table" then
			out[key] = copyTable(item)
		else
			out[key] = item
		end
	end
	return out
end

local function templateArgs(frame)
	local out = copyTable(Args.parentArgs(frame))
	if frame ~= nil and frame.args ~= nil then
		for key, value in pairs(frame.args) do
			out[key] = value
		end
	end
	return out
end

function p.resolve(args)
	return Link.resolve("ability", args or {})
end

function p.render(args)
	args = copyTable(args or {})
	args.kind = "ability"
	return Link.render(args)
end

function p.link(frame)
	return p.render(templateArgs(frame))
end

return p
