local Args = require("Module:Erenshor/Args")
local Link = require("Module:Erenshor/Link")
local Format = require("Module:Erenshor/Format")
local Tooltip = require("Module:Erenshor/Item/Tooltip")
local Cargo = require("Module:Erenshor/Cargo")

local Index = mw.loadData("Module:Erenshor/Data/Items")
local AbilityData = mw.loadData("Module:Erenshor/Data/AbilityLinks")
local SkillData = mw.loadData("Module:Erenshor/Data/Skills")
local SpellData = mw.loadData("Module:Erenshor/Data/Spells")

local p = {}

local FIELD_OVERRIDES = {
	armor = "armor",
	buy = "buyValue",
	buffgiven = "buffGiven",
	buffsource = "buffSource",
	casttime = "castTime",
	componentfor = "componentFor",
	cooldown = "cooldown",
	craftsource = "craftSource",
	classes = "classes",
	damage = "damage",
	delay = "weaponDelay",
	description = "description",
	effect = "effect",
	effects = "effects",
	image = "image",
	imagecaption = "imageCaption",
	ingredients = "ingredients",
	itemlevel = "itemLevel",
	manacost = "manaCost",
	othersource = "othersource",
	disposable = "disposable",
	dps = "dps",
	droprates = "dropRates",
	duration = "duration",
	guaranteeddrops = "guaranteedDrops",
	proceffect = "procEffect",
	produces = "produces",
	relic = "relic",
	questsource = "questSource",
	relatedquest = "relatedQuest",
	sell = "sellValue",
	slot = "slot",
	source = "source",
	title = "name",
	type = "type",
	taughtskill = "taughtSkill",
	taughtspell = "taughtSpell",
	skilltype = "skillType",
	spelltype = "spellType",
	vendorsource = "vendorSource",
	worneffect = "wornEffectOverride",
}

