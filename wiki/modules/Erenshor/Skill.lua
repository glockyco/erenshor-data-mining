local AbilityLink = require("Module:Erenshor/AbilityLink")
local Args = require("Module:Erenshor/Args")
local Link = require("Module:Erenshor/Link")
local Format = require("Module:Erenshor/Format")
local Tooltip = require("Module:Erenshor/Skill/Tooltip")

local Data = mw.loadData("Module:Erenshor/Data/Skills")

local p = {}

local FIELD_OVERRIDES = {
	["title"] = "name",
	["image"] = "image",
	["imagecaption"] = "imageCaption",
	["description"] = "description",
	["type"] = "type",
	["classes"] = "classesOverride",
	["is_sim_usable"] = "simPlayersAutolearn",
	["range"] = "range",
	["is_self_only"] = "selfOnlyOverride",
	["is_group_effect"] = "aeSkill",
	["is_applied_to_caster"] = "affectPlayer",
	["effects"] = "effectsOverride",
	["damage_type"] = "damageType",
	["target_damage"] = "targetDamageOverride",
	["pet_to_summon"] = "petToSummonOverride",
	["special_descriptor"] = "specialDescriptorOverride",
	["source"] = "source",
	["itemswitheffect"] = "itemsWithEffect",
	["used_by"] = "usedBy",
	["casttime"] = "castTimeOverride",
	["cooldown"] = "cooldownOverride",
}

local ROOT_PUBLIC_PARAMETERS = {
	"title",
	"image",
	"imagecaption",
	"description",
	"type",
	"classes",
	"is_sim_usable",
	"range",
	"is_self_only",
	"is_group_effect",
	"is_applied_to_caster",
	"effects",
	"damage_type",
	"target_damage",
	"pet_to_summon",
	"special_descriptor",
	"source",
	"itemswitheffect",
	"used_by",
	"casttime",
	"cooldown",
}

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

local function ensureImageFile(image, fallbackName)
	local value = image
	if isBlank(value) then
		value = fallbackName
	end
	if isBlank(value) then
		return nil
	end
	value = tostring(value)
	if value:match("%.[Pp][Nn][Gg]$") or value:match("%.[Jj][Pp][Gg]$") then
		return value
	end
	return value .. ".png"
end

local function numberText(value)
	local number = tonumber(value)
	if number == nil then
		return tostring(value)
	end
	if number == math.floor(number) then
		return tostring(math.floor(number))
	end
	return tostring(number)
end

local function nonZeroNumberText(value)
	local number = tonumber(value)
	if number == nil or number == 0 then
		return ""
	end
	return numberText(number)
end

local function boolText(value)
	if value == true or value == "1" or value == "True" or value == "true" then
		return "True"
	end
	return ""
end

local function linkedAbility(stableKey)
	if isBlank(stableKey) then
		return ""
	end
	return AbilityLink.render({ stablekey = stableKey })
end

local function classLevelsText(skill)
	if not isBlank(skill.classesOverride) then
		return skill.classesOverride
	end
	if skill.classLevels == nil then
		return ""
	end
	local out = {}
	for _, entry in ipairs(skill.classLevels) do
		local displayName = entry.displayName or entry.className
		if
			not isBlank(displayName)
			and tonumber(entry.level) ~= nil
			and tonumber(entry.level) > 0
		then
			table.insert(
				out,
				Link.render({ kind = "class", page = displayName })
					.. " ("
					.. numberText(entry.level)
					.. ")"
			)
		end
	end
	return table.concat(out, "<br>")
end

local function equipmentText(skill)
	if not isBlank(skill.specialDescriptorOverride) then
		return skill.specialDescriptorOverride
	end
	local out = {}
	if skill.require2h then
		table.insert(out, "Two-handed weapon")
	end
	if skill.requireDw then
		table.insert(out, "Dual wield")
	end
	if skill.requireBow then
		table.insert(out, "Bow")
	end
	if skill.requireShield then
		table.insert(out, "Shield")
	end
	if skill.requireBehind then
		table.insert(out, "Behind target")
	end
	return table.concat(out, ", ")
end

local function effectsText(skill)
	if not isBlank(skill.effectsOverride) then
		return skill.effectsOverride
	end
	local out = {}
	local seen = {}
	local function add(value)
		if not isBlank(value) and seen[value] == nil then
			seen[value] = true
			table.insert(out, value)
		end
	end
	add(linkedAbility(skill.effectStableKey))
	add(linkedAbility(skill.stanceStableKey))
	add(linkedAbility(skill.castOnTargetStableKey))
	return table.concat(out, "<br>")
