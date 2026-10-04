local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local SkillTooltip = require("Module:Erenshor/Skill/Tooltip")

local Data = mw.loadData("Module:Erenshor/Data/Stances")
local SkillData = mw.loadData("Module:Erenshor/Data/Skills")

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

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
end

local skillsByStance = nil

local function skillsForStance(stanceStableKey)
	if skillsByStance == nil then
		skillsByStance = {}
		for skillStableKey, skill in pairs(SkillData.skills) do
			if not isBlank(skill.stanceStableKey) then
				if skillsByStance[skill.stanceStableKey] == nil then
					skillsByStance[skill.stanceStableKey] = {}
				end
				table.insert(skillsByStance[skill.stanceStableKey], skillStableKey)
			end
		end
		for _, skillKeys in pairs(skillsByStance) do
			table.sort(skillKeys)
		end
	end
	return skillsByStance[stanceStableKey] or {}
end

local function explicitStableKey(args)
	return Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
end

local function resolveStableKey(args)
	local stableKey = explicitStableKey(args)
	if stableKey ~= nil and Data.stances[stableKey] ~= nil then
		return stableKey
	end
	return nil
end

local function missingStance(args, pageTitle)
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
		return missingStance(args, pageTitle)
	end

	local stance = copyTable(Data.stances[stableKey])
	stance.stableKey = stableKey
	return stance
end

local function missingOutput(stance)
	return '<span class="erenshor-missing-data">Missing stance data: '
		.. Format.escape(stance.name)
		.. "</span>[[Category:Pages with missing Erenshor stance data]]"
end

local function tooltipSkill(stance)
	local skillKeys = skillsForStance(stance.stableKey)
	local skill = nil
	if #skillKeys > 0 then
		local skillStableKey = skillKeys[1]
		local source = SkillData.skills[skillStableKey]
		if source ~= nil then
			skill = copyTable(source)
			skill.stableKey = skillStableKey
		end
	end
	if skill == nil then
		skill = {
			name = stance.name,
			type = "Utility",
			stanceStableKey = stance.stableKey,
		}
	end
	return skill
end

function p.renderTooltip(args, pageTitle)
	local stance = p.resolve(args, pageTitle)
	if stance.missing then
		return missingOutput(stance)
	end
	return SkillTooltip.render(tooltipSkill(stance), {
		kind = "stance",
		stableKey = stance.stableKey,
	})
end

function p.tooltip(frame)
	return p.renderTooltip(templateArgs(frame), currentTitleText())
end

function p.renderPageTooltip(args, pageTitle)
	local stance = p.resolve(args, pageTitle)
	if stance.missing then
		return ""
	end
	return SkillTooltip.render(tooltipSkill(stance), {
		kind = "stance",
		stableKey = stance.stableKey,
	})
end

function p.pageTooltip(frame)
	return p.renderPageTooltip(templateArgs(frame), currentTitleText())
end

return p
