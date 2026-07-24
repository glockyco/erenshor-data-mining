local AbilityLink = require("Module:Erenshor/AbilityLink")
local Args = require("Module:Erenshor/Args")
local Link = require("Module:Erenshor/Link")
local Format = require("Module:Erenshor/Format")
local Tooltip = require("Module:Erenshor/Spell/Tooltip")
local Cargo = require("Module:Erenshor/Cargo")

local Data = mw.loadData("Module:Erenshor/Data/Spells")

local p = {}

local FIELD_OVERRIDES = {
	["title"] = "name",
	["image"] = "image",
	["imagecaption"] = "imageCaption",
	["description"] = "description",
	["type"] = "type",
	["line"] = "line",
	["classes"] = "classesOverride",
	["required_level"] = "requiredLevel",
	["manacost"] = "manaCost",
	["aggro"] = "aggro",
	["is_taunt"] = "taunt",
	["casttime"] = "castTimeOverride",
	["cooldown"] = "cooldownOverride",
	["duration"] = "durationOverride",
	["has_unstable_duration"] = "unstableDuration",
	["is_instant_effect"] = "instantEffect",
	["is_reap_and_renew"] = "reapAndRenew",
	["is_sim_usable"] = "simUsable",
	["range"] = "range",
	["max_level_target"] = "maxLevelTarget",
	["is_self_only"] = "selfOnly",
	["is_group_effect"] = "groupEffect",
	["is_applied_to_caster"] = "applyToCaster",
	["effects"] = "effects",
	["damage_type"] = "damageType",
	["resist_modifier"] = "resistModifier",
	["target_damage"] = "targetDamage",
	["target_healing"] = "targetHealing",
	["caster_healing"] = "casterHealing",
	["shield_amount"] = "shieldAmount",
	["pet_to_summon"] = "petToSummon",
	["status_effect"] = "statusEffectOverride",
	["add_proc"] = "addProcOverride",
	["add_proc_chance"] = "addProcChance",
	["has_lifetap"] = "lifetap",
	["lifesteal"] = "lifesteal",
	["damage_shield"] = "damageShield",
	["percent_mana_restoration"] = "percentManaRestoration",
	["bleed_damage_percent"] = "bleedDamagePercent",
	["special_descriptor"] = "specialDescriptor",
	["hp"] = "hp",
	["ac"] = "ac",
	["mana"] = "mana",
	["str"] = "str",
	["dex"] = "dex",
	["end"] = "end",
	["agi"] = "agi",
	["wis"] = "wis",
	["int"] = "int",
	["cha"] = "cha",
	["mr"] = "mr",
	["er"] = "er",
	["vr"] = "vr",
	["pr"] = "pr",
	["haste"] = "haste",
	["resonance"] = "resonance",
	["movement_speed"] = "movementSpeed",
	["atk_roll_modifier"] = "atkRollModifier",
	["xp_bonus"] = "xpBonus",
	["is_root"] = "root",
	["is_stun"] = "stun",
	["is_charm"] = "charm",
	["is_broken_on_damage"] = "breakOnDamage",
	["is_fear"] = "fear",
	["inflict_on_self"] = "inflictOnSelf",
	["itemswitheffect"] = "itemsWithEffect",
	["source"] = "source",
	["used_by"] = "usedBy",
}

