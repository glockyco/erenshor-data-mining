local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")
local Details = require("Module:Erenshor/ItemData/Details")
local Provenance = require("Module:Erenshor/ItemData/Provenance")

local p = {}
p.EDITOR_FIELDS = { type = true, questsource = true, relatedquest = true, othersource = true }
local INVALID = "[[Category:Item data calls with invalid identities]]"
local UNSUPPORTED = "[[Category:Item data calls with unsupported parameters]]"
local COVERED = "[[Category:Item data notes covered by game data]]"
local index
local shards, provenanceShards = {}, {}

local function arguments(frame)
	local out = {}
	for key, v in pairs(Args.parentArgs(frame)) do
		out[key] = v
	end
	for key, v in pairs(frame.args or {}) do
		out[key] = v
	end
	return out
end

local function attribute(value)
	return Format.escape(value):gsub('"', "&quot;")
end

local function properties(row)
	local out = {}
	for _, pair in ipairs({
		{ "stackable", "Stackable" },
		{ "unique", "Unique" },
		{ "relic", "Relic" },
		{ "noTradeNoDestroy", "Cannot trade or destroy" },
		{ "playerCannotSell", "Cannot be sold" },
		{ "disposable", "Consumed on use" },
		{ "mustBeEquippedToClick", "Must equip to cast" },
		{ "rareItem", "Rare item" },
		{ "fuelSource", "Fuel source" },
		{ "auctionable", "Auctionable" },
		{ "unavailableToSimPlayers", "Unavailable to simulated players" },
	}) do
		if row[pair[1]] then
			out[#out + 1] = pair[2]
		end
	end
	if row.fuelLevel ~= nil and row.fuelSource then
		out[#out + 1] = "Fuel level: " .. tostring(row.fuelLevel)
	end
	if (row.mining or 0) > 0 then
		out[#out + 1] = "Mining power: " .. tostring(row.mining)
	end
	if row.cosmeticEffect then
		out[#out + 1] = "Cosmetic: " .. tostring(row.cosmeticEffect):gsub("_", " ")
	end
	return table.concat(out, "<br />")
end

local function invalid(key)
	return '<span class="error item-data-invalid">ItemData requires one current item stablekey: '
		.. Format.escape(tostring(key or ""))
		.. "</span>"
		.. INVALID
end

function p.resolve(key)
	if type(key) ~= "string" or not key:match("^item:.+") then
		return nil
	end
	if index == nil then
		index = mw.loadData("Module:Erenshor/Data/ItemsV2")
	end
	if index.schemaVersion ~= 2 or index.provenanceSchemaVersion ~= 1 then
		error("Unsupported ItemData schema", 2)
	end
	local bucket = index.byKey[key]
	if type(bucket) ~= "string" or not bucket:match("^[0-9a-f][0-9a-f]$") then
		return nil
	end
	if shards[bucket] == nil then
		shards[bucket] = mw.loadData("Module:Erenshor/Data/ItemsV2/" .. bucket)
	end
	local row = shards[bucket][key]
	if type(row) ~= "table" or row.stableKey ~= key then
		return nil
	end
	return row
end

local function provenanceByKey(key, bucket)
	if
		type(bucket) ~= "string"
		or #bucket < 2
		or #bucket > 64
		or not bucket:match("^[0-9a-f]+$")
	then
		error("Missing ItemData provenance shard", 2)
	end
	if provenanceShards[bucket] == nil then
		provenanceShards[bucket] = mw.loadData("Module:Erenshor/Data/ItemProvenanceV1/" .. bucket)
	end
	local data = provenanceShards[bucket][key]
	if data == nil then
		error("Missing ItemData provenance: " .. key, 2)
	end
	return data
end

function p.provenance(row)
	return provenanceByKey(row.stableKey, row.provenanceShard)
end

function p.outcome(use)
	if index == nil then
		index = mw.loadData("Module:Erenshor/Data/ItemsV2")
	end
	local owners = index.outcomeItemByKey
	local owner = owners and owners[use.outcome_key]
	if type(owner) ~= "string" then
		error("Missing canonical ItemData outcome owner: " .. tostring(use.outcome_key), 2)
	end
	local data = provenanceByKey(owner, index.provenanceByKey[owner])
	for _, outcome in ipairs(data.acquisitions or {}) do
		if outcome.acquisition_key == use.outcome_key and outcome.item_stable_key == owner then
			return outcome, data.references
		end
	end
	error("Missing canonical ItemData outcome: " .. tostring(use.outcome_key), 2)
end

local function classifications(row, provenance)
	local labels = { row.type or "Item" }
	if row.assignQuestOnRead or row.completeQuestOnRead then
		labels[#labels + 1] = "[[Quest Items|Quest Item]]"
	end
	local quest, crafting = false, false
	for _, use in ipairs(provenance.uses or {}) do
		if use.kind == "quest_requirement" then
			quest = true
		end
		if use.kind == "crafting_material" then
			crafting = true
		end
	end
	if quest and not row.assignQuestOnRead and not row.completeQuestOnRead then
		labels[#labels + 1] = "[[Quest Items|Quest Item]]"
	end
	if crafting then
		labels[#labels + 1] = "[[Crafting]]"
	end
	return table.concat(labels, ", ")
end

local function infobox(frame, row, provenance)
	local aliases = {}
	for _, alias in ipairs(row.aliases or {}) do
		aliases[#aliases + 1] = alias
	end
	local args = {
		title = row.name,
		stablekey = row.stableKey,
		icon = Details.existingFile(frame, row.icon),
		screenshot = row.screenshot or "",
		type = classifications(row, provenance),
		aka = table.concat(aliases, ", "),
		classes = Link.join(row.classLinks),
		effects = Details.effectLinks(row),
		description = (row.kind == "charm" or row.kind == "spellscroll" or row.kind == "skillbook")
				and Details.description(row.description)
			or "",
		buy = row.buyValue and Format.currency(row.buyValue) or "",
		sell = row.playerCannotSell and "Cannot be sold"
			or (row.sellValue and Format.currency(row.sellValue) or ""),
		item_db_index = row.itemDbIndex ~= nil and tostring(row.itemDbIndex) or "",
		slot = row.slot or "",
		itemlevel = row.itemLevel or "",
		item_flags = properties(row),
		taughtspell = row.teachesSpell
				and Link.render({ kind = "ability", stablekey = row.teachesSpell })
			or "",
		taughtskill = row.teachesSkill
				and Link.render({ kind = "ability", stablekey = row.teachesSkill })
			or "",
		ingredients = Details.recipeLinks(row.ingredients),
		produces = Details.recipeLinks(row.rewards),
	}
	local readQuests = {}
	if row.assignQuestOnRead then
		readQuests[#readQuests + 1] = "Starts when read: "
			.. Provenance.identity(row.assignQuestOnRead, provenance.references)
	end
	if row.completeQuestOnRead then
		readQuests[#readQuests + 1] = "Completes when read: "
			.. Provenance.identity(row.completeQuestOnRead, provenance.references)
	end
	args.relatedquest = table.concat(readQuests, "<br />")
	for _, render in ipairs(row.renders or {}) do
		local field = render.body and "render_" .. render.body or "render"
		if field == "render" or field == "render_male" or field == "render_female" then
			args[field] = render.title
		end
	end
	local lifecycle = row.lifecycle or provenance.disposition or {}
	if
		lifecycle.disposition == "removed"
		or lifecycle.disposition == "unobtainable"
		or lifecycle.disposition == "unused"
	then
		args.historical_state = lifecycle.disposition
		local notice = lifecycle.notice or {}
		args.historical_update, args.historical_date, args.historical_url =
			notice.update or "", notice.date or "", notice.url or ""
		args.historical_chat = notice.chat and "yes" or ""
	end
	return frame:expandTemplate({ title = "Item", args = args })
end

local function editorial(args)
	local out = {}
	for _, field in ipairs({ "type", "questsource", "relatedquest", "othersource" }) do
		if args[field] ~= nil and tostring(args[field]) ~= "" then
			local label = ({
				type = "Additional classifications",
				questsource = "Additional rewards",
				relatedquest = "Additional quest associations",
				othersource = "Other source notes",
			})[field]
			out[#out + 1] = '<div class="item-data-editor-note" data-erenshor-editor-field="'
				.. field
				.. '"><h3>'
				.. label
				.. "</h3>"
				.. tostring(args[field])
				.. "</div>"
		end
	end
	if #out == 0 then
		return ""
	end
	return '<div class="item-data-editorial"><h2>Editor notes</h2>'
		.. table.concat(out, "\n")
		.. "</div>"
end

function p.renderArgs(frame, args)
	local key = args.stablekey
	local row = p.resolve(key)
	if row == nil then
		return invalid(key)
	end
	local data = p.provenance(row)
	local unsupported = false
	for name in pairs(args) do
		if name ~= "stablekey" and not p.EDITOR_FIELDS[name] then
			unsupported = true
		end
	end
	local out = {
		'<div class="item-data-root" data-erenshor-key="' .. attribute(key) .. '">',
		infobox(frame, row, data),
		'<div class="item-data-details" data-erenshor-key="' .. attribute(key) .. '">',
		Details.render(frame, row),
		"</div>",
		Provenance.render(data, p.outcome),
		editorial(args),
	}
	if row.bookTitle then
		out[#out + 1] = '<div class="item-data-book-title">Book: '
			.. Format.escape(row.bookTitle)
			.. "</div>"
	end
	out[#out + 1] = "</div>"
	if unsupported then
		out[#out + 1] = UNSUPPORTED
	end
	return Format.preserveIdentityAttributes(table.concat(out, "\n"))
end

function p.render(frame)
	return p.renderArgs(frame, arguments(frame))
end

function p.sourceNoteArgs(args)
	local row = p.resolve(args.item)
	if row == nil or Args.isBlank(args.kind) or Args.isBlank(args.source) then
		return invalid(args.item)
	end
	local out = '<span class="item-data-source-note">' .. tostring(args.text or "") .. "</span>"
	if Provenance.covered(p.provenance(row), args.item, args.kind, args.source) then
		out = out .. COVERED
	end
	return out
end

function p.sourceNote(frame)
	return p.sourceNoteArgs(arguments(frame))
end

return p
