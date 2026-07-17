local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Quality = require("Module:Erenshor/Item/Quality")

local AbilityData
local ItemIndex
local CharacterData
local QuestData

local p = {}

local ITEM_SHARDS = {}

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
end

local function copyTable(value)
	local out = {}
	if value == nil then
		return out
	end
	for key, item in pairs(value) do
		out[key] = item
	end
	return out
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

local function templateArgs(frame)
	local out = copyTable(Args.parentArgs(frame))
	for key, value in pairs(frame.args or {}) do
		out[key] = value
	end
	return out
end

local function explicitStableKey(args)
	return Args.resolve(args or {}, "stablekey", nil)
		or Args.resolve(args or {}, "stableKey", nil)
		or Args.resolve(args or {}, "key", nil)
end

local function loadItemShard(name)
	if isBlank(name) then
		return nil
	end
	if ITEM_SHARDS[name] == nil then
		ITEM_SHARDS[name] = mw.loadData("Module:Erenshor/Data/Items/" .. tostring(name))
	end
	return ITEM_SHARDS[name]
end

local function itemByStableKey(stableKey)
	if isBlank(stableKey) then
		return nil
	end
	if ItemIndex == nil then
		ItemIndex = mw.loadData("Module:Erenshor/Data/Items")
	end
	local shardName = ItemIndex.byKey[stableKey]
	local shard = loadItemShard(shardName)
	if shard == nil then
		return nil
	end
	return shard[stableKey]
end

local function abilityByStableKey(stableKey)
	if isBlank(stableKey) then
		return nil
	end
	if AbilityData == nil then
		AbilityData = mw.loadData("Module:Erenshor/Data/AbilityLinks")
	end
	return AbilityData.abilities[stableKey]
end

local function spanAttributes(kind, args, page, quality)
	local attributes = {
		'class="erenshor-link erenshor-link--' .. Format.escape(kind) .. '"',
		'data-erenshor-kind="' .. Format.escape(kind) .. '"',
	}
	if not isBlank(page) then
		table.insert(attributes, 'data-erenshor-page="' .. Format.escape(page) .. '"')
	end
	local stableKey = explicitStableKey(args)
	if not isBlank(stableKey) then
		table.insert(attributes, 'data-erenshor-key="' .. Format.escape(stableKey) .. '"')
	end
	if kind == "item" and not isBlank(quality) then
		table.insert(attributes, 'data-erenshor-quality="' .. Format.escape(quality) .. '"')
	end
	return table.concat(attributes, " ")
end

local function wrap(kind, args, body, page, quality)
	if isBlank(body) then
		return ""
	end
	return "<span " .. spanAttributes(kind, args or {}, page, quality) .. ">" .. body .. "</span>"
end

local function resolvedText(args, record, fallback)
	return Args.resolve(args or {}, "text", nil) or (record and record.name) or fallback
end

local function resolvedPage(args, record, fallback)
	return Args.resolve(args or {}, "link", nil)
		or Args.resolve(args or {}, "page", nil)
		or (record and record.page)
		or fallback
end

local function resolveItemQuality(args)
	local requested = Args.resolve(args or {}, "quality", nil, { dashBlank = false })
	if requested == nil then
		return nil
	end
	local canonical = Quality.canonicalName(requested)
	if canonical == nil then
		error(string.format("Parameter 'quality' has invalid value %q", tostring(requested)), 3)
	end
	return canonical
end

local function renderItem(args)
	args = args or {}
	local quality = resolveItemQuality(args)
	local target = Args.resolve(args, "item", nil)
		or Args.resolve(args, "name", nil)
		or Args.resolve(args, 1, nil)
	local item
	if isBlank(target) then
		item = itemByStableKey(explicitStableKey(args))
	end
	local page = resolvedPage(args, item, target)
	local text = resolvedText(args, item, target or page)
	local image = Args.resolve(args, "image", nil) or (item and item.image) or page or text
	local imageLink = Format.fileLink(
		ensureImageFile(image, page or text),
		{ alt = text, size = "24x24px", link = page }
	)
	if Args.bool(args, "imageonly", false) then
		return wrap("item", args, imageLink, page, quality)
	end
	return wrap("item", args, imageLink .. " " .. Format.pageLink(page, text), page, quality)