local ROOT_PUBLIC_PARAMETERS = {
	"title",
	"image",
	"imagecaption",
	"description",
	"type",
	"line",
	"classes",
	"required_level",
	"manacost",
	"aggro",
	"is_taunt",
	"casttime",
	"cooldown",
	"duration",
	"has_unstable_duration",
	"is_instant_effect",
	"is_reap_and_renew",
	"is_sim_usable",
	"range",
	"max_level_target",
	"is_self_only",
	"is_group_effect",
	"is_applied_to_caster",
	"effects",
	"damage_type",
	"resist_modifier",
	"target_damage",
	"target_healing",
	"caster_healing",
	"shield_amount",
	"pet_to_summon",
	"status_effect",
	"add_proc",
	"add_proc_chance",
	"has_lifetap",
	"lifesteal",
	"damage_shield",
	"percent_mana_restoration",
	"bleed_damage_percent",
	"special_descriptor",
	"hp",
	"ac",
	"mana",
	"str",
	"dex",
	"end",
	"agi",
	"wis",
	"int",
	"cha",
	"mr",
	"er",
	"vr",
	"pr",
	"haste",
	"resonance",
	"movement_speed",
	"atk_roll_modifier",
	"xp_bonus",
	"is_root",
	"is_stun",
	"is_charm",
	"is_broken_on_damage",
	"is_fear",
	"inflict_on_self",
	"itemswitheffect",
	"source",
	"used_by",
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

local function secondsText(value)
	local number = tonumber(value)
	if number == nil or number == 0 then
		return ""
	end
	return numberText(number) .. " seconds"
end

local function castTimeText(spell)
	if not isBlank(spell.castTimeOverride) then
		return spell.castTimeOverride
	end
	local seconds = tonumber(spell.castTimeSeconds)
	if seconds == nil or seconds < 0.05 then
		return "Instant"
	end
	return string.format("%.1f seconds", seconds)
end

local function cooldownText(spell)
	if not isBlank(spell.cooldownOverride) then
		return spell.cooldownOverride
	end
	return secondsText(spell.cooldownSeconds)
end

local function durationText(spell)
	if not isBlank(spell.durationOverride) then
		return spell.durationOverride
	end
	local seconds = tonumber(spell.durationSeconds)
	if seconds == nil or seconds == 0 then
		return ""
	end
	return numberText(seconds) .. " seconds"
end

local function imageCaptionText(spell)
	if not isBlank(spell.imageCaption) then
		return spell.imageCaption
	end
	if isBlank(spell.statusEffectMessageOnPlayer) then
		return ""
	end
	return "You " .. tostring(spell.statusEffectMessageOnPlayer)
end

local function classesText(spell)
	if not isBlank(spell.classesOverride) then
		return spell.classesOverride
	end
	local level = tonumber(spell.requiredLevel)
	if level == nil or level <= 0 or spell.classes == nil then
		return ""
	end
	local out = {}
	local classLinks = spell.classLinks
	for index, className in ipairs(spell.classes) do
		if not isBlank(className) then
			local classLink = type(classLinks) == "table" and classLinks[index] or nil
			local args
			if type(classLink) == "table" and not isBlank(classLink.stablekey) then
				args = { kind = "class", stablekey = classLink.stablekey }
			else
				args = { kind = "class", page = className }
			end
			table.insert(out, Link.render(args) .. " (" .. numberText(level) .. ")")
		end
	end
	return table.concat(out, "<br>")
end

local function rangeText(spell)
	if spell.selfOnly == true then
		return ""
	end
	return nonZeroNumberText(spell.range)
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

local function linkedCharacter(stableKey)
	if isBlank(stableKey) then
		return ""
	end
	return Link.render({ kind = "character", stablekey = stableKey })
end

local function linkedSpell(stableKey)
	if isBlank(stableKey) or Data.spells[stableKey] == nil then
		return ""
	end
	return AbilityLink.render({ stablekey = stableKey })
end

local function statusEffectText(spell)
	if not isBlank(spell.statusEffectOverride) then
		return spell.statusEffectOverride
	end
	return linkedSpell(spell.statusEffectStableKey)
end

local function addProcText(spell)
	if not isBlank(spell.addProcOverride) then
		return spell.addProcOverride
	end
	return linkedSpell(spell.addProcStableKey)
end

local FIELD_ACCESSORS = {
	title = function(s)
		return s.name
	end,
	image = function(s)
		return ensureImageFile(s.image, s.name)
	end,
	imagecaption = imageCaptionText,
	description = function(s)
		return s.description
	end,
	type = function(s)
		return s.type
	end,
	line = function(s)
		return s.line
	end,
	classes = classesText,
	required_level = function(s)
		return nonZeroNumberText(s.requiredLevel)
	end,
	manacost = function(s)
		return nonZeroNumberText(s.manaCost)
	end,
	aggro = function(s)
		return nonZeroNumberText(s.aggro)
	end,
	is_taunt = function(s)
		return boolText(s.taunt)
	end,
	casttime = castTimeText,
	cooldown = cooldownText,
	duration = durationText,
	has_unstable_duration = function(s)
		return boolText(s.unstableDuration)
	end,
	is_instant_effect = function(s)
		return boolText(s.instantEffect)
	end,
	is_reap_and_renew = function(s)
		return boolText(s.reapAndRenew)
	end,
	is_sim_usable = function(s)
		return boolText(s.simUsable)
	end,
	range = rangeText,
	max_level_target = function(s)
		return nonZeroNumberText(s.maxLevelTarget)
	end,
	is_self_only = function(s)
		return boolText(s.selfOnly)
	end,
	is_group_effect = function(s)
		return boolText(s.groupEffect)
	end,
	is_applied_to_caster = function(s)
		return boolText(s.applyToCaster)
	end,
	effects = function(s)
		return s.effects
	end,
	damage_type = function(s)
		if tonumber(s.targetDamage) == nil or tonumber(s.targetDamage) == 0 then
			return ""
		end
		return s.damageType
	end,
	resist_modifier = function(s)
		return nonZeroNumberText(s.resistModifier)
	end,
	target_damage = function(s)
		return nonZeroNumberText(s.targetDamage)
	end,
	target_healing = function(s)
		return nonZeroNumberText(s.targetHealing)
	end,
	caster_healing = function(s)
		return nonZeroNumberText(s.casterHealing)
	end,
	shield_amount = function(s)
		return nonZeroNumberText(s.shieldAmount)
	end,
	pet_to_summon = function(s)
		if not isBlank(s.petToSummon) then
			return s.petToSummon
		end
		return linkedCharacter(s.petToSummonStableKey)
	end,
	status_effect = statusEffectText,
	add_proc = addProcText,
	add_proc_chance = function(s)
		return nonZeroNumberText(s.addProcChance)
	end,
	has_lifetap = function(s)
		return boolText(s.lifetap)
	end,
	lifesteal = function(s)
		return nonZeroNumberText(s.lifesteal)
	end,
	damage_shield = function(s)
		return nonZeroNumberText(s.damageShield)
	end,
	percent_mana_restoration = function(s)
		return nonZeroNumberText(s.percentManaRestoration)
	end,
	bleed_damage_percent = function(s)
		return nonZeroNumberText(s.bleedDamagePercent)
	end,
	special_descriptor = function(s)
		return s.specialDescriptor
	end,
	hp = function(s)
		return nonZeroNumberText(s.hp)
	end,
	ac = function(s)
		return nonZeroNumberText(s.ac)
	end,
	mana = function(s)
		return nonZeroNumberText(s.mana)
	end,
	str = function(s)
		return nonZeroNumberText(s.str)
	end,
	dex = function(s)
		return nonZeroNumberText(s.dex)
	end,
	["end"] = function(s)
		return nonZeroNumberText(s["end"])
	end,
	agi = function(s)
		return nonZeroNumberText(s.agi)
	end,
	wis = function(s)
		return nonZeroNumberText(s.wis)
	end,
	["int"] = function(s)
		return nonZeroNumberText(s["int"])
	end,
	cha = function(s)
		return nonZeroNumberText(s.cha)
	end,
	mr = function(s)
		return nonZeroNumberText(s.mr)
	end,
	er = function(s)
		return nonZeroNumberText(s.er)
	end,
	vr = function(s)
		return nonZeroNumberText(s.vr)
	end,
	pr = function(s)
		return nonZeroNumberText(s.pr)
	end,
	haste = function(s)
		return nonZeroNumberText(s.haste)
	end,
	resonance = function(s)
		return nonZeroNumberText(s.resonance)
	end,
	movement_speed = function(s)
		return nonZeroNumberText(s.movementSpeed)
	end,
	atk_roll_modifier = function(s)
		return nonZeroNumberText(s.atkRollModifier)
	end,
	xp_bonus = function(s)
		return nonZeroNumberText(s.xpBonus)
	end,
	is_root = function(s)
		return boolText(s.root)
	end,
	is_stun = function(s)
		return boolText(s.stun)
	end,
	is_charm = function(s)
		return boolText(s.charm)
	end,
	is_broken_on_damage = function(s)
		return boolText(s.breakOnDamage)
	end,
	is_fear = function(s)
		return boolText(s.fear)
	end,
	inflict_on_self = function(s)
		return boolText(s.inflictOnSelf)
	end,
	itemswitheffect = function(s)
		return lineList(s.itemsWithEffect)
	end,
	source = function(s)
		return lineList(s.source)
	end,
	used_by = function(s)
		return lineList(s.usedBy)
	end,
}

local function explicitStableKey(args)
	return Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
end

local function resolveStableKey(args)
	local stableKey = explicitStableKey(args)
	if stableKey ~= nil and Data.spells[stableKey] ~= nil then
		return stableKey
	end
	return nil
end

local function applyRootOverrides(spell, args)
	for _, publicName in ipairs(ROOT_PUBLIC_PARAMETERS) do
		local fieldName = FIELD_OVERRIDES[publicName]
		if fieldName ~= nil and Args.has(args, publicName) then
			spell[fieldName] = Args.resolve(args, publicName, spell[fieldName])
		end
	end
end

local function missingSpell(args, pageTitle)
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
		return missingSpell(args, pageTitle)
	end

	local spell = copyTable(Data.spells[stableKey])
	spell.stableKey = stableKey
	applyRootOverrides(spell, args)
	return spell
end

local function missingOutput(spell)
	return '<span class="erenshor-missing-data">Missing spell data: '
		.. Format.escape(spell.name)
		.. "</span>[[Category:Pages with missing Erenshor spell data]]"
end

function p.fieldValue(args, pageTitle, key)
	local spell = p.resolve(args, pageTitle)
	if spell.missing then
		return ""
	end
	local accessor = FIELD_ACCESSORS[key]
	if accessor == nil then
		return ""
	end
	local value = accessor(spell)
	if value == nil or value == false then
		return ""
	end
	return tostring(value)
end

function p.statusText(args, pageTitle)
	local spell = p.resolve(args, pageTitle)
	if spell.missing then
		return missingOutput(spell)
	end
	return ""
end

local function cargoFields(spell, pageTitle)
	return {
		{ "StableKey", spell.stableKey },
		{ "Page", pageTitle },
		{ "Name", spell.name },
		{ "Image", ensureImageFile(spell.image, spell.name) },
		{ "Type", spell.type },
		{ "Line", spell.line },
		{ "RequiredLevel", spell.requiredLevel },
		{ "ManaCost", spell.manaCost },
		{ "CastTimeSeconds", spell.castTimeSeconds },
		{ "CooldownSeconds", spell.cooldownSeconds },
		{ "DurationSeconds", spell.durationSeconds },
		{ "CastRange", spell.range },
		{ "DamageType", spell.damageType },
		{ "TargetDamage", spell.targetDamage },
		{ "TargetHealing", spell.targetHealing },
		{ "CasterHealing", spell.casterHealing },
		{ "ShieldingAmt", spell.shieldAmount },
		{ "Aggro", spell.aggro },
		{ "SimUsable", spell.simUsable },
		{ "SimsNeedHelpToLearn", spell.simsNeedHelpToLearn },
		{ "SelfOnly", spell.selfOnly },
		{ "GroupEffect", spell.groupEffect },
		{ "CrowdControl", spell.crowdControl },
		{ "GrantInvisibility", spell.grantInvisibility },
		{ "CannotInterrupt", spell.cannotInterrupt },
		{ "Jolt", spell.jolt },
		{ "NoResonate", spell.noResonate },
		{ "ArmorPenPercent", spell.armorPenPercent },
		{ "LevelScaledManaRestoration", spell.levelScaledManaRestoration },
		{ "ShapeshiftForm", spell.shapeshiftForm },
		{ "StatusEffectKey", spell.statusEffectStableKey },
		{ "AddProcKey", spell.addProcStableKey },
		{ "PetToSummonKey", spell.petToSummonStableKey },
	}
end

local function classFields(spell, className)
	return {
		{ "AbilityKey", spell.stableKey },
		{ "Class", className },
		{ "RequiredLevel", spell.requiredLevel },
	}
end

-- A spell's classes are a flat name list; each becomes one AbilityClasses row that
-- broadcasts the spell's single requiredLevel.
local function eachClass(spell, callback)
	if type(spell.classes) ~= "table" then
		return
	end
	for _, className in ipairs(spell.classes) do
		if not isBlank(className) then
			callback(className)
		end
	end
end

function p.field(frame)
	return p.fieldValue(templateArgs(frame), currentTitleText(), frame.args[1])
end

function p.status(frame)
	return p.statusText(templateArgs(frame), currentTitleText())
end

function p.cargoArgs(frame)
	local pageTitle = currentTitleText()
	local spell = p.resolve(templateArgs(frame), pageTitle)
	if spell.missing then
		return {}
	end
	return Cargo.buildArgs("Spells", cargoFields(spell, pageTitle))
end

function p.cargoClassRows(frame)
	local spell = p.resolve(templateArgs(frame), currentTitleText())
	local rows = {}
	if not spell.missing then
		eachClass(spell, function(className)
			table.insert(rows, Cargo.buildArgs("AbilityClasses", classFields(spell, className)))
		end)
	end
	return rows
end

function p.cargoStore(frame)
	local pageTitle = currentTitleText()
	local spell = p.resolve(templateArgs(frame), pageTitle)
	if spell.missing then
		return ""
	end
	Cargo.store("Spells", cargoFields(spell, pageTitle))
	eachClass(spell, function(className)
		Cargo.store("AbilityClasses", classFields(spell, className))
	end)
	return ""
end

function p.renderTooltip(args, pageTitle)
	local spell = p.resolve(args, pageTitle)
	if spell.missing then
		return missingOutput(spell)
	end
	return Tooltip.render(spell)
end

function p.tooltip(frame)
	return p.renderTooltip(templateArgs(frame), currentTitleText())
end

function p.renderPageTooltip(args, pageTitle)
	local spell = p.resolve(args, pageTitle)
	if spell.missing then
		return ""
	end
	return Tooltip.render(spell)
end

function p.pageTooltip(frame)
	return p.renderPageTooltip(templateArgs(frame), currentTitleText())
end

return p
