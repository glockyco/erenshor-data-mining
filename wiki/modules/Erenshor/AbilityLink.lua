local Args = require("Module:Erenshor/Args")
local Link = require("Module:Erenshor/Link")

local Data = mw.loadData("Module:Erenshor/Data/AbilityLinks")

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
	args = args or {}
	local target = Args.resolve(args, 1, nil)
	local stableKey = Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
	local ability = nil
	if stableKey ~= nil then
		ability = copyTable(Data.abilities[stableKey])
	end
	if ability == nil then
		ability = {
			name = target,
			page = target,
			image = target,
		}
	end

	ability.page = Args.resolve(args, "link", ability.page)
	ability.name = Args.resolve(args, "text", ability.name)
	ability.image = Args.resolve(args, "image", ability.image)
	return ability
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
