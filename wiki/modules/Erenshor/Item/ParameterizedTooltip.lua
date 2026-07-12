-- Module:Erenshor/Item/ParameterizedTooltip
--
-- Renders the legacy Item/Weapon and Item/Armor templates from one Normal
-- quality parameter set.  Quality.lua is the only place that owns the game
-- quality formulas; this module only maps fields and assembles wikitext.

local Args = require("Module:Erenshor/Args")
local Quality = require("Module:Erenshor/Item/Quality")

local p = {}

local LEGACY_FIELDS = {
	"image",
	"name",
	"slot",
	"type",
	"relic",
	"tier",
	"quality",
	"str",
	"end",
	"dex",
	"agi",
	"int",
	"wis",
	"cha",
	"res",
	"damage",
	"delay",
	"range",
	"health",
	"mana",
	"armor",
	"magic",
	"poison",
	"elemental",
	"void",
	"description",
	"arcanist",
	"duelist",
	"druid",
	"paladin",
	"reaver",
	"stormcaller",
	"proc_style",
	"proc_chance",
	"proc_spell_icon",
	"proc_spell_name",
	"proc_spell_level",
	"proc_spell_duration_ticks",
	"proc_spell_type",
	"proc_spell_line",
	"proc_target_damage",
	"proc_target_healing",
	"proc_shielding_amt",
	"proc_damage_type",
	"proc_cast_time",
	"proc_cooldown",
	"proc_spell_range",
	"proc_lifetap",
	"proc_group_effect",
	"proc_stun_target",
	"proc_charm_target",
	"proc_root_target",
	"proc_taunt_spell",
	"proc_aggro",
	"proc_status_effect_name",
	"proc_hp",
	"proc_ac",
	"proc_mana",
	"proc_str",
	"proc_dex",
	"proc_end",
	"proc_agi",
	"proc_wis",
	"proc_int",
	"proc_cha",
	"proc_mr",
	"proc_er",
	"proc_pr",
	"proc_vr",
	"proc_movement_speed",
	"proc_damage_shield",
	"proc_haste",
	"proc_percent_lifesteal",
	"proc_atk_roll_modifier",
	"proc_resonate_chance",
	"proc_add_proc_name",
	"proc_add_proc_chance",
	"proc_special_descriptor",
	"proc_xp_bonus",
}

local BASE_ALIASES = {
	weaponDamage = { "damage", "weaponDamage", "weapon_damage" },
	hp = { "health", "hp" },
	mana = { "mana" },
	ac = { "armor", "ac" },
	str = { "str" },
	["end"] = { "end" },
	dex = { "dex" },
	agi = { "agi" },
	int = { "int" },
	wis = { "wis" },
	cha = { "cha" },
	res = { "res" },
	mr = { "magic", "mr" },
	er = { "elemental", "er" },
	pr = { "poison", "pr" },
	vr = { "void", "vr" },
}

local STAT_OUTPUTS = {
	{ name = "str", key = "str" },
	{ name = "end", key = "end" },
	{ name = "dex", key = "dex" },
	{ name = "agi", key = "agi" },
	{ name = "int", key = "int" },
	{ name = "wis", key = "wis" },
	{ name = "cha", key = "cha" },
	{ name = "res", key = "res" },
	{ name = "damage", key = "weaponDamage" },
	{ name = "health", key = "hp" },
	{ name = "mana", key = "mana" },
	{ name = "armor", key = "ac" },
	{ name = "magic", key = "mr" },
	{ name = "poison", key = "pr" },
	{ name = "elemental", key = "er" },
	{ name = "void", key = "vr" },
}

local function templateArgs(frame)
	local out = {}
	if frame ~= nil and type(frame.getParent) == "function" then
		local parent = frame:getParent()
		if parent ~= nil and parent.args ~= nil then
			for key, value in pairs(parent.args) do
				out[key] = value
			end
		end
	end
	if frame ~= nil and frame.args ~= nil then
		for key, value in pairs(frame.args) do
			out[key] = value
		end
	end
	return out
end

local function text(value)
	if value == nil then
		return ""
	end
	return tostring(value)
end

local function supplied(args, name)
	local value = Args.resolve(args, name, nil)
	if value == nil then
		return nil
	end
	return text(value)
end

local function firstSupplied(args, names)
	for _, name in ipairs(names) do
		local value = supplied(args, name)
		if value ~= nil then
			return value
		end
	end
	return nil
end

local function imageValue(args)
	local value = supplied(args, "image")
	if value == nil or value == "" or value == "-" then
		return value or ""
	end
	if string.match(value, "%.[^./]+$") ~= nil then
		return value
	end
	return value .. ".png"
end

