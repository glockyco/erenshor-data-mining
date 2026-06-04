local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")

local Data = mw.loadData("Module:Erenshor/Data/Zones")

local p = {}

local FIELD_OVERRIDES = {
	["connects"] = "connects",
	["image"] = "image",
	["imagecaption"] = "imageCaption",
	["level"] = "level",
	["maplink"] = "mapLink",
	["title"] = "name",
	["type"] = "type",
}

local ROOT_PUBLIC_PARAMETERS = {
	"title",
	"image",
	"imagecaption",
	"type",
	"level",
	"maplink",
	"connects",
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

local function normalizeMapSelector(value)
	if isBlank(value) then
		return nil
	end
	local selector = tostring(value)
	if selector:match("^zone:") then
		return selector
	end
	return "zone:" .. selector
end

local function encodeSelector(selector)
	return tostring(selector):gsub(":", "%%3A"):gsub(" ", "%%20")
end

local function mapLinkForSelector(selector)
	if isBlank(selector) then
		return ""
	end
	return "[https://erenshor-maps.wowmuch1.workers.dev/map?sel="
		.. encodeSelector(selector)
		.. " Map]"
end

local function explicitStableKey(args)
	return Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
end

local function resolveStableKey(args)
	local stableKey = explicitStableKey(args)
	if stableKey ~= nil and Data.zones[stableKey] ~= nil then
		return stableKey
	end
	return nil
end

local function applyRootOverrides(zone, args)
	for _, publicName in ipairs(ROOT_PUBLIC_PARAMETERS) do
		local fieldName = FIELD_OVERRIDES[publicName]
		if fieldName ~= nil and Args.has(args, publicName) then
			zone[fieldName] = Args.resolve(args, publicName, zone[fieldName])
		end
	end
end

local function missingZone(args, pageTitle)
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
		return missingZone(args, pageTitle)
	end

	local zone = copyTable(Data.zones[stableKey])
	zone.stableKey = stableKey
	applyRootOverrides(zone, args)
	return zone
end

local function missingOutput(zone)
	return '<span class="erenshor-missing-data">Missing zone data: '
		.. Format.escape(zone.name)
		.. "</span>[[Category:Pages with missing Erenshor zone data]]"
end

local function connectLinks(connects)
	if connects == nil then
		return nil
	end
	if type(connects) ~= "table" then
		return connects
	end
	local out = {}
	for _, page in ipairs(connects) do
		if not isBlank(page) then
			table.insert(out, Format.pageLink(page))
		end
	end
	return table.concat(out, "<br>")
end

local function zoneCategories(zoneType)
	if zoneType == "Dungeon" then
		return "[[Category:Zones]][[Category:Dungeons]]"
	end
	return "[[Category:Zones]]"
end

local FIELD_ACCESSORS = {
	name = function(z)
		return z.name
	end,
	image = function(z)
		return ensureImageFile(z.image, z.name)
	end,
	imagecaption = function(z)
		return z.imageCaption
	end,
	type = function(z)
		return z.type
	end,
	level = function(z)
		return z.level
	end,
	maplink = function(z)
		return z.mapLink or mapLinkForSelector(z.map)
	end,
	connects = function(z)
		return connectLinks(z.connects)
	end,
}

function p.fieldValue(args, pageTitle, key)
	local zone = p.resolve(args, pageTitle)
	if zone.missing then
		return ""
	end
	local accessor = FIELD_ACCESSORS[key]
	if accessor == nil then
		error("Unknown Zone infobox field: " .. tostring(key))
	end
	local value = accessor(zone)
	if value == nil then
		return ""
	end
	return tostring(value)
end

function p.statusText(args, pageTitle)
	local zone = p.resolve(args, pageTitle)
	if zone.missing then
		return missingOutput(zone)
	end
	return zoneCategories(zone.type)
end

function p.renderMapLink(args, pageTitle)
	args = args or {}
	if Args.has(args, "zone") then
		local selector = normalizeMapSelector(Args.resolve(args, "zone", nil))
		if selector == nil then
			return "—"
		end
		return mapLinkForSelector(selector)
	end

	local zone = p.resolve(args, pageTitle)
	if zone.missing then
		return "—"
	end
	return mapLinkForSelector(zone.map)
end

function p.field(frame)
	return p.fieldValue(templateArgs(frame), currentTitleText(), frame.args[1])
end

function p.status(frame)
	return p.statusText(templateArgs(frame), currentTitleText())
end

function p.mapLink(frame)
	return p.renderMapLink(templateArgs(frame), currentTitleText())
end

return p
