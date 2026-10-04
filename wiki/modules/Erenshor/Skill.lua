local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Tooltip = require("Module:Erenshor/Skill/Tooltip")

local Data = mw.loadData("Module:Erenshor/Data/Skills")

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

local function currentTitleText()
	if mw ~= nil and mw.title ~= nil and mw.title.getCurrentTitle ~= nil then
		return mw.title.getCurrentTitle().text
	end
	return ""
end

local function explicitStableKey(args)
	return Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
end

local function resolveStableKey(args)
	local stableKey = explicitStableKey(args)
	if stableKey ~= nil and Data.skills[stableKey] ~= nil then
		return stableKey
	end
	return nil
end

local function missingSkill(args, pageTitle)
	return {
		missing = true,
		name = Args.resolve(args, "title", pageTitle) or pageTitle,
		page = pageTitle,
	}
end

function p.resolve(args, pageTitle)
	args = args or {}
	pageTitle = pageTitle or currentTitleText()

	local stableKey = resolveStableKey(args)
	if stableKey == nil then
		return missingSkill(args, pageTitle)
	end

	local skill = copyTable(Data.skills[stableKey])
	skill.stableKey = stableKey
	return skill
end

local function missingOutput(skill)
	return '<span class="erenshor-missing-data">Missing skill data: '
		.. Format.escape(skill.name)
		.. "</span>[[Category:Pages with missing Erenshor skill data]]"
end

function p.renderTooltip(args, pageTitle)
	local skill = p.resolve(args, pageTitle)
	if skill.missing then
		return missingOutput(skill)
	end
	return Tooltip.render(skill)
end

function p.tooltip(frame)
	return p.renderTooltip(templateArgs(frame), currentTitleText())
end

function p.renderPageTooltip(args, pageTitle)
	local skill = p.resolve(args, pageTitle)
	if skill.missing then
		return ""
	end
	return Tooltip.render(skill)
end

function p.pageTooltip(frame)
	return p.renderPageTooltip(templateArgs(frame), currentTitleText())
end

return p
