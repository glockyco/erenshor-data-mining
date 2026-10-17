local Link = require("Module:Erenshor/Link")
local Quality = require("Module:Erenshor/Item/Quality")
local ParameterizedTooltip = require("Module:Erenshor/Item/ParameterizedTooltip")
local Format = require("Module:Erenshor/Format")

local p = {}
local FILE_TITLES = {}

function p.existingFile(frame, title)
	if title == nil or title == "" then
		return ""
	end
	if FILE_TITLES[title] == nil then
		FILE_TITLES[title] = frame:callParserFunction("#ifexist", { "Media:" .. title, title, "" })
	end
	return FILE_TITLES[title]
end

local STAT_NAMES = {
	weaponDamage = "damage",
	hp = "health",
	ac = "armor",
	mr = "magic",
	er = "elemental",
	pr = "poison",
	vr = "void",
	mana = "mana",
	str = "str",
	["end"] = "end",
	dex = "dex",
	agi = "agi",
	int = "int",
	wis = "wis",
	cha = "cha",
	res = "res",
}
local SPELL_FIELDS = {
	requiredLevel = "spell_level",
	type = "spell_type",
	line = "spell_line",
	targetDamage = "target_damage",
	targetHealing = "target_healing",
	shieldAmount = "shielding_amt",
	damageType = "damage_type",
	castTimeSeconds = "cast_time",
	cooldownSeconds = "cooldown",
	range = "spell_range",
	lifetap = "lifetap",
	groupEffect = "group_effect",
	stun = "stun_target",
	charm = "charm_target",
	root = "root_target",
	taunt = "taunt_spell",
	aggro = "aggro",
	hp = "hp",
	ac = "ac",
	mana = "mana",
	str = "str",
	["end"] = "end",
	dex = "dex",
	agi = "agi",
	int = "int",
	wis = "wis",
	cha = "cha",
	mr = "mr",
	er = "er",
	pr = "pr",
	vr = "vr",
	movementSpeed = "movement_speed",
	damageShield = "damage_shield",
	haste = "haste",
	lifesteal = "percent_lifesteal",
	atkRollModifier = "atk_roll_modifier",
	resonance = "resonate_chance",
	addProcChance = "add_proc_chance",
	specialDescriptor = "special_descriptor",
}
local EFFECT_LABELS = {
	weaponProc = "Attack",
	wandEffect = "Attack",
	bowEffect = "Attack",
	clickEffect = "Activatable",
	wornEffect = "Worn",
	aura = "Aura",
	skillUse = "Activatable",
	teachesSpell = "Teaches spell",
	teachesSkill = "Teaches skill",
}

local function value(v)
	if v == nil or v == false or v == 0 then
		return ""
	end
	if v == true then
		return "True"
	end
	return tostring(v)
end

function p.description(v)
	local out =
		mw.text.trim(tostring(v or "")):gsub("\r\n", "\n"):gsub("\r", "\n"):gsub("\n", "<br>")
	while out:find("<br><br><br>", 1, true) do
		out = out:gsub("<br><br><br>", "<br><br>")
	end
	out = out:gsub(
		"<[Cc][Oo][Ll][Oo][Rr]=[Gg][Rr][Ee][Ee][Nn]>%s*([^<]-)%s*</[Cc][Oo][Ll][Oo][Rr]>",
		'<span style="color: #15e300;">%1</span>'
	)
	return out
end

local function ability(key)
	return Link.render({ kind = "ability", stablekey = key })
end

local function resolveAbility(key, isSkill)
	local module = isSkill and require("Module:Erenshor/Skill") or require("Module:Erenshor/Spell")
	local record = module.resolve({ stablekey = key })
	if record.missing then
		error("ItemData references missing ability: " .. tostring(key), 2)
	end
	return record
end

local function classParam(name)
	return name == "Windblade" and "duelist" or string.lower(name)
end

local function classFlags(row, args)
	for _, class in ipairs(row.classes or {}) do
		args[classParam(class)] = "True"
	end
end

local function standardStats(row)
	for _, stats in ipairs(row.stats or {}) do
		if stats.quality == "Standard" then
			return stats
		end
	end
	return (row.stats or {})[1] or {}
end