end

local function renderAbility(args)
	args = args or {}
	local target = Args.resolve(args, 1, nil)
	local ability = abilityByStableKey(explicitStableKey(args))
	local page = resolvedPage(args, ability, target)
	local text = resolvedText(args, ability, target or page)
	local image = Args.resolve(args, "image", nil) or (ability and ability.image) or text
	local imageLink = Format.fileLink(ensureImageFile(image, text), { size = "30px", link = page })
	local body = '<span style="color:#fff;text-shadow:1px 1px 10px red, 1px 1px 10px orange;">'
		.. imageLink
	if Args.resolve(args, "imageonly", nil) ~= "1" then
		body = body .. " " .. Format.pageLink(page, text)
	end
	body = body .. "</span>"
	return wrap("ability", args, body, page)
end

local function renderQuest(args)
	args = args or {}
	local target = Args.resolve(args, 1, nil)
	local page = resolvedPage(args, nil, target)
	local text = resolvedText(args, nil, target or page)
	local icon = Format.fileLink("questiconsmall.png", { link = page })
	return wrap("quest", args, icon .. Format.pageLink(page, text), page)
end

local function renderPlain(kind, args)
	args = args or {}
	local target = Args.resolve(args, 1, nil)
	local stableKey = explicitStableKey(args)
	local record
	if kind == "character" and stableKey ~= nil then
		if CharacterData == nil then
			CharacterData = mw.loadData("Module:Erenshor/Data/Characters")
		end
		record = CharacterData.characters[stableKey]
	elseif kind == "quest" and stableKey ~= nil then
		if QuestData == nil then
			QuestData = mw.loadData("Module:Erenshor/Data/Quests")
		end
		record = QuestData.quests[stableKey]
	end
	local page = resolvedPage(args, record, target)
	local text = resolvedText(args, record, target or page)
	return wrap(kind, args, Format.pageLink(page, text), page)
end

function p.render(args)
	args = args or {}
	local kind = Args.resolve(args, "kind", nil)
	if isBlank(kind) then
		return ""
	end
	kind = tostring(kind):lower()
	if kind == "item" then
		return renderItem(args)
	elseif kind == "ability" then
		return renderAbility(args)
	elseif kind == "quest" then
		return renderQuest(args)
	elseif kind == "character" or kind == "zone" or kind == "faction" or kind == "class" then
		return renderPlain(kind, args)
	end
	return renderPlain(kind, args)
end

function p.join(values, separator)
	if values == nil then
		return ""
	end
	local out = {}
	for _, value in ipairs(values) do
		local rendered = p.render(value)
		if not isBlank(rendered) then
			table.insert(out, rendered)
		end
	end
	return table.concat(out, separator or "<br>")
end

-- Resolve an item record (page, name, image, unique, …) by StableKey. Lets other
-- modules read item-owned facts at the display layer instead of denormalizing them
-- into every relationship that references the item.
function p.itemRecord(stableKey)
	return itemByStableKey(stableKey)
end

local function renderFrame(frame, kind)
	local args = templateArgs(frame)
	args.kind = kind
	return p.render(args)
end

function p.item(frame)
	return renderFrame(frame, "item")
end

function p.ability(frame)
	return renderFrame(frame, "ability")
end

function p.quest(frame)
	return renderFrame(frame, "quest")
end

function p.character(frame)
	return renderFrame(frame, "character")
end

function p.zone(frame)
	return renderFrame(frame, "zone")
end

function p.faction(frame)
	return renderFrame(frame, "faction")
end

function p.class(frame)
	return renderFrame(frame, "class")
end

return p