end

local function publicSkillType(skillType)
	if skillType == "Innate" then
		return "Passive"
	end
	return skillType
end

local function castTimeText(skill)
	if not isBlank(skill.castTimeOverride) then
		return skill.castTimeOverride
	end
	if skill.type ~= "Innate" then
		return "Instant"
	end
	return ""
end

local function cooldownText(skill)
	if not isBlank(skill.cooldownOverride) then
		return skill.cooldownOverride
	end
	local seconds = tonumber(skill.cooldownSeconds)
	if seconds == nil or seconds == 0 then
		return ""
	end
	return numberText(seconds) .. " seconds"
end

local function selfOnlyText(skill)
	if not isBlank(skill.selfOnlyOverride) then
		return skill.selfOnlyOverride
	end
	return boolText(skill.affectPlayer and not skill.affectTarget)
end

local function lineList(values)
	if values == nil then
		return nil
	end
	if type(values) ~= "table" then
		return values
	end
	local out = {}
	for _, value in ipairs(values) do
		if type(value) == "table" and value.kind ~= nil then
			table.insert(out, Link.render(value))
		else
			table.insert(out, value)
		end
	end
	return table.concat(out, "<br>")
end

local FIELD_ACCESSORS = {
	title = function(s)
		return s.name
	end,
	image = function(s)
		return ensureImageFile(s.image, s.name)
	end,
	imagecaption = function(s)
		return s.imageCaption
	end,
	description = function(s)
		return s.description
	end,
	type = function(s)
		return publicSkillType(s.type)
	end,
	classes = classLevelsText,
	is_sim_usable = function(s)
		return boolText(s.simPlayersAutolearn)
	end,
	range = function(s)
		return nonZeroNumberText(s.range)
	end,
	is_self_only = selfOnlyText,
	is_group_effect = function(s)
		return boolText(s.aeSkill)
	end,
	is_applied_to_caster = function(s)
		return boolText(s.affectPlayer)
	end,
	effects = effectsText,
	damage_type = function(s)
		if s.type ~= "Attack" then
			return ""
		end
		return s.damageType
	end,
	target_damage = function(s)
		if not isBlank(s.targetDamageOverride) then
			return s.targetDamageOverride
		end
		return nonZeroNumberText(s.skillPower)
	end,
	pet_to_summon = function(s)
		if not isBlank(s.petToSummonOverride) then
			return s.petToSummonOverride
		end
		return linkedAbility(s.spawnOnUseStableKey)
	end,
	special_descriptor = equipmentText,
	source = function(s)
		return lineList(s.source)
	end,
	itemswitheffect = function(s)
		return lineList(s.itemsWithEffect)
	end,
	used_by = function(s)
		return lineList(s.usedBy)
	end,
	casttime = castTimeText,
	cooldown = cooldownText,
}

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

local function applyRootOverrides(skill, args)
	for _, publicName in ipairs(ROOT_PUBLIC_PARAMETERS) do
		local fieldName = FIELD_OVERRIDES[publicName]
		if fieldName ~= nil and Args.has(args, publicName) then
			skill[fieldName] = Args.resolve(args, publicName, skill[fieldName])
		end
	end
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
	applyRootOverrides(skill, args)
	return skill
end

local function missingOutput(skill)
	return '<span class="erenshor-missing-data">Missing skill data: '
		.. Format.escape(skill.name)
		.. "</span>[[Category:Pages with missing Erenshor skill data]]"
end

function p.fieldValue(args, pageTitle, key)
	local skill = p.resolve(args, pageTitle)
	if skill.missing then
		return ""
	end
	local accessor = FIELD_ACCESSORS[key]
	if accessor == nil then
		return ""
	end
	local value = accessor(skill)
	if value == nil or value == false then
		return ""
	end
	return tostring(value)
end

function p.statusText(args, pageTitle)
	local skill = p.resolve(args, pageTitle)
	if skill.missing then
		return missingOutput(skill)
	end
	return ""
end

function p.field(frame)
	return p.fieldValue(templateArgs(frame), currentTitleText(), frame.args[1])
end

function p.status(frame)
	return p.statusText(templateArgs(frame), currentTitleText())
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

return p
