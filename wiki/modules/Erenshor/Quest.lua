local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Render = require("Module:Erenshor/Render")

local Data = mw.loadData("Module:Erenshor/Data/Quests")

local p = {}

local FIELD_OVERRIDES = {
	["factionchanges"] = "factionChanges",
	["gold"] = "gold",
	["image"] = "image",
	["imagecaption"] = "imageCaption",
	["items"] = "items",
	["items required"] = "itemsRequired",
	["level"] = "level",
	["location"] = "location",
	["next"] = "next",
	["prerequisite"] = "prerequisite",
	["previous"] = "previous",
	["repeatable"] = "repeatable",
	["title"] = "name",
	["experience"] = "experience",
}

local ROOT_PUBLIC_PARAMETERS = {
	"title",
	"image",
	"imagecaption",
	"location",
	"repeatable",
	"prerequisite",
	"level",
	"items required",
	"experience",
	"gold",
	"factionchanges",
	"items",
	"previous",
	"next",
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
	if stableKey ~= nil and Data.quests[stableKey] ~= nil then
		return stableKey
	end
	return nil
end

local function applyRootOverrides(quest, args)
	for _, publicName in ipairs(ROOT_PUBLIC_PARAMETERS) do
		local fieldName = FIELD_OVERRIDES[publicName]
		if fieldName ~= nil and Args.has(args, publicName) then
			quest[fieldName] = Args.resolve(args, publicName, quest[fieldName])
		end
	end
end

local function missingQuest(args, pageTitle)
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
		return missingQuest(args, pageTitle)
	end

	local quest = copyTable(Data.quests[stableKey])
	quest.stableKey = stableKey
	applyRootOverrides(quest, args)
	return quest
end

local function missingOutput(quest)
	return '<span class="erenshor-missing-data">Missing quest data: '
		.. Format.escape(quest.name)
		.. "</span>[[Category:Pages with missing Erenshor quest data]]"
end

function p.renderInfobox(args, pageTitle)
	local quest = p.resolve(args, pageTitle)
	if quest.missing then
		return missingOutput(quest)
	end

	local rows = {
		{
			label = "Image",
			value = Format.fileLink(
				ensureImageFile(quest.image, quest.name),
				{ alt = quest.name, size = "64x64px" }
			),
		},
		{ label = "Caption", value = quest.imageCaption },
		{ label = "Location", value = quest.location },
		{ label = "Repeatable", value = quest.repeatable },
		{ label = "Prerequisite", value = quest.prerequisite },
		{ label = "Level", value = quest.level },
		{ label = "Items required", value = quest.itemsRequired },
		{ label = "Experience", value = quest.experience },
		{ label = "Gold", value = quest.gold },
		{ label = "Faction changes", value = quest.factionChanges },
		{ label = "Items", value = quest.items },
		{ label = "Previous", value = quest.previous },
		{ label = "Next", value = quest.next },
	}

	return Render.infobox({
		title = quest.name,
		type = "Quest",
		classes = { "erenshor-quest-infobox" },
		rows = rows,
	}) .. "[[Category:Quests]]"
end

function p.infobox(frame)
	return p.renderInfobox(templateArgs(frame), currentTitleText())
end

return p
