local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")

local Data = mw.loadData("Module:Erenshor/Data/Characters")

local p = {}

local FIELD_OVERRIDES = {
	ac = "ac",
	agility = "agility",
	charisma = "charisma",
	class = "class",
	coordinates = "coordinates",
	droprates = "dropRates",
	elemental = "elemental",
	endurance = "endurance",
	experience = "experience",
	faction = "faction",
	factionchange = "factionChange",
	guaranteeddrops = "guaranteedDrops",
	health = "health",
	image = "image",
	imagecaption = "imageCaption",
	intelligence = "intelligence",
	level = "level",
	levelmodmax = "levelModMax",
	levelmodmin = "levelModMin",
	levelvariancemax = "levelVarianceMax",
	levelvariancemin = "levelVarianceMin",
	magic = "magic",
	mana = "mana",
	name = "name",
	poison = "poison",
	respawn = "respawn",
	spawnchance = "spawnChance",
	spells = "spells",
	strength = "strength",
	title = "name",
	type = "type",
	void = "void",
	wisdom = "wisdom",
	xpmultiplier = "xpMultiplier",
	zones = "zones",
}

local ROOT_PUBLIC_PARAMETERS = {
	"name",
	"title",
	"image",
	"imagecaption",
	"type",
	"faction",
	"factionchange",
	"class",
	"zones",
	"coordinates",
	"respawn",
	"spawnchance",
	"level",
	"experience",
	"guaranteeddrops",
	"droprates",
	"spells",
	"health",
	"mana",
	"ac",
	"strength",
	"endurance",
	"dexterity",
	"agility",
	"intelligence",
	"wisdom",
	"charisma",
	"magic",
	"poison",
	"elemental",
	"void",
	"levelmodmin",
	"levelmodmax",
	"levelvariancemin",
	"levelvariancemax",
	"xpmultiplier",
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

local function explicitStableKey(args)
	return Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
end

local function resolveStableKey(args)
	local stableKey = explicitStableKey(args)
	if stableKey ~= nil and Data.characters[stableKey] ~= nil then
		return stableKey
	end
	return nil
end

local function applyOverride(character, args, publicName, fieldName)
	if Args.has(args, publicName) then
		character[fieldName] = Args.resolve(args, publicName, character[fieldName])
	end
end

local function applyRootOverrides(character, args)
	for _, publicName in ipairs(ROOT_PUBLIC_PARAMETERS) do
		local fieldName = FIELD_OVERRIDES[publicName]
		if fieldName ~= nil then
			applyOverride(character, args, publicName, fieldName)
		end
	end
end

local function missingCharacter(args, pageTitle)
	return {
		missing = true,
		name = Args.resolve(args, "name", pageTitle) or pageTitle,
		page = pageTitle,
	}
end

function p.resolve(args, pageTitle)
	args = args or {}
	pageTitle = pageTitle or currentTitleText()

	local stableKey = resolveStableKey(args)
	if stableKey == nil then
		return missingCharacter(args, pageTitle)
	end

	local character = copyTable(Data.characters[stableKey])
	character.stableKey = stableKey
	applyRootOverrides(character, args)
	return character
end

local function missingOutput(character)
	return '<span class="erenshor-missing-data">Missing character data: '
		.. Format.escape(character.name)
		.. "</span>[[Category:Pages with missing Erenshor character data]]"
end

local function typeText(characterType)
	if characterType == "NPC" then
		return "[[:Category:Characters|NPC]]"
	end
	if characterType == "Boss" or characterType == "Rare" or characterType == "Enemy" then
		return Format.pageLink("Enemies", characterType)
	end
	return characterType
end

local function categoryForType(characterType)
	if characterType == "Boss" then
		return "[[Category:Bosses]]"
	end
	if characterType == "NPC" then
		return "[[Category:Characters]]"
	end
	if characterType == "[[Simulated Players|Sim]]" then
		return ""
	end
	return "[[Category:Enemies]]"
end

local function mapLink(selector)
	if isBlank(selector) then
		return ""
	end
	local encoded = tostring(selector):gsub(" ", "%%20")
	return "[https://erenshor-maps.wowmuch1.workers.dev/map?sel="
		.. encoded
		.. " View on the interactive map]"
end

local FIELD_ACCESSORS = {
	name = function(c)
		return c.name
	end,
	image = function(c)
		return ensureImageFile(c.image, c.name)
	end,
	imagecaption = function(c)
		return c.imageCaption
	end,
	type = function(c)
		return typeText(c.type)
	end,
	faction = function(c)
		return c.faction
	end,
	factionchange = function(c)
		return c.factionChange
	end,
	class = function(c)
		return c.class
	end,
	map = function(c)
		return mapLink(c.mapSelector)
	end,
	zones = function(c)
		return c.zones
	end,
	coordinates = function(c)
		return c.coordinates
	end,
	respawn = function(c)
		return c.respawn
	end,
	spawnchance = function(c)
		return c.spawnChance
	end,
	level = function(c)
		return c.level
	end,
	experience = function(c)
		return c.experience
	end,
	guaranteeddrops = function(c)
		return c.guaranteedDrops
	end,
	droprates = function(c)
		return c.dropRates
	end,
	spells = function(c)
		return c.spells
	end,
	health = function(c)
		return c.health
	end,
	ac = function(c)
		return c.ac
	end,
	magic = function(c)
		return c.magic
	end,
	poison = function(c)
		return c.poison
	end,
	elemental = function(c)
		return c.elemental
	end,
	void = function(c)
		return c.void
	end,
}

function p.fieldValue(args, pageTitle, key)
	local character = p.resolve(args, pageTitle)
	if character.missing then
		return ""
	end
	local accessor = FIELD_ACCESSORS[key]
	if accessor == nil then
		error("Unknown Character infobox field: " .. tostring(key))
	end
	local value = accessor(character)
	if value == nil then
		return ""
	end
	return tostring(value)
end

function p.statusText(args, pageTitle)
	local character = p.resolve(args, pageTitle)
	if character.missing then
		return missingOutput(character)
	end
	return categoryForType(character.type)
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

local function cargoStoreText(character, pageTitle)
	local fields = {
		{ "_table", "Characters" },
		{ "Page", pageTitle },
		{ "StableKey", character.stableKey },
		{ "Name", character.name },
		{ "Type", character.type },
		{ "Zones", character.zones },
		{ "Level", character.level },
		{ "Class", character.class },
		{ "Faction", character.faction },
		{ "SpawnChance", character.spawnChance },
		{ "HasDrops", character.hasDrops },
		{ "HasSpells", character.hasSpells },
		{ "MapSelector", character.mapSelector },
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

function p.cargoStore(frame)
	local args = templateArgs(frame)
	local pageTitle = currentTitleText()
	local character = p.resolve(args, pageTitle)
	if character.missing then
		return ""
	end
	local text = cargoStoreText(character, pageTitle)
	if frame ~= nil and frame.preprocess ~= nil then
		return frame:preprocess(text)
	end
	return text
end

return p
