local ParameterizedTooltip = require("Module:Erenshor/Item/ParameterizedTooltip")
local Quality = require("Module:Erenshor/Item/Quality")

local p = {}

local function assertEqual(actual, expected, label)
	if actual ~= expected then
		error(
			string.format("%s: expected %s, got %s", label, tostring(expected), tostring(actual)),
			2
		)
	end
end

local function assertContains(actual, expected, label)
	if string.find(actual, expected, 1, true) == nil then
		error(string.format("%s: expected output to contain %s", label, expected), 2)
	end
end

local function assertAbsent(actual, unexpected, label)
	if string.find(actual, unexpected, 1, true) ~= nil then
		error(string.format("%s: unexpected output containing %s", label, unexpected), 2)
	end
end

local function countOccurrences(actual, expected)
	local count = 0
	local position = 1
	while true do
		local start = string.find(actual, expected, position, true)
		if start == nil then
			return count
		end
		count = count + 1
		position = start + #expected
	end
end

local function renderParameterized(input)
	local args = input.args or input
	local child = mw.getCurrentFrame():newChild({ title = "ParameterizedTooltip", args = args })
	return ParameterizedTooltip.render(child)
end

local function assertVariantFields(actual, expected, label, keys)
	keys = keys
		or {
			"str",
			"end",
			"dex",
			"agi",
			"int",
			"wis",
			"cha",
			"res",
			"weaponDamage",
			"hp",
			"mana",
			"ac",
			"mr",
			"er",
			"pr",
			"vr",
		}
	assertEqual(#actual, #expected, label .. " has all qualities")
	for index, expectedVariant in ipairs(expected) do
		assertEqual(actual[index].quality, expectedVariant.quality, label .. " quality " .. index)
		for _, key in ipairs(keys) do
			assertEqual(
				actual[index][key],
				expectedVariant[key],
				label .. " " .. expectedVariant.quality .. " " .. key
			)
		end
	end
end

function p.run()
	assertEqual(
		Quality.canonicalName(" standard "),
		"Standard",
		"quality canonicalization trims whitespace"
	)
	assertEqual(
		Quality.canonicalName("standard"),
		"Standard",
		"quality canonicalization ignores case"
	)
	assertEqual(Quality.canonicalName("Normal"), nil, "legacy Normal quality alias is rejected")
	assertEqual(
		Quality.canonicalName("normal"),
		nil,
		"lowercase legacy normal quality alias is rejected"
	)
	assertEqual(Quality.canonicalName("0"), nil, "numeric zero quality alias is rejected")
	assertEqual(
		Quality.canonicalName("Not a quality"),
		nil,
		"unknown quality canonicalization fails closed"
	)
	assertEqual(Quality.roundToInt(1.5), 2, "Unity rounding rounds 1.5 up")
	assertEqual(#Quality.variants({}), 8, "released mode enables all quality variants")
	assertEqual(#Quality.variants({}, true), 8, "Planar March mode enables all variants")

	local modeBase = {
		str = 25,
		hp = 225,
		mana = 200,
		ac = 10,
		mr = 10,
		res = 1,
		weaponDamage = 38,
	}
	local legacyVariants = Quality.variants(modeBase, false)
	assertEqual(legacyVariants[2].str, 37, "legacy Blessed primary stat uses one-half scaling")
	assertEqual(legacyVariants[2].hp, 281, "legacy Blessed health uses one-quarter scaling")
	assertEqual(legacyVariants[2].ac, 12, "legacy Blessed armor uses one-quarter scaling")
	assertEqual(legacyVariants[2].mr, 11, "legacy Blessed resist uses the CalcRes increment")
	assertEqual(legacyVariants[3].mr, 12, "legacy Ascended resist uses the CalcRes increment")
	assertEqual(legacyVariants[3].hp, 337, "legacy Ascended health uses one-half scaling")
	assertEqual(legacyVariants[3].ac, 15, "legacy Ascended armor uses one-half scaling")
	assertEqual(legacyVariants[2].res, 2, "legacy Blessed resonance gains one")
	assertEqual(legacyVariants[3].weaponDamage, 40, "legacy Ascended damage is unchanged")

	local planarVariants = Quality.variants(modeBase, true)
	assertEqual(planarVariants[7].str, 36, "Planar March Blessed primary stat uses new scaling")
	assertEqual(planarVariants[7].hp, 300, "Planar March Blessed health uses new scaling")
	assertEqual(planarVariants[7].ac, 15, "Planar March Blessed armor uses new scaling")
	assertEqual(planarVariants[7].mr, 14, "Planar March Blessed resist uses new scaling")
	assertEqual(planarVariants[7].quality, "Blessed", "Planar March preserves progression order")
	assertEqual(planarVariants[6].hp, 250, "Planar March Improved +5 health uses new scaling")
	assertEqual(planarVariants[6].mr, 11, "Planar March Improved +5 preserves resist edge case")
	assertEqual(planarVariants[7].res, 2, "Planar March Blessed resonance gains one")
	assertEqual(planarVariants[8].weaponDamage, 40, "Planar March Ascended damage is unchanged")

	assertVariantFields(
		Quality.variants(
			{ ac = 2, hp = 0, mana = 0, res = 0, mr = 0, er = 0, pr = 0, vr = 0 },
			true
		),
		{
			{
				quality = "Standard",
				str = 0,
				["end"] = 0,
				dex = 0,
				agi = 0,
				int = 0,
				wis = 0,
				cha = 0,
				res = 0,
				weaponDamage = 0,
				hp = 0,
				mana = 0,
				ac = 2,
				mr = 0,
				er = 0,
				pr = 0,
				vr = 0,
			},
			{
				quality = "Improved +1",
				str = 0,
				["end"] = 0,
				dex = 0,
				agi = 0,
				int = 0,
				wis = 0,
				cha = 0,
				res = 0,
				weaponDamage = 0,
				hp = 5,
				mana = 5,
				ac = 3,
				mr = 0,
				er = 0,
				pr = 0,
				vr = 0,
			},
			{
				quality = "Improved +2",
				str = 0,
				["end"] = 0,
				dex = 0,
				agi = 0,
				int = 0,
				wis = 0,
				cha = 0,
				res = 0,
				weaponDamage = 0,
				hp = 10,
				mana = 10,
				ac = 4,
				mr = 0,
				er = 0,
				pr = 0,
				vr = 0,
			},
			{
				quality = "Improved +3",
				str = 0,
				["end"] = 0,
				dex = 0,
				agi = 0,
				int = 0,
				wis = 0,
				cha = 0,
				res = 0,
				weaponDamage = 0,
				hp = 15,
				mana = 15,
				ac = 5,
				mr = 1,
				er = 1,
				pr = 1,
				vr = 1,
			},
			{
				quality = "Improved +4",
				str = 0,
				["end"] = 0,
				dex = 0,
				agi = 0,
				int = 0,
				wis = 0,
				cha = 0,
				res = 0,
				weaponDamage = 0,
				hp = 20,
				mana = 20,
				ac = 6,
				mr = 1,
				er = 1,
				pr = 1,
				vr = 1,
			},
			{
				quality = "Improved +5",
				str = 0,
				["end"] = 0,
				dex = 0,
				agi = 0,
				int = 0,
				wis = 0,
				cha = 0,
				res = 0,
				weaponDamage = 0,
				hp = 25,
				mana = 25,
				ac = 7,
				mr = 1,
				er = 1,
				pr = 1,
				vr = 1,
			},
			{
				quality = "Blessed",
				str = 0,
				["end"] = 0,
				dex = 0,
				agi = 0,
				int = 0,
				wis = 0,
				cha = 0,
				res = 1,
				weaponDamage = 0,
				hp = 30,
				mana = 30,
				ac = 5,
				mr = 1,
				er = 1,
				pr = 1,
				vr = 1,
			},
			{
				quality = "Ascended",
				str = 0,
				["end"] = 0,
				dex = 0,
				agi = 0,
				int = 0,
				wis = 0,
				cha = 0,
				res = 2,
				weaponDamage = 0,
				hp = 50,
				mana = 50,
				ac = 10,
				mr = 3,
				er = 3,
				pr = 3,
				vr = 3,
			},
		},
		"armor oracle",
		{
			"str",
			"end",
			"dex",
			"agi",
			"int",
			"wis",
			"cha",
			"res",
			"hp",
			"mana",
			"ac",
			"mr",
			"er",
			"pr",
			"vr",
		}
	)
	assertVariantFields(
		Quality.variants({
			weaponDamage = 38,
			hp = 225,
			mana = 200,
			ac = 0,
			str = 25,
			dex = 30,
			agi = 15,
			int = 20,
			res = 1,
			mr = 0,
			er = 0,
			pr = 0,
			vr = 0,
		}, true),
		{
			{
				quality = "Standard",
				str = 25,
				["end"] = 0,
				dex = 30,
				agi = 15,
				int = 20,
				wis = 0,
				cha = 0,
				res = 1,
				weaponDamage = 38,
				hp = 225,
				mana = 200,
				ac = 0,
				mr = 0,
				er = 0,
				pr = 0,
				vr = 0,
			},
			{
				quality = "Improved +1",
				str = 26,
				["end"] = 0,
				dex = 31,
				agi = 16,
				int = 21,
				wis = 0,
				cha = 0,
				res = 1,
				weaponDamage = 38,
				hp = 230,
				mana = 205,
				ac = 0,
				mr = 0,
				er = 0,
				pr = 0,
				vr = 0,
			},
			{
				quality = "Improved +2",
				str = 26,
				["end"] = 0,
				dex = 31,
				agi = 16,
				int = 21,
				wis = 0,
				cha = 0,
				res = 1,
				weaponDamage = 38,
				hp = 235,
				mana = 210,
				ac = 0,
				mr = 0,
				er = 0,
				pr = 0,
				vr = 0,
			},
			{
				quality = "Improved +3",
				str = 27,
				["end"] = 0,
				dex = 32,
				agi = 17,
				int = 22,
				wis = 0,
				cha = 0,
				res = 1,
				weaponDamage = 38,
				hp = 240,
				mana = 215,
				ac = 0,
				mr = 1,
				er = 1,
				pr = 1,
				vr = 1,
			},
			{
				quality = "Improved +4",
				str = 27,
				["end"] = 0,
				dex = 32,
				agi = 17,
				int = 22,
				wis = 0,
				cha = 0,
				res = 1,
				weaponDamage = 38,
				hp = 245,
				mana = 220,
				ac = 0,
				mr = 1,
				er = 1,
				pr = 1,
				vr = 1,
			},
			{
				quality = "Improved +5",
				str = 28,
				["end"] = 0,
				dex = 33,
				agi = 18,
				int = 23,
				wis = 0,
				cha = 0,
				res = 1,
				weaponDamage = 38,
				hp = 250,
				mana = 225,
				ac = 0,
				mr = 1,
				er = 1,
				pr = 1,
				vr = 1,
			},
			{
				quality = "Blessed",
				str = 36,
				["end"] = 0,
				dex = 43,
				agi = 23,
				int = 30,
				wis = 0,
				cha = 0,
				res = 2,
				weaponDamage = 39,
				hp = 300,
				mana = 270,
				ac = 3,
				mr = 1,
				er = 1,
				pr = 1,
				vr = 1,
			},
			{
				quality = "Ascended",
				str = 50,
				["end"] = 0,
				dex = 60,
				agi = 30,
				int = 40,
				wis = 0,
				cha = 0,
				res = 3,
				weaponDamage = 40,
				hp = 387,
				mana = 350,
				ac = 8,
				mr = 3,
				er = 3,
				pr = 3,
				vr = 3,
			},
		},
		"weapon oracle"
	)

	local armorTooltip = renderParameterized({
		args = {
			kind = "Armor",
			icon = "Cloth Sleeves icon.png",
			name = "Cloth Sleeves",
			slot = "Arm",
			armor = "2",
			health = "0",
			mana = "0",
			res = "0",
			magic = "0",
			poison = "0",
			elemental = "0",
			void = "0",
		},
	})
	assertEqual(
		countOccurrences(armorTooltip, 'class="item-tooltip item-tooltip-armor"'),
		8,
		"Planar March mode emits all eight armor quality variants"
	)
	for _, quality in ipairs({
		"Standard",
		"Improved +1",
		"Improved +2",
		"Improved +3",
		"Improved +4",
		"Improved +5",
		"Blessed",
		"Ascended",
	}) do
		assertContains(armorTooltip, quality, "armor output labels " .. quality)
	end
	assertEqual(
		countOccurrences(armorTooltip, 'data-erenshor-quality="Standard"'),
		1,
		"parameterized Standard quality metadata is exact"
	)
	assertEqual(
		countOccurrences(armorTooltip, 'data-erenshor-quality="Blessed"'),
		1,
		"parameterized Blessed quality metadata is exact"
	)
	assertContains(
		armorTooltip,
		"item-tooltip-quality-sparkle-improved",
		"Planar March mode renders Improved sparkles"
	)
	assertContains(
		armorTooltip,
		'item-tooltip-stat-value">3</span>',
		"Planar March Ascended armor uses released scaling"
	)

	local nonAttackingRelic = renderParameterized({
		args = {
			kind = "Weapon",
			icon = "Siva-Braxonian Teachings icon.png",
			name = "Siva-Braxonian Teachings",
			type = "Primary or Secondary",
			relic = "True",
			damage = "",
			delay = "",
			str = "5",
			int = "25",
		},
	})
	assertAbsent(nonAttackingRelic, "Base DPS:", "non-attacking equipment hides DPS")
	assertAbsent(
		nonAttackingRelic,
		"Expression error",
		"non-attacking equipment does not evaluate blank attack operands"
	)
	assertAbsent(
		nonAttackingRelic,
		'item-tooltip-stat-label">Damage</',
		"non-attacking equipment hides synthetic zero damage"
	)

	local weaponTooltipFromParams = renderParameterized({
		args = {
			kind = "Weapon",
			icon = "Oldenbow icon.png",
			name = "Oldenbow",
			type = "Primary",
			damage = "38",
			delay = "2",
			health = "225",
			mana = "200",
			str = "25",
			dex = "30",
			agi = "15",
			int = "20",
			res = "1",
			proc_chance = "25",
			proc_style = "Cast",
			proc_spell_icon = "Ice Spear icon.png",
			proc_spell_name = "Ember Burst",
		},
	})
	assertEqual(
		countOccurrences(weaponTooltipFromParams, 'class="item-tooltip item-tooltip-weapon"'),
		8,
		"Planar March mode emits all eight weapon quality variants"
	)
	assertContains(
		weaponTooltipFromParams,
		"Improved +1",
		"Planar March mode renders Improved weapon variants"
	)
	assertContains(
		weaponTooltipFromParams,
		'item-tooltip-stat-value">38</span>',
		"Standard weapon damage remains unchanged"
	)
	assertContains(
		weaponTooltipFromParams,
		'item-tooltip-stat-value">39</span>',
		"Blessed weapon damage gains one"
	)
	assertContains(
		weaponTooltipFromParams,
		'item-tooltip-stat-value">40</span>',
		"Ascended weapon damage gains two"
	)
	assertContains(
		weaponTooltipFromParams,
		"25% chance on CAST:",
		"weapon proc metadata is preserved"
	)
	assertContains(
		weaponTooltipFromParams,
		"Ice Spear icon.png",
		"proc spell icon receives a MediaWiki filename"
	)
	assertAbsent(weaponTooltipFromParams, "Healing: 0", "zero healing is omitted")
	assertAbsent(weaponTooltipFromParams, "Shield Amount: 0", "zero shielding is omitted")
	assertAbsent(weaponTooltipFromParams, "XP Bonus: +0.0%", "zero XP bonus is omitted")
	assertAbsent(weaponTooltipFromParams, "{{Item/", "legacy invocations are fully expanded")
	assertAbsent(weaponTooltipFromParams, "{{{", "no unguarded template parameters leak")
	local displayReadyTooltip = renderParameterized({
		args = {
			kind = "Weapon",
			icon = "Oldenbow icon.png",
			name = "Oldenbow",
			type = "Primary - 2-Handed",
			damage = "38",
			delay = "2",
			proc_style = "Attack",
			proc_chance = "8",
			proc_spell_icon = "Ice Spear icon.png",
			proc_spell_name = "[[Ice Spear]]",
			proc_spell_level = "21",
			proc_cast_time = "1.0",
		},
	})
	assertContains(
		displayReadyTooltip,
		"Ice Spear icon.png",
		"display-ready icon filename passes through"
	)
	assertAbsent(
		displayReadyTooltip,
		"Ice Spear icon.png.png",
		"icon extension is not appended twice"
	)
	assertContains(
		displayReadyTooltip,
		"[[Ice Spear]]",
		"pre-linked spell name passes through unchanged"
	)
	assertContains(displayReadyTooltip, "Cast Time: 1.0 sec", "cast time is already in seconds")
	assertContains(displayReadyTooltip, "Primary - 2-Handed", "two-handed weapon type renders")
	assertAbsent(armorTooltip, "{{Item/", "armor invocations are fully expanded")
	assertAbsent(armorTooltip, "{{{", "no unguarded armor parameters leak")
	local customImageTooltip = renderParameterized({
		args = { kind = "Armor", icon = "Manual.webp", name = "Manual", armor = "1" },
	})
	assertContains(customImageTooltip, "Manual.webp", "custom image extensions are preserved")
	local missingIconTooltip = renderParameterized({
		args = { kind = "Armor", name = "No Icon", armor = "1", tier = "1" },
	})
	assertAbsent(missingIconTooltip, "erenshor-icon", "an item with no icon draws no frame")
	assertAbsent(missingIconTooltip, "{{{", "an item with no icon leaks no parameter")

	return "PASS Erenshor Item/ParameterizedTooltip testcases"
end

return p
