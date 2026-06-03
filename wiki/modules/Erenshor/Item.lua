local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Render = require("Module:Erenshor/Render")

local Index = mw.loadData("Module:Erenshor/Data/Items")

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

local function boolText(value)
	if value == nil then
		return ""
	end
	if value then
		return "Yes"
	end
	return "No"
end

local function hasValue(value)
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

function p.renderInfobox(args, pageTitle)
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return missingOutput(item)
	end

	local rows = {
		{
			label = "Image",
			value = Format.fileLink(
				ensureImageFile(item.image, item.name),
				{ alt = item.name, size = "64x64px" }
			),
		},
		{ label = "Caption", value = item.imageCaption },
		{ label = "Type", value = item.type },
		{ label = "Slot", value = item.slot },
		{ label = "Item level", value = item.itemLevel },
		{ label = "Damage", value = item.damage },
		{ label = "Delay", value = item.weaponDelay },
		{ label = "Armor", value = item.armor },
		{ label = "Classes", value = classText(item.classes) },
		{ label = "Relic", value = boolText(item.relic) },
		{ label = "Buy", value = Format.currency(item.buyValue) },
		{ label = "Sell", value = Format.currency(item.sellValue) },
		{ label = "Sold by", value = item.vendorSource },
		{ label = "Dropped by", value = item.source },
		{ label = "Other source", value = item.othersource },
		{ label = "Reward from", value = item.questSource },
		{ label = "Related quest", value = item.relatedQuest },
		{ label = "Crafting recipe", value = item.craftSource },
		{ label = "Component for", value = item.componentFor },
		{ label = "Effects", value = item.effects },
		{ label = "DPS", value = item.dps },
		{ label = "Casting Time", value = item.castTime },
		{ label = "Duration", value = item.duration },
		{ label = "Cooldown", value = item.cooldown },
		{ label = "Activatable", value = item.effect },
		{ label = "Worn Effect", value = item.wornEffect },
		{ label = "Proc Effect", value = item.procEffect },
		{ label = "Buff Given", value = item.buffGiven },
		{ label = "Teaches Spell", value = item.taughtSpell },
		{ label = "Teaches Skill", value = item.taughtSkill },
		{ label = "Spell Type", value = item.spellType },
		{ label = "Skill Type", value = item.skillType },
		{ label = "Mana Cost", value = item.manaCost },
		{ label = "Consumable", value = boolText(item.disposable) },
		{ label = "Produces", value = item.produces },
		{ label = "Ingredients", value = item.ingredients },
		{ label = "Description", value = item.description },
		{ label = "Provides one of", value = item.guaranteedDrops },
		{ label = "Overall Item Chances", value = item.dropRates },
	}

	return Render.infobox({ title = item.name, classes = { "erenshor-item-infobox" }, rows = rows })
end

function p.renderTooltip(args, pageTitle)
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return missingOutput(item)
	end

	local mode = Args.resolve(args, "mode", item.type) or item.type
	local rows = {
		{ label = "Type", value = item.type },
		{ label = "Slot", value = item.slot },
		{ label = "Damage", value = item.damage },
		{ label = "Armor", value = item.armor },
	}
	return Render.infobox({
		title = item.name .. " " .. mode,
		classes = { "erenshor-item-tooltip" },
		rows = rows,
	})
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
	local fields = {
		{ "_table", "Items" },
		{ "Page", pageTitle },
		{ "StableKey", item.stableKey },
		{ "Name", item.name },
		{ "Type", item.type },
		{ "Slot", item.slot },
		{ "ItemLevel", item.itemLevel },
		{ "Damage", item.damage },
		{ "Delay", item.weaponDelay },
		{ "Armor", item.armor },
		{ "BuyValue", item.buyValue },
		{ "SellValue", item.sellValue },
		{ "Image", ensureImageFile(item.image, item.name) },
		{ "Classes", classCargo(item.classes) },
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

function p.infobox(frame)
	return p.renderInfobox(templateArgs(frame), currentTitleText())
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
