local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")

local Data = mw.loadData("Module:Erenshor/Data/Stances")

local p = {}

local FIELD_OVERRIDES = {
	["title"] = "name",
	["image"] = "image",
	["imagecaption"] = "imageCaption",
	["description"] = "description",
	["switch_message"] = "switchMessage",
	["max_hp_mod"] = "maxHpMod",
	["damage_mod"] = "damageMod",
	["damage_taken_mod"] = "damageTakenMod",
	["proc_rate_mod"] = "procRateMod",
	["aggro_gen_mod"] = "aggroGenMod",
	["spell_damage_mod"] = "spellDamageMod",
	["self_damage_per_attack"] = "selfDamagePerAttack",
	["self_damage_per_cast"] = "selfDamagePerCast",
	["lifesteal_amount"] = "lifestealAmount",
	["resonance_amount"] = "resonanceAmount",
	["stop_regen"] = "stopRegen",
	["activated_by"] = "activatedBy",
}

local ROOT_PUBLIC_PARAMETERS = {
	"title",
	"image",
	"imagecaption",
	"description",
	"switch_message",
	"max_hp_mod",
	"damage_mod",
	"damage_taken_mod",
	"proc_rate_mod",
	"aggro_gen_mod",
	"spell_damage_mod",
	"self_damage_per_attack",
	"self_damage_per_cast",
	"lifesteal_amount",
	"resonance_amount",
	"stop_regen",
	"activated_by",
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

-- Format a number without a trailing ".0" (4.0 -> "4", 1.5 -> "1.5").
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

-- Combat-modifier multiplier -> signed percentage. 1.0 means no change and
-- renders an em dash, matching the live Template:Stance <format> logic.
local function modifierPercent(value)
	local number = tonumber(value)
	if number == nil then
		return ""
	end
	if number == 1 then
		return "—"
	end
	local percent = math.floor((number - 1) * 100 + 0.5)
	if percent > 0 then
		return "+" .. percent .. "%"
	end
	return percent .. "%"
end

-- Lifesteal multiplier: 1.0 (no change) and 0 are hidden; otherwise a percent.
local function lifestealText(value)
	local number = tonumber(value)
	if number == nil or number == 0 or number == 1 then
		return ""
	end
	return numberText(number) .. "%"
end

local function selfDamageAttackText(value)
	local number = tonumber(value)
	if number == nil or number <= 0 then
		return ""
	end
	return numberText(number) .. "% max HP"
end

local function selfDamageCastText(value)
	local number = tonumber(value)
	if number == nil or number <= 0 then
		return ""
	end
	return numberText(number)
end

local function stopRegenText(value)
	if value == true or value == "1" or value == "yes" or value == "true" then
		return "Yes"
	end
	return ""
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
	switch_message = function(s)
		return s.switchMessage
	end,
	max_hp_mod = function(s)
		return modifierPercent(s.maxHpMod)
	end,
	damage_mod = function(s)
		return modifierPercent(s.damageMod)
	end,
	damage_taken_mod = function(s)
		return modifierPercent(s.damageTakenMod)
	end,
	proc_rate_mod = function(s)
		return modifierPercent(s.procRateMod)
	end,
	aggro_gen_mod = function(s)
		return modifierPercent(s.aggroGenMod)
	end,
	spell_damage_mod = function(s)
		return modifierPercent(s.spellDamageMod)
	end,
	resonance_amount = function(s)
		return modifierPercent(s.resonanceAmount)
	end,
	lifesteal_amount = function(s)
		return lifestealText(s.lifestealAmount)
	end,
	self_damage_per_attack = function(s)
		return selfDamageAttackText(s.selfDamagePerAttack)
	end,
	self_damage_per_cast = function(s)
		return selfDamageCastText(s.selfDamagePerCast)
	end,
	stop_regen = function(s)
		return stopRegenText(s.stopRegen)
	end,
	activated_by = function(s)
		return s.activatedBy
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
	if stableKey ~= nil and Data.stances[stableKey] ~= nil then
		return stableKey
	end
	return nil
end

local function applyRootOverrides(stance, args)
	for _, publicName in ipairs(ROOT_PUBLIC_PARAMETERS) do
		local fieldName = FIELD_OVERRIDES[publicName]
		if fieldName ~= nil and Args.has(args, publicName) then
			stance[fieldName] = Args.resolve(args, publicName, stance[fieldName])
		end
	end
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
	applyRootOverrides(stance, args)
	return stance
end

local function missingOutput(stance)
	return '<span class="erenshor-missing-data">Missing stance data: '
		.. Format.escape(stance.name)
		.. "</span>[[Category:Pages with missing Erenshor stance data]]"
end

function p.fieldValue(args, pageTitle, key)
	local stance = p.resolve(args, pageTitle)
	if stance.missing then
		return ""
	end
	local accessor = FIELD_ACCESSORS[key]
	if accessor == nil then
		error("Unknown Stance infobox field: " .. tostring(key))
	end
	local value = accessor(stance)
	if value == nil then
		return ""
	end
	return tostring(value)
end

function p.statusText(args, pageTitle)
	local stance = p.resolve(args, pageTitle)
	if stance.missing then
		return missingOutput(stance)
	end
	return ""
end

function p.field(frame)
	return p.fieldValue(templateArgs(frame), currentTitleText(), frame.args[1])
end

function p.status(frame)
	return p.statusText(templateArgs(frame), currentTitleText())
end

return p
