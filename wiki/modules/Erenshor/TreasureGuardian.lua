local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")

local p = {}

local DASH = "–"

local function data()
	return mw.loadData("Module:Erenshor/Data/TreasureGuardians")
end

local function grouped(value)
	local text = tostring(value)
	local count
	repeat
		text, count = text:gsub("^(%d+)(%d%d%d)", "%1,%2")
	until count == 0
	return text
end

local function range(minValue, maxValue, formatter)
	formatter = formatter or tostring
	if minValue == maxValue then
		return formatter(minValue)
	end
	return formatter(minValue) .. DASH .. formatter(maxValue)
end

-- The swing delay counts down 60 ticks per second.
local function delaySeconds(ticks)
	local text = string.format("%.2f", ticks / 60):gsub("0+$", ""):gsub("%.$", "")
	return text
end

local function percent(chance)
	return string.format("%d%%", math.floor(chance * 100 + 0.5))
end

local function joinList(items)
	if #items <= 1 then
		return items[1] or ""
	end
	if #items == 2 then
		return items[1] .. " and " .. items[2]
	end
	return table.concat(items, ", ", 1, #items - 1) .. ", and " .. items[#items]
end

local function guardianLinks(guardians)
	local links = {}
	for _, guardian in ipairs(guardians) do
		table.insert(links, Format.pageLink(guardian.page, guardian.name))
	end
	return joinList(links)
end

local function countText(minValue, maxValue)
	if minValue == maxValue then
		return tostring(minValue)
	end
	if maxValue == minValue + 1 then
		return minValue .. " or " .. maxValue
	end
	return minValue .. " to " .. maxValue
end

local function plural(count, word)
	return count == 1 and (count .. " " .. word) or (count .. " " .. word .. "s")
end

-- code-fact: treasure.strike_melee
-- code-fact: treasure.strike_bolt
-- code-fact: treasure.wave_blocked_while_guarded
local function waveText(source)
	local first = source.waves[1]
	return "When a player attacks a dug-up [[Treasure Hunting|treasure chest]] with a melee weapon, a wand, or a bow, "
		.. "and none of its guardians is alive, the ground rumbles for "
		.. Format.seconds(first.nextWaveDelaySeconds)
		.. ". Then "
		.. countText(first.nextWaveGuardiansMin, first.nextWaveGuardiansMax)
		.. " guardians appear, chosen at random from "
		.. guardianLinks(source.guardians)
		.. ". Their level and stats follow the level of the attacking player."
end

-- code-fact: treasure.chest_immune.damage
local function breakText(source)
	local safeWaves = 0
	local chances = {}
	for _, wave in ipairs(source.waves) do
		if wave.strikeBreakChance <= 0 then
			safeWaves = wave.wavesSpawned + 1
		else
			table.insert(
				chances,
				percent(wave.strikeBreakChance) .. " after " .. plural(wave.wavesSpawned, "wave")
			)
		end
	end
	return "The chest never takes damage, but each attack can break it open: never before "
		.. plural(safeWaves, "wave")
		.. " have appeared, and then with a chance of "
		.. joinList(chances)
		.. ", even while guardians are alive."
end

local function statsTable(rows)
	local out = {
		'{| class="wikitable sortable"',
		"|+ Stats by the level of the attacking player",
		"! Player level !! Level !! Health !! Base damage !! Base attack delay !! AC !! Each resist",
	}
	for _, row in ipairs(rows) do
		table.insert(out, "|-")
		table.insert(
			out,
			table.concat({
				"| " .. row.playerLevel,
				range(row.levelMin, row.levelMax),
				range(row.healthMin, row.healthMax, grouped),
				range(row.attackMin, row.attackMax),
				range(row.attackDelayMin, row.attackDelayMax, delaySeconds) .. " s",
				range(row.acMin, row.acMax),
				range(row.resistMin, row.resistMax),
			}, " || ")
		)
	end
	table.insert(out, "|}")
	return table.concat(out, "\n")
end

local function missingOutput(stableKey)
	return '<span class="erenshor-missing-data">Missing treasure guardian data: '
		.. Format.escape(stableKey or "")
		.. "</span>[[Category:Pages with missing Erenshor treasure guardian data]]"
end

function p.render(args)
	local stableKey = Args.resolve(args or {}, "stablekey", nil)
	local source = data()
	local rows = stableKey and source.scaling[stableKey]
	if rows == nil then
		return missingOutput(stableKey)
	end
	return waveText(source) .. "\n\n" .. breakText(source) .. "\n\n" .. statsTable(rows)
end

function p.stats(frame)
	return p.render(Args.parentArgs(frame))
end

return p