local ROOT_PUBLIC_PARAMETERS = {
	"title",
	"image",
	"imagecaption",
	"type",
	"slot",
	"itemlevel",
	"vendorsource",
	"source",
	"othersource",
	"questsource",
	"relatedquest",
	"craftsource",
	"componentfor",
	"relic",
	"classes",
	"effects",
	"damage",
	"delay",
	"dps",
	"casttime",
	"duration",
	"cooldown",
	"effect",
	"worneffect",
	"proceffect",
	"buffgiven",
	"taughtspell",
	"taughtskill",
	"spelltype",
	"skilltype",
	"manacost",
	"disposable",
	"produces",
	"ingredients",
	"description",
	"buy",
	"sell",
	"guaranteeddrops",
	"droprates",
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
	if
		value:match("%.[Pp][Nn][Gg]$")
		or value:match("%.[Jj][Pp][Gg]$")
		or value:match("%.[Jj][Pp][Ee][Gg]$")
	then
		return value
	end
	return value .. ".png"
end

local function itemForStableKey(stableKey)
	local shardName = Index.byKey[stableKey]
	if shardName == nil then
		return nil
	end
	local shard = mw.loadData("Module:Erenshor/Data/Items/" .. shardName)
	return shard[stableKey]
end

local function explicitStableKey(args)
	return Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
end

local function resolveStableKey(args)
	local stableKey = explicitStableKey(args)
	if stableKey ~= nil and itemForStableKey(stableKey) ~= nil then
		return stableKey
	end
	return nil
end

local function applyOverride(item, args, publicName, fieldName)
	if Args.has(args, publicName) then
		item[fieldName] = Args.resolve(args, publicName, item[fieldName])
	end
end

local function applyRootOverrides(item, args)
	for _, publicName in ipairs(ROOT_PUBLIC_PARAMETERS) do
		local fieldName = FIELD_OVERRIDES[publicName]
		if fieldName ~= nil then
			applyOverride(item, args, publicName, fieldName)
		end
	end

	if Args.has(args, "relic") then
		item.relic = Args.bool(args, "relic", item.relic)
	end
	if Args.has(args, "disposable") then
		item.disposable = Args.bool(args, "disposable", item.disposable)
	end
	if Args.has(args, "buy") then
		item.buyValue = Args.number(args, "buy", item.buyValue)
	end
	if Args.has(args, "sell") then
		item.sellValue = Args.number(args, "sell", item.sellValue)
	end
	if Args.has(args, "damage") then
		item.damage = Args.number(args, "damage", item.damage)
	end
	if Args.has(args, "armor") then
		item.armor = Args.number(args, "armor", item.armor)
	end
end

local function missingItem(args, pageTitle)
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
		return missingItem(args, pageTitle)
	end

	local item = copyTable(itemForStableKey(stableKey))
	item.stableKey = stableKey
	applyRootOverrides(item, args)
	return item
end

local function classText(classes)
	if classes == nil then
		return ""
	end
	if type(classes) == "table" then
		local links = {}
		for _, class in ipairs(classes) do
			if not isBlank(class) then
				table.insert(links, Link.render({ kind = "class", page = class }))
			end
		end
		return table.concat(links, " / ")
	end
	return tostring(classes)
end

local function classCargo(classes)
	if classes == nil then
		return ""
	end
	if type(classes) == "table" then
		return table.concat(classes, ",")
	end
	return tostring(classes)
end

local hasValue

local function normalStats(item)
	for _, stats in ipairs(item.stats or {}) do
		if stats.quality == "Normal" or stats.quality == "0" then
			return stats
		end
	end
	return (item.stats or {})[1] or {}
end

local function baseDps(item)
	local damage = tonumber(item.damage)
	local delay = tonumber(item.weaponDelay)
	if damage == nil or delay == nil then
		return nil
	end
	if delay == 0 then
		delay = 1
	end
	local dps = math.ceil(damage / delay)
	if item.weaponType == "TwoHandMelee" or item.weaponType == "TwoHandStaff" then
		dps = dps * 2
	end
	return dps
end

local function publicSkillType(skillType)
	if skillType == "Innate" then
		return "Passive"
	end
	return skillType
end

local function taughtSkillType(item)
	if hasValue(item.skillType) then
		return publicSkillType(item.skillType)
	end
	local skill = SkillData.skills[item.teachesSkill]
	if skill == nil then
		return nil
	end
	return publicSkillType(skill.type)
end

local function taughtSpellType(item)
	if hasValue(item.spellType) then
		return item.spellType
	end
	local spell = SpellData.spells[item.teachesSpell]
	if spell == nil then
		return nil
	end
	return spell.type
end
local function abilityPage(stableKey)
	if isBlank(stableKey) then
		return nil
	end
	local ability = AbilityData.abilities[stableKey]
	if ability == nil or isBlank(ability.page) then
		return nil
	end
	return ability.page
end

local function percent(value)
	local amount = tonumber(value)
	if amount == nil then
		return ""
	end
	return tostring(math.floor(amount))
end

local function weaponProcTrigger(item)
	-- Faithful to ItemInfoWindow.cs: shields proc on bash, bracers on cast,
	-- ordinary weapons on attack.
	if item.shield then
		return "on bash"
	end
	if item.slot == "Bracer" then
		return "on cast"
	end
	return "on attack"
end

local function procOverview(item)
	if hasValue(item.weaponProc) and hasValue(item.weaponProcChance) then
		return abilityPage(item.weaponProc), percent(item.weaponProcChance), weaponProcTrigger(item)
	end
	if hasValue(item.wandEffect) and hasValue(item.wandProcChance) then
		return abilityPage(item.wandEffect), percent(item.wandProcChance), "on attack"
	end
	if hasValue(item.bowEffect) and hasValue(item.bowProcChance) then
		return abilityPage(item.bowEffect), percent(item.bowProcChance), "on attack"
	end
	return nil, nil, nil
end

local function abilityLinkMarkup(page)
	if isBlank(page) then
		return ""
	end
	return Link.render({ kind = "ability", page = page })
end

local function abilityLinkFromStableKey(stableKey)
	return abilityLinkMarkup(abilityPage(stableKey))
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
		if type(value) == "table" and value.link ~= nil then
			local quantity = tonumber(value.quantity)
			local rendered = Link.render(value.link)
			if quantity ~= nil then
				table.insert(out, tostring(quantity) .. "x " .. rendered)
			else
				table.insert(out, rendered)
			end
		elseif type(value) == "table" and value.kind ~= nil then
			table.insert(out, Link.render(value))
		else
			table.insert(out, value)
		end
	end
	return table.concat(out, "<br>")
end

local function linkList(values)
	if type(values) ~= "table" then
		return values
	end
	return Link.join(values, "<br>")
end

local function probabilityList(values, decimals)
	if type(values) ~= "table" then
		return values
	end
	local out = {}
	for _, row in ipairs(values) do
		if type(row) == "table" and row.link ~= nil then
			local probability = tonumber(row.probability)
			if probability ~= nil then
				table.insert(
					out,
					Link.render(row.link)
						.. " ("
						.. string.format("%." .. decimals .. "f", probability)
						.. "%)"
				)
			end
		end
	end
	return table.concat(out, "<br>")
end

function p.overviewNotes(frame)
	-- The overview "Notes" cell coalesces an item's own proc/worn/click abilities
	-- at display time from the Lua data module; Cargo stores the scalar ability
	-- StableKeys (for reverse queries), never this rendered conflation.
	local item = itemForStableKey(explicitStableKey(templateArgs(frame)))
	if item == nil then
		return ""
	end
	local notes = {}
	local procPage, procChance, procTrigger = procOverview(item)
	if hasValue(procPage) then
		table.insert(
			notes,
			abilityLinkMarkup(procPage) .. ", " .. procChance .. "% " .. procTrigger
		)
	end
	if hasValue(item.wornEffect) then
		table.insert(notes, "Worn: " .. abilityLinkFromStableKey(item.wornEffect))
	end
	if hasValue(item.clickEffect) then
		table.insert(notes, "On click: " .. abilityLinkFromStableKey(item.clickEffect))
	end
	local text = table.concat(notes, "<br>")
	if frame ~= nil and frame.preprocess ~= nil then
		return frame:preprocess(text)
	end
	return text
end

local function boolText(value)
	if value == nil then
		return ""
	end
	if value then
		return "Yes"
	end
	return "No"
end

function hasValue(value)
	if type(value) == "boolean" then
		return value
	end
	return not isBlank(value)
end

local function missingOutput(item)
	return '<span class="erenshor-missing-data">Missing item data: '
		.. Format.escape(item.name)
		.. "</span>[[Category:Pages with missing Erenshor item data]]"
end

local FIELD_ACCESSORS = {
	name = function(i)
		return i.name
	end,
	image = function(i)
		return ensureImageFile(i.image, i.name)
	end,
	imagecaption = function(i)
		return i.imageCaption
	end,
	type = function(i)
		return i.type
	end,
	vendorsource = function(i)
		return linkList(i.vendorSource)
	end,
	source = function(i)
		return probabilityList(i.source, 1)
	end,
	othersource = function(i)
		return i.othersource
	end,
	questsource = function(i)
		return linkList(i.questSource)
	end,
	relatedquest = function(i)
		return linkList(i.relatedQuest)
	end,
	craftsource = function(i)
		return i.craftSource
	end,
	componentfor = function(i)
		return linkList(i.componentFor)
	end,
	relic = function(i)
		return i.relic == true and "Yes" or ""
	end,
	classes = function(i)
		return classText(i.classes)
	end,
	effects = function(i)
		return i.effects
	end,
	damage = function(i)
		return i.damage
	end,
	delay = function(i)
		return i.weaponDelay
	end,
	dps = baseDps,
	casttime = function(i)
		return i.castTime
	end,
	duration = function(i)
		return i.duration
	end,
	cooldown = function(i)
		return i.cooldown
	end,
	effect = function(i)
		if hasValue(i.effect) then
			return i.effect
		end
		return abilityLinkFromStableKey(i.clickEffect)
	end,
	worneffect = function(i)
		if hasValue(i.wornEffectOverride) then
			return i.wornEffectOverride
		end
		return abilityLinkFromStableKey(i.wornEffect)
	end,
	proceffect = function(i)
		if hasValue(i.procEffect) then
			return i.procEffect
		end
		return abilityLinkFromStableKey(i.weaponProc)
	end,
	buffgiven = function(i)
		return i.buffGiven
	end,
	taughtspell = function(i)
		if hasValue(i.taughtSpell) then
			return i.taughtSpell
		end
		return abilityLinkFromStableKey(i.teachesSpell)
	end,
	taughtskill = function(i)
		if hasValue(i.taughtSkill) then
			return i.taughtSkill
		end
		return abilityLinkFromStableKey(i.teachesSkill)
	end,
	spelltype = taughtSpellType,
	skilltype = taughtSkillType,
	manacost = function(i)
		return i.manaCost
	end,
	disposable = function(i)
		return i.disposable == true and "Yes" or ""
	end,
	produces = function(i)
		if hasValue(i.produces) then
			return i.produces
		end
		return lineList(i.rewards)
	end,
	ingredients = function(i)
		return lineList(i.ingredients)
	end,
	description = function(i)
		return i.description
	end,
	buy = function(i)
		return Format.currency(i.buyValue)
	end,
	sell = function(i)
		return Format.currency(i.sellValue)
	end,
	guaranteeddrops = function(i)
		return linkList(i.guaranteedDrops)
	end,
	droprates = function(i)
		return probabilityList(i.dropRates, 0)
	end,
}

function p.fieldValue(args, pageTitle, key)
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return ""
	end
	local accessor = FIELD_ACCESSORS[key]
	if accessor == nil then
		-- Overridable params without a display accessor (e.g. slot, itemlevel, title)
		-- still resolve to their generated data value so override review can detect
		-- article parameters that merely duplicate exported data.
		local overrideField = FIELD_OVERRIDES[key]
		if overrideField ~= nil then
			local raw = item[overrideField]
			if raw == nil then
				return ""
			end
			return tostring(raw)
		end
		error("Unknown Item infobox field: " .. tostring(key))
	end
	local value = accessor(item)
	if value == nil then
		return ""
	end
	return tostring(value)
end

function p.statusText(args, pageTitle)
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return missingOutput(item)
	end
	return ""
end

function p.renderTooltip(args, pageTitle)
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return missingOutput(item)
	end
	return Tooltip.render(item)
end

function p.renderLink(args, pageTitle)
	args = args or {}
	local out = {}
	for key, value in pairs(args) do
		out[key] = value
	end
	out.kind = "item"
	if
		Args.resolve(out, 1, nil) == nil
		and Args.resolve(out, "item", nil) == nil
		and Args.resolve(out, "name", nil) == nil
	then
		out[1] = pageTitle
	end
	return Link.render(out)
end

local function cargoFields(item, pageTitle)
	local stats = normalStats(item)
	return {
		{ "Page", pageTitle },
		{ "StableKey", item.stableKey },
		{ "Name", item.name },
		{ "Type", item.type },
		{ "Slot", item.slot },
		{ "WeaponType", item.weaponType },
		{ "ItemLevel", item.itemLevel },
		{ "Damage", item.damage },
		{ "Delay", item.weaponDelay },
		{ "Armor", item.armor },
		{ "HP", stats.hp },
		{ "Mana", stats.mana },
		{ "Str", stats.str },
		{ "End", stats["end"] },
		{ "Dex", stats.dex },
		{ "Agi", stats.agi },
		{ "Intellect", stats["int"] },
		{ "Wis", stats.wis },
		{ "Cha", stats.cha },
		{ "Res", stats.res },
		{ "MR", stats.mr },
		{ "PR", stats.pr },
		{ "ER", stats.er },
		{ "VR", stats.vr },
		{ "BuyValue", item.buyValue },
		{ "SellValue", item.sellValue },
		{ "Image", ensureImageFile(item.image, item.name) },
		{ "Classes", classCargo(item.classes) },
		{ "TeachesSpell", item.teachesSpell },
		{ "TeachesSkill", item.teachesSkill },
		{ "WeaponProc", item.weaponProc },
		{ "WeaponProcChance", item.weaponProcChance },
		{ "WandEffect", item.wandEffect },
		{ "WandProcChance", item.wandProcChance },
		{ "BowEffect", item.bowEffect },
		{ "BowProcChance", item.bowProcChance },
		{ "WornEffect", item.wornEffect },
		{ "ClickEffect", item.clickEffect },
		{ "SkillUse", item.skillUse },
		{ "Aura", item.aura },
		{ "Relic", item.relic },
		{ "HasProc", hasValue(item.weaponProc) or hasValue(item.procEffect) },
		{ "HasWornEffect", hasValue(item.wornEffect) },
	}
end

function p.field(frame)
	return p.fieldValue(templateArgs(frame), currentTitleText(), frame.args[1])
end

function p.classLinks(frame)
	local value = frame.args[1]
	if value == nil or isBlank(value) then
		return ""
	end
	local links = {}
	for class in string.gmatch(value, "[^,]+") do
		local trimmed = mw.text.trim(class)
		if not isBlank(trimmed) then
			table.insert(links, Link.render({ kind = "class", page = trimmed }))
		end
	end
	return table.concat(links, ", ")
end

function p.status(frame)
	return p.statusText(templateArgs(frame), currentTitleText())
end

function p.tooltip(frame)
	return p.renderTooltip(templateArgs(frame), currentTitleText())
end

function p.link(frame)
	return p.renderLink(templateArgs(frame), currentTitleText())
end

function p.cargoArgs(frame)
	local args = templateArgs(frame)
	local pageTitle = currentTitleText()
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return {}
	end
	return Cargo.buildArgs("Items", cargoFields(item, pageTitle))
end

function p.cargoStore(frame)
	local args = templateArgs(frame)
	local pageTitle = currentTitleText()
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return ""
	end
	return Cargo.store("Items", cargoFields(item, pageTitle))
end

return p