local function effectStyle(effect, row)
	if effect.kind == "weaponProc" or effect.kind == "wandEffect" or effect.kind == "bowEffect" then
		if (effect.chance or 0) <= 0 then
			return nil
		end
	end
	if effect.kind == "weaponProc" then
		if effect.trigger then
			return effect.trigger
		end
		if row.slot == "Bracer" then
			return "Cast"
		end
		if row.shield then
			return "Bash"
		end
		if row.slot == "Primary" or row.slot == "Secondary" or row.slot == "PrimaryOrSecondary" then
			return "Attack"
		end
		return nil
	end
	if effect.trigger == "Click" then
		return "Activatable"
	end
	if effect.trigger == "Learn" then
		return EFFECT_LABELS[effect.kind]
	end
	return effect.trigger or EFFECT_LABELS[effect.kind] or effect.kind
end

local function spellArgs(frame, effect)
	local spell = resolveAbility(effect.spellKey, false)
	local args =
		{ spell_name = ability(effect.spellKey), spell_icon = p.existingFile(frame, spell.icon) }
	for source, target in pairs(SPELL_FIELDS) do
		args[target] = value(spell[source])
	end
	args.spell_duration_ticks = value((spell.durationSeconds or 0) / 3)
	if spell.castTimeSeconds and spell.castTimeSeconds ~= 0 then
		args.cast_time = string.format("%.1f", spell.castTimeSeconds)
	end
	if spell.statusEffectStableKey then
		args.status_effect_name = ability(spell.statusEffectStableKey)
	end
	if spell.addProcStableKey then
		args.add_proc_name = ability(spell.addProcStableKey)
	end
	if spell.line == "XPBonus" then
		args.xp_bonus = value(Quality.roundToInt((spell.xpBonus or 0) * 100))
	end
	args.spell_desc = p.description(spell.description)
	return args
end

local function prefixArgs(args, fields, prefix)
	for key, v in pairs(fields) do
		args[prefix .. "_" .. key] = v
	end
end

function p.effectDetails(frame, row, effect)
	local style = effectStyle(effect, row)
	if effect.skillKey then
		local Skill = require("Module:Erenshor/Skill")
		return '<div class="item-spell-details"><div class="item-spell-details-header">'
			.. Format.escape(style)
			.. "</div>"
			.. Skill.renderTooltip({ stablekey = effect.skillKey })
			.. "</div>"
	end
	local args = spellArgs(frame, effect)
	args.worn = (style == "Worn" or style == "Aura") and "1" or "0"
	args.proc_header = style .. ":"
	if effect.chance ~= nil then
		args.proc_header = tostring(effect.chance) .. "% chance on " .. string.upper(style) .. ":"
	end
	return frame:expandTemplate({ title = "Item/SpellDetails", args = args })
end

