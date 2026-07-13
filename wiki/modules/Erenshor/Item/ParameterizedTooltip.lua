-- Module:Erenshor/Item/ParameterizedTooltip
--
-- Renders the legacy Item/Weapon and Item/Armor templates from one Normal
-- quality parameter set.  Quality.lua is the only place that owns the game
-- quality formulas; this module only maps fields and composes the legacy
-- card templates via frame:expandTemplate.
--
-- The legacy card templates open with wikitable markup, which MediaWiki
-- only recognizes at the start of a line.  Rendered output is therefore
-- assembled from newline-joined strings; mw.html would concatenate the
-- expanded cards onto one line and demote "{|" to literal text.

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

local ZERO_OMIT_FIELDS = {
	proc_target_damage = true,
	proc_target_healing = true,
	proc_shielding_amt = true,
	proc_lifetap = true,
	proc_group_effect = true,
	proc_stun_target = true,
	proc_charm_target = true,
	proc_root_target = true,
	proc_taunt_spell = true,
	proc_hp = true,
	proc_ac = true,
	proc_mana = true,
	proc_str = true,
	proc_dex = true,
	proc_end = true,
	proc_agi = true,
	proc_wis = true,
	proc_int = true,
	proc_cha = true,
	proc_mr = true,
	proc_er = true,
	proc_pr = true,
	proc_vr = true,
	proc_movement_speed = true,
	proc_damage_shield = true,
	proc_haste = true,
	proc_percent_lifesteal = true,
	proc_atk_roll_modifier = true,
	proc_resonate_chance = true,
	proc_add_proc_chance = true,
	proc_xp_bonus = true,
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

local function fileValue(value)
	if value == nil or value == "" or value == "-" then
		return value or ""
	end
	if string.match(value, "%.[^./]+$") ~= nil then
		return value
	end
	return value .. ".png"
end

local function imageValue(args)
	return fileValue(supplied(args, "image"))
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

local function hasAttackStats(args)
	local damage = tonumber(firstSupplied(args, BASE_ALIASES.weaponDamage))
	local delay = tonumber(supplied(args, "delay"))
	return damage ~= nil and damage > 0 and delay ~= nil and delay > 0
end

local function invocation(kindName, args, stats, frame)
	local templateName = kindName == "Weapon" and "Item/Weapon" or "Item/Armor"
	local templateArguments = {}
	local known = { kind = true, item_kind = true, stablekey = true }
	local rendersAttackStats = kindName == "Weapon" and hasAttackStats(args)

	local function put(field, value)
		templateArguments[field] = text(value)
		known[field] = true
	end

	put("image", imageValue(args))
	put("name", displayName(args, stats))
	put("slot", supplied(args, "slot"))
	put("type", supplied(args, "type"))
	put("relic", supplied(args, "relic"))
	put("tier", stats.visualTier)
	put("quality", stats.quality)

	-- Quality-derived stats replace whatever the article supplied.  Alias
	-- names (health/armor/magic/...) are marked known so the passthrough
	-- loop below cannot smuggle the Normal-quality inputs back in.
	for _, output in ipairs(STAT_OUTPUTS) do
		if output.name ~= "damage" or rendersAttackStats then
			put(output.name, stats[output.key])
		else
			known[output.name] = true
		end
		for _, alias in ipairs(BASE_ALIASES[output.key] or {}) do
			known[alias] = true
		end
	end

	-- Metadata and proc fields pass through once per card.  Optional numeric
	-- proc fields are dropped when zero so the legacy templates hide those
	-- rows exactly as hand-written invocations did.
	for _, field in ipairs(LEGACY_FIELDS) do
		if not known[field] then
			local value = supplied(args, field)
			if field == "proc_spell_icon" then
				value = fileValue(value)
			end
			if ZERO_OMIT_FIELDS[field] and tonumber(value) == 0 then
				known[field] = true
			else
				put(field, value)
			end
		end
	end

	-- Forward unrecognized fields so the legacy templates can learn new
	-- parameters without a module change silently dropping them.
	for key, value in pairs(args) do
		if type(key) == "string" and not known[key] then
			templateArguments[key] = text(value)
		end
	end

	return frame:expandTemplate({ title = templateName, args = templateArguments })
end

function p.render(frame)
	local args = templateArgs(frame)
	local itemKind = kind(args)
	local variants = Quality.variants(baseStats(args))
	local out = {
		'<div class="item-tooltip-quality-set" style="display:flex;flex-wrap:wrap;gap:1em;align-items:flex-start;width:calc(100% - 360px);min-width:350px;max-width:100%;overflow:visible">',
	}
	for _, stats in ipairs(variants) do
		out[#out + 1] = '<div class="item-tooltip-quality" style="flex:0 1 350px">'
		out[#out + 1] = '<div class="item-tooltip-quality-label item-tooltip-tier-'
			.. stats.visualTier
			.. '">'
			.. stats.quality
			.. "</div>"
		if stats.visualTier >= 3 then
			out[#out + 1] =
				'<div class="item-tooltip-quality-sparkle item-tooltip-quality-sparkle-improved">[[File:Blue_Sparkle.gif|80px]]</div>'
		end
		out[#out + 1] = invocation(itemKind, args, stats, frame)
		out[#out + 1] = "</div>"
	end
	out[#out + 1] = "</div>"
	return table.concat(out, "\n")
end

return p
