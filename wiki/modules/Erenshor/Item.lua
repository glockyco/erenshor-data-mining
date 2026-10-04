local Args = require("Module:Erenshor/Args")
local Link = require("Module:Erenshor/Link")
local Format = require("Module:Erenshor/Format")
local Tooltip = require("Module:Erenshor/Item/Tooltip")
local Quality = require("Module:Erenshor/Item/Quality")

local Index = mw.loadData("Module:Erenshor/Data/Items")
local Links = mw.loadData("Module:Erenshor/Data/Links")
local SkillData = mw.loadData("Module:Erenshor/Data/Skills")
local SpellData = mw.loadData("Module:Erenshor/Data/Spells")

local p = {}

local FIELD_OVERRIDES = {
	armor = "armor",
	buy = "buyValue",
	buffgiven = "buffGiven",
	buffsource = "buffSource",
	casttime = "castTime",
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
	duration = "duration",
	proceffect = "procEffect",
	produces = "produces",
	relic = "relic",
	sell = "sellValue",
	slot = "slot",
	title = "name",
	type = "type",
	taughtskill = "taughtSkill",
	taughtspell = "taughtSpell",
	skilltype = "skillType",
	spelltype = "spellType",
	worneffect = "wornEffectOverride",
}

local ROOT_PUBLIC_PARAMETERS = {
	"title",
	"image",
	"imagecaption",
	"type",
	"slot",
	"itemlevel",
	"othersource",
	"craftsource",
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
	local stableKey = Args.resolve(args, "stablekey", nil)
	if stableKey ~= nil then
		return stableKey
	end
	stableKey = Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
	if stableKey ~= nil then
		return stableKey
	end
	local encodedStableKey = Args.resolve(args, "encodedstablekey", nil)
	if encodedStableKey ~= nil then
		return mw.uri.decode(encodedStableKey, "PATH")
	end
	return nil
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

local function classText(classes, classLinks)
	if type(classLinks) == "table" then
		local links = {}
		for _, classLink in ipairs(classLinks) do
			if type(classLink) == "table" and not isBlank(classLink.stablekey) then
				table.insert(
					links,
					Link.render({ kind = "class", stablekey = classLink.stablekey })
				)
			end
		end
		if #links > 0 then
			return table.concat(links, " / ")
		end
	end
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

local hasValue

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
	local ability = Links.byKey[stableKey]
	if ability == nil or ability.kind ~= "ability" or isBlank(ability.page) then
		return nil
	end
	return ability.page
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
	othersource = function(i)
		return i.othersource
	end,
	craftsource = function(i)
		return i.craftSource
	end,
	relic = function(i)
		return i.relic == true and "Yes" or ""
	end,
	classes = function(i)
		return classText(i.classes, i.classLinks)
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
	local requestedQuality = Args.resolve(args, "quality", nil, { dashBlank = false })
	if requestedQuality ~= nil then
		local suppliedQuality = requestedQuality
		requestedQuality = mw.uri.decode(requestedQuality, "PATH")
		requestedQuality = Quality.canonicalName(requestedQuality)
		if requestedQuality == nil then
			error(
				"Invalid item quality '"
					.. suppliedQuality
					.. "'; expected Standard, Improved +1 through +5, Blessed, or Ascended",
				2
			)
		end
	end
	local item = p.resolve(args, pageTitle)
	if item.missing then
		return missingOutput(item)
	end
	return Tooltip.render(item, requestedQuality)
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

return p
