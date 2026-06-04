local Args = require("Module:Erenshor/Args")
local Skill = require("Module:Erenshor/Skill")
local Spell = require("Module:Erenshor/Spell")

local p = {}

local function copyTable(value)
	local out = {}
	if value == nil then
		return out
	end
	for key, item in pairs(value) do
		out[key] = item
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

local function currentTitleText()
	if mw ~= nil and mw.title ~= nil and mw.title.getCurrentTitle ~= nil then
		return mw.title.getCurrentTitle().text
	end
	return ""
end

local function stableKey(args)
	return Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
end

local function moduleFor(args)
	local key = stableKey(args)
	if key ~= nil and tostring(key):match("^skill:") then
		return Skill
	end
	return Spell
end

function p.fieldValue(args, pageTitle, key)
	return moduleFor(args).fieldValue(args, pageTitle, key)
end

function p.statusText(args, pageTitle)
	return moduleFor(args).statusText(args, pageTitle)
end

function p.field(frame)
	local args = templateArgs(frame)
	return p.fieldValue(args, currentTitleText(), frame.args[1])
end

function p.status(frame)
	local args = templateArgs(frame)
	return p.statusText(args, currentTitleText())
end

return p
