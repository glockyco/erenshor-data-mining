local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Tooltip = require("Module:Erenshor/Item/Tooltip")

local Index = mw.loadData("Module:Erenshor/Data/Items")
local AbilityData = mw.loadData("Module:Erenshor/Data/AbilityLinks")

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
	worneffect = "wornEffect",
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
		return Format.classList(classes)
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

local function classOverviewLinks(classes)
	if classes == nil then
		return ""
	end
	if type(classes) ~= "table" then
		return tostring(classes)
	end

	local links = {}
	for _, class in ipairs(classes) do
		if not isBlank(class) then
			table.insert(links, Format.pageLink(class))
		end
	end
	return table.concat(links, ", ")
end

local function normalStats(item)
	for _, stats in ipairs(item.stats or {}) do
		if stats.quality == "Normal" or stats.quality == "0" then
			return stats
		end
	end
	return (item.stats or {})[1] or {}
end

local function abilityPageLink(stableKey)
	if isBlank(stableKey) then
		return ""
	end
	local ability = AbilityData.abilities[stableKey]
	if ability == nil or isBlank(ability.page) then
		return Format.escape(stableKey)
	end
	return Format.pageLink(ability.page)
end

local function percent(value)
	local amount = tonumber(value)
	if amount == nil then
		return ""
	end
	return tostring(math.floor(amount))
end

local function overviewNotes(item)
	local notes = {}
	if hasValue(item.weaponProc) and hasValue(item.weaponProcChance) then
		local trigger = "on attack"
		if item.shield then
			trigger = "on bash"
		end
		table.insert(
			notes,
			abilityPageLink(item.weaponProc)
				.. ", "
				.. percent(item.weaponProcChance)
				.. "% "
				.. trigger
		)
	end
	if hasValue(item.wandEffect) and hasValue(item.wandProcChance) then
		table.insert(
			notes,
			abilityPageLink(item.wandEffect) .. ", " .. percent(item.wandProcChance) .. "% on cast"
		)
	end
	if hasValue(item.bowEffect) and hasValue(item.bowProcChance) then
		table.insert(
			notes,
			abilityPageLink(item.bowEffect) .. ", " .. percent(item.bowProcChance) .. "% on attack"
		)
	end
	if hasValue(item.wornEffect) then
		table.insert(notes, "Worn: " .. abilityPageLink(item.wornEffect))
	end
	if hasValue(item.clickEffect) then
		table.insert(notes, "On click: " .. abilityPageLink(item.clickEffect))
	end
	return table.concat(notes, "<br>")
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
		return i.vendorSource
	end,
	source = function(i)
		return i.source
	end,
	othersource = function(i)
		return i.othersource
	end,
	questsource = function(i)
		return i.questSource
	end,
	relatedquest = function(i)
		return i.relatedQuest
	end,
	craftsource = function(i)
		return i.craftSource
	end,
	componentfor = function(i)
		return i.componentFor
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
	dps = function(i)
		return i.dps
	end,
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
		return i.effect
	end,
	worneffect = function(i)
		return i.wornEffect
	end,
	proceffect = function(i)
		return i.procEffect
	end,
	buffgiven = function(i)
		return i.buffGiven
	end,
	taughtspell = function(i)
		return i.taughtSpell
	end,
	taughtskill = function(i)
		return i.taughtSkill
	end,
	spelltype = function(i)
		return i.spellType
	end,
	skilltype = function(i)
		return i.skillType
	end,
	manacost = function(i)
		return i.manaCost
	end,
	disposable = function(i)
		return i.disposable == true and "Yes" or ""
	end,
	produces = function(i)
		return i.produces
	end,
	ingredients = function(i)
		return i.ingredients
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
		return i.guaranteedDrops
	end,
	droprates = function(i)
		return i.dropRates
	end,
}

function p.fieldValue(args, pageTitle, key)
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return ""
	end
	local accessor = FIELD_ACCESSORS[key]
	if accessor == nil then
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
	local itemName = Args.resolve(args, "item", nil)
		or Args.resolve(args, "name", nil)
		or Args.resolve(args, 1, nil)
		or pageTitle
	local item = nil
	local stableKey = explicitStableKey(args)
	if stableKey ~= nil then
		item = p.resolve(args, pageTitle)
		if item.missing then
			item = nil
		end
	end
	local link = Args.resolve(args, "link", nil) or (item and item.page) or itemName
	local text = Args.resolve(args, "text", nil) or (item and item.name) or itemName
	local image = Args.resolve(args, "image", nil) or (item and item.image) or itemName
	local imageLink =
		Format.fileLink(ensureImageFile(image, text), { alt = text, size = "24x24px" })

	if Args.bool(args, "imageonly", false) then
		return imageLink
	end
	return imageLink .. " " .. Format.pageLink(link, text)
end

local function cargoValue(value)
	if value == nil then
		return ""
	end
	if type(value) == "boolean" then
		if value then
			return "yes"
		end
		return "no"
	end
	return tostring(value):gsub("|", "&#124;"):gsub("\n", " ")
end

local function cargoStoreText(item, pageTitle)
	local stats = normalStats(item)
	local fields = {
		{ "_table", "Items" },
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
		{ "ClassLinks", classOverviewLinks(item.classes) },
		{ "OverviewNotes", overviewNotes(item) },
		{ "Relic", item.relic },
		{ "HasProc", hasValue(item.weaponProc) or hasValue(item.procEffect) },
		{ "HasWornEffect", hasValue(item.wornEffect) },
	}
	local out = { "{{#cargo_store:" }
	for _, field in ipairs(fields) do
		table.insert(out, "|" .. field[1] .. "=" .. cargoValue(field[2]))
	end
	table.insert(out, "}}")
	return table.concat(out)
end

function p.field(frame)
	return p.fieldValue(templateArgs(frame), currentTitleText(), frame.args[1])
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

function p.cargoStore(frame)
	local args = templateArgs(frame)
	local pageTitle = currentTitleText()
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return ""
	end
	local text = cargoStoreText(item, pageTitle)
	if frame ~= nil and frame.preprocess ~= nil then
		return frame:preprocess(text)
	end
	return text
end

return p