local function displayName(args, stats)
	local value = supplied(args, "name") or ""
	if value == "" then
		return value
	end
	if stats.runtimeId >= 11 and stats.runtimeId <= 15 then
		return value .. " +" .. (stats.runtimeId - 10)
	end
	return value
end

local function kind(args)
	local value = firstSupplied(args, { "kind", "item_kind" })
	if value == nil then
		error("ItemTooltip requires kind=Weapon or kind=Armor", 2)
	end
	local normalized = string.lower(value)
	if normalized == "weapon" then
		return "Weapon"
	end
	if normalized == "armor" then
		return "Armor"
	end
	error("ItemTooltip kind must be Weapon or Armor", 2)
end

local function baseStats(args)
	local base = {}
	for key, aliases in pairs(BASE_ALIASES) do
		base[key] = firstSupplied(args, aliases) or 0
	end
	return base
end

local function markKnown(known, key)
	known[key] = true
end

local function add(lines, key, value, templateArguments)
	local normalized = text(value)
	lines[#lines + 1] = "|" .. key .. "=" .. normalized
	if templateArguments ~= nil then
		templateArguments[key] = normalized
	end
end

local function invocation(kindName, args, stats, frame)
	local templateName = kindName == "Weapon" and "Item/Weapon" or "Item/Armor"
	local templateArguments = {}
	local lines = { "{{" .. templateName }
	local known = { kind = true, item_kind = true, stablekey = true }

	for _, field in ipairs({ "image", "name", "slot", "type", "relic" }) do
		local value = supplied(args, field) or ""
		if field == "image" then
			value = imageValue(args)
		elseif field == "name" then
			value = displayName(args, stats)
		end
		add(lines, field, value, templateArguments)
		markKnown(known, field)
	end
	add(lines, "tier", stats.visualTier, templateArguments)
	add(lines, "quality", stats.quality, templateArguments)
	markKnown(known, "tier")
	markKnown(known, "quality")

	local computed = {
		image = true,
		name = true,
		slot = true,
		type = true,
		relic = true,
		tier = true,
		quality = true,
	}
	for _, output in ipairs(STAT_OUTPUTS) do
		computed[output.name] = true
		if output.name ~= "damage" or kindName == "Weapon" then
			add(lines, output.name, stats[output.key], templateArguments)
		end
		for _, alias in ipairs(BASE_ALIASES[output.key] or {}) do
			markKnown(known, alias)
		end
		markKnown(known, output.name)
	end

	-- Preserve metadata and proc fields without duplicating their mapping in
	-- every quality row.  Computed stat fields are supplied above.
	for _, field in ipairs(LEGACY_FIELDS) do
		markKnown(known, field)
		if not computed[field] then
			add(lines, field, supplied(args, field) or "", templateArguments)
		end
	end

	-- Keep future fields that the legacy template may learn without silently
	-- dropping them.  Sorting makes output deterministic.
	local extra = {}
	for key in pairs(args) do
		if type(key) == "string" and not known[key] then
			extra[#extra + 1] = key
		end
	end
	table.sort(extra)
	for _, key in ipairs(extra) do
		add(lines, key, args[key], templateArguments)
	end

	lines[#lines + 1] = "}}"
	if frame ~= nil and type(frame.preprocess) == "function" then
		local source = "{{#tag:div|" .. table.concat(lines, "\n") .. "}}"
		return frame:preprocess(source)
	end
	if frame ~= nil and type(frame.expandTemplate) == "function" then
		return frame:expandTemplate({ title = templateName, args = templateArguments })
	end
	return table.concat(lines, "\n")
end

function p.render(frame)
	local args = templateArgs(frame)
	local itemKind = kind(args)
	local variants = Quality.variants(baseStats(args))
	local wrapper = mw.html
		.create("div")
		:addClass("item-tooltip-quality-set")
		:css("display", "flex")
		:css("flex-wrap", "wrap")
		:css("gap", "1em")
		:css("align-items", "flex-start")
		:css("width", "calc(100% - 360px)")
		:css("min-width", "350px")
		:css("max-width", "100%")
		:css("overflow", "visible")
	for _, stats in ipairs(variants) do
		local card = wrapper:tag("div"):addClass("item-tooltip-quality"):css("flex", "0 1 350px")
		card:tag("div")
			:addClass("item-tooltip-quality-label")
			:addClass("item-tooltip-tier-" .. stats.visualTier)
			:wikitext(stats.quality)
		if stats.visualTier >= 3 then
			card:tag("div")
				:addClass("item-tooltip-quality-sparkle")
				:addClass("item-tooltip-quality-sparkle-improved")
				:wikitext("[[File:Blue_Sparkle.gif|80px]]")
		end
		card:wikitext(invocation(itemKind, args, stats, frame))
	end
	return tostring(wrapper)
end

return p