function p.recipeLinks(rows)
	local out = {}
	for _, row in ipairs(rows or {}) do
		out[#out + 1] = tostring(row.quantity or 1) .. "x " .. Link.render(row.link)
	end
	return table.concat(out, "<br />")
end

function p.render(frame, row)
	local stats = standardStats(row)
	local args = {
		name = row.name,
		icon = p.existingFile(frame, row.icon),
		slot = row.slot or "",
		description = p.description(row.description),
		value = (row.buyValue or 0) > 0 and not row.noTradeNoDestroy and tostring(row.buyValue)
			or "Unsellable",
		relic = value(row.relic),
		disposable = value(row.disposable),
		must_equip = value(row.mustBeEquippedToClick),
	}
	classFlags(row, args)
	local template = ({
		weapon = "Weapon",
		armor = "Armor",
		charm = "Charm",
		aura = "Aura",
		spellscroll = "SpellScroll",
		skillbook = "SkillBook",
		consumable = "Consumable",
		mold = "Mold",
		cosmetic = "General",
		general = "General",
	})[row.kind]
	if template == nil then
		error("Unsupported ItemData kind: " .. tostring(row.kind), 2)
	end
	local effects = {}
	for _, effect in ipairs(row.effects or {}) do
		if
			effect.kind ~= "teachesSpell"
			and effect.kind ~= "teachesSkill"
			and effectStyle(effect, row)
		then
			effects[#effects + 1] = effect
		end
	end
	local primary = effects[1]
	local extras = {}
	if primary and primary.spellKey then
		local prefix = template == "Aura" and "aura"
			or ((template == "Weapon" or template == "Armor") and "proc" or "effect")
		local fields = spellArgs(frame, primary)
		prefixArgs(args, fields, prefix)
		args[prefix .. "_style"] = effectStyle(primary, row)
		args[prefix .. "_chance"] = value(primary.chance)
		if template == "Aura" then
			args.aura_spell_desc = fields.spell_desc
		end
	end
	for index, effect in ipairs(effects) do
		if
			index > 1
			or not effect.spellKey
			or (
				template ~= "Weapon"
				and template ~= "Armor"
				and template ~= "Aura"
				and template ~= "General"
				and template ~= "Consumable"
			)
		then
			extras[#extras + 1] = p.effectDetails(frame, row, effect)
		end
	end
	if template == "Weapon" or template == "Armor" then
		if stats.quality == nil then
			error("ItemData equipment has no stats: " .. row.stableKey, 2)
		end
		for source, target in pairs(STAT_NAMES) do
			args[target] = stats[source] or 0
		end
		if mw.ustring.len(row.name) > 24 then
			args.name = '<span style="font-size:20px">' .. row.name .. "</span>"
		end
		args.kind = template
		args.type = tostring(row.slot or ""):gsub("PrimaryOrSecondary", "Primary or Secondary")
		if row.weaponType == "TwoHandMelee" or row.weaponType == "TwoHandStaff" then
			args.type = args.type .. " - 2-Handed"
		end
		args.two_handed = (
			row.weaponType == "TwoHandMelee"
			or row.weaponType == "TwoHandStaff"
			or row.weaponType == "TwoHandBow"
		)
				and "True"
			or ""
		if (stats.weaponDamage or 0) > 0 and (row.weaponDelay or 0) > 0 then
			args.delay = row.weaponDelay
			args.range = row.wand and row.wandRange or (row.bow and row.bowRange or 1)
		end
		return ParameterizedTooltip.renderArgs(frame, args, table.concat(extras, "\n"))
	elseif template == "Charm" then
		for _, name in ipairs({ "str", "end", "dex", "agi", "int", "wis", "cha" }) do
			args[name .. "scaling"] = value(Quality.roundToInt(stats[name .. "Scaling"] or 0))
		end
		args.resistscaling = value(Quality.roundToInt(stats.resistScaling or 0))
		args.mitigationscaling = value(Quality.roundToInt(stats.mitigationScaling or 0))
	elseif template == "Mold" then
		args.ingredients = p.recipeLinks(row.ingredients)
		args.rewards = p.recipeLinks(row.rewards)
		args.station = row.station or ""
	elseif template == "SpellScroll" then
		if row.teachesSpell then
			local spell = resolveAbility(row.teachesSpell, false)
			for _, class in ipairs(row.classes or {}) do
				args[classParam(class) .. "_level"] = value(spell.requiredLevel)
			end
			args.mana_cost = value(spell.manaCost)
			args.spell_type = spell.type or ""
			args.spell_desc = p.description(spell.description)
			extras[#extras + 1] = '<div class="item-spell-details">'
				.. require("Module:Erenshor/Spell").renderTooltip({ stablekey = row.teachesSpell })
				.. "</div>"
		end
	elseif template == "SkillBook" then
		if row.teachesSkill then
			local skill = resolveAbility(row.teachesSkill, true)
			for _, class in ipairs(skill.classLevels or {}) do
				args[classParam(class.className) .. "_level"] = value(class.level)
			end
			args.skill_type = skill.type or ""
			args.skill_desc = p.description(skill.description)
			args.simplayers_autolearn = skill.simPlayersAutolearn and "true" or "false"
			extras[#extras + 1] = '<div class="item-spell-details">'
				.. require("Module:Erenshor/Skill").renderTooltip({ stablekey = row.teachesSkill })
				.. "</div>"
		end
	end
	return frame:expandTemplate({ title = "Item/" .. template, args = args })
		.. table.concat(extras, "\n")
end

function p.effectLinks(row)
	local out = {}
	for _, effect in ipairs(row.effects or {}) do
		local style = effectStyle(effect, row)
		if style then
			out[#out + 1] = style .. ": " .. ability(effect.spellKey or effect.skillKey)
		end
	end
	return table.concat(out, "<br />")
end

return p
