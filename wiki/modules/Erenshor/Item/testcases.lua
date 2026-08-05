local Item = require("Module:Erenshor/Item")
local ParameterizedTooltip = require("Module:Erenshor/Item/ParameterizedTooltip")
local Quality = require("Module:Erenshor/Item/Quality")
local Tooltip = require("Module:Erenshor/Item/Tooltip")

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

local function qualityCard(actual, quality)
	local marker = 'data-erenshor-quality="' .. quality .. '"'
	local start = string.find(actual, marker, 1, true)
	if start == nil then
		error("quality card is missing " .. quality, 2)
	end
	local nextStart = string.find(actual, 'data-erenshor-quality="', start + #marker, true)
	return string.sub(actual, start, (nextStart or (#actual + 1)) - 1)
end

local function statFragment(label, value)
	return 'item-tooltip-stat-label">'
		.. label
		.. '</span><span class="item-tooltip-stat-value">'
		.. tostring(value)
		.. "</span>"
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
			image = "Cloth Sleeves.png",
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
			image = "Siva-Braxonian Teachings.png",
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
			image = "Oldenbow",
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
			proc_spell_icon = "Ice Spear",
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
		"Ice Spear.png",
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
			image = "Oldenbow.png",
			name = "Oldenbow",
			type = "Primary - 2-Handed",
			damage = "38",
			delay = "2",
			proc_style = "Attack",
			proc_chance = "8",
			proc_spell_icon = "Ice Spear.png",
			proc_spell_name = "[[Ice Spear]]",
			proc_spell_level = "21",
			proc_cast_time = "1.0",
		},
	})
	assertContains(
		displayReadyTooltip,
		"Ice Spear.png",
		"display-ready icon filename passes through"
	)
	assertAbsent(displayReadyTooltip, "Ice Spear.png.png", "icon extension is not appended twice")
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
		args = { kind = "Armor", image = "Manual.webp", name = "Manual", armor = "1" },
	})
	assertContains(customImageTooltip, "Manual.webp", "custom image extensions are preserved")

	local weapon = Item.resolve({ stablekey = "item:ember_longsword" }, "Anything")
	assertEqual(weapon.name, "Ember Longsword", "stable key resolves item")
	assertEqual(weapon.type, "Weapon", "weapon type resolves")
	assertEqual(weapon.damage, 18, "weapon damage resolves")
	local encodedWeapon = Item.resolve({ encodedstablekey = "item%3Aember_longsword" }, "Anything")
	assertEqual(encodedWeapon.name, "Ember Longsword", "percent-decoded stable key resolves item")
	local rawKeyPrecedence = Item.resolve({
		stablekey = "item:ember_longsword",
		encodedstablekey = "item%3Aabyssal_plate",
	}, "Anything")
	assertEqual(rawKeyPrecedence.name, "Ember Longsword", "raw stable key takes precedence")

	local pageWeapon = Item.resolve({}, "Ember Longsword")
	assertEqual(pageWeapon.missing, true, "page title does not resolve item without stable key")

	local sharedCommon =
		Item.resolve({ stablekey = "item:shared-page-common" }, "Shared Item Fixture")
	local sharedRare = Item.resolve({ stablekey = "item:shared-page-rare" }, "Shared Item Fixture")
	assertEqual(
		sharedCommon.stableKey,
		"item:shared-page-common",
		"common stable key remains distinct"
	)
	assertEqual(sharedRare.stableKey, "item:shared-page-rare", "rare stable key remains distinct")
	assertEqual(
		sharedCommon.name,
		"Shared Item Fixture",
		"common record keeps the shared page name"
	)
	assertEqual(sharedRare.name, "Shared Item Fixture", "rare record keeps the shared page name")
	assertEqual(sharedCommon.page, sharedRare.page, "shared records intentionally use one page")
	assertEqual(
		sharedCommon.description,
		"COMMON identity fixture",
		"common stable key resolves its description"
	)
	assertEqual(
		sharedRare.description,
		"RARE identity fixture",
		"rare stable key resolves its description"
	)
	local sharedCommonTooltip =
		Item.renderTooltip({ stablekey = "item:shared-page-common" }, "Shared Item Fixture")
	local sharedRareTooltip =
		Item.renderTooltip({ stablekey = "item:shared-page-rare" }, "Shared Item Fixture")
	assertContains(
		sharedCommonTooltip,
		"COMMON identity fixture",
		"common stable key renders its marker"
	)
	assertAbsent(
		sharedCommonTooltip,
		"RARE identity fixture",
		"common tooltip excludes rare marker"
	)
	assertContains(sharedRareTooltip, "RARE identity fixture", "rare stable key renders its marker")
	assertAbsent(
		sharedRareTooltip,
		"COMMON identity fixture",
		"rare tooltip excludes common marker"
	)

	local override = Item.resolve({
		stablekey = "item:ember_longsword",
		image = "Manual.png",
		othersource = "Quest reward",
		slot = "Secondary",
		itemlevel = "13",
	}, "Ember Longsword")
	assertEqual(override.image, "Manual.png", "article image override wins")
	assertEqual(override.othersource, "Quest reward", "manual source override wins")
	assertEqual(override.slot, "Secondary", "article slot override wins")
	assertEqual(override.itemLevel, "13", "article item level override wins")

	local blanked =
		Item.resolve({ stablekey = "item:ember_longsword", image = "-" }, "Ember Longsword")
	assertEqual(blanked.image, nil, "dash sentinel blanks supported fields")

	local weaponKey = { stablekey = "item:ember_longsword" }
	assertEqual(
		Item.fieldValue(weaponKey, "Ember Longsword", "name"),
		"Ember Longsword",
		"field name resolves"
	)
	assertEqual(
		Item.fieldValue(weaponKey, "Ember Longsword", "damage"),
		"18",
		"field damage resolves"
	)
	assertEqual(
		Item.fieldValue(weaponKey, "Ember Longsword", "buy"),
		"12500",
		"field buy renders the raw gold value"
	)
	assertContains(
		Item.fieldValue(weaponKey, "Ember Longsword", "classes"),
		'data-erenshor-key="class:duelist"',
		"generated item classes carry stable class identity"
	)
	assertContains(
		Item.fieldValue(weaponKey, "Ember Longsword", "classes"),
		'data-erenshor-page="Windblade"',
		"generated item classes use canonical class page"
	)

	local cargo = Item.cargoArgs({ args = { stablekey = "item:abyssal_plate" } })
	assertEqual(cargo.Armor, "40", "cargo store contains armor overview AC")
	assertEqual(cargo.Classes, "Paladin,Warrior", "cargo store contains plain class names")
	local classRender = Item.classLinks({ args = { "Paladin,Warrior" } })
	assertContains(classRender, "erenshor-link--class", "classLinks renders semantic class links")
	assertContains(classRender, "[[Paladin]]", "classLinks renders Paladin link")
	assertEqual(
		cargo.WornEffectKey,
		"spell:minor_lightning",
		"cargo store contains worn ability stable key"
	)
	local wornNotes = Item.overviewNotes({ args = { stablekey = "item:abyssal_plate" } })
	assertContains(wornNotes, "Worn: ", "overview notes include worn prefix")
	assertContains(
		wornNotes,
		"erenshor-link--ability",
		"overview notes render semantic worn ability link"
	)
	assertContains(wornNotes, "[[Minor Lightning]]", "overview notes render worn ability page")
	local wornTooltip = Item.renderTooltip(
		{ stablekey = "item:abyssal_plate", quality = "Standard" },
		"Abyssal Plate"
	)
	assertContains(wornTooltip, "Resonance ", "item effect tooltip includes game resonance row")
	assertContains(wornTooltip, "+30", "item effect tooltip includes resonance value")
	assertAbsent(wornTooltip, "24px", "item effect link omits its duplicate ability icon")

	local weaponCargo = Item.cargoArgs({ args = { stablekey = "item:ember_longsword" } })
	assertEqual(weaponCargo.WeaponType, "OneHandMelee", "cargo store contains weapon subtype")
	assertEqual(weaponCargo.Damage, "18", "cargo store contains normal weapon damage")
	assertEqual(weaponCargo.Delay, "2.5", "cargo store contains weapon delay")
	assertEqual(
		weaponCargo.WeaponProcKey,
		"spell:ember_proc",
		"cargo store contains weapon proc stable key"
	)
	assertEqual(weaponCargo.WeaponProcChance, "20", "cargo store contains weapon proc chance")
	local procNotes = Item.overviewNotes({ args = { stablekey = "item:ember_longsword" } })
	assertContains(
		procNotes,
		"erenshor-link--ability",
		"overview notes render semantic weapon proc link"
	)
	assertContains(procNotes, "[[Ember Burst]]", "overview notes render weapon proc page")
	assertContains(procNotes, "20% on attack", "overview notes render proc chance and trigger")
	local scrollCargo = Item.cargoArgs({ args = { stablekey = "item:scroll_of_ember" } })
	assertEqual(
		scrollCargo.TeachesSpellKey,
		"spell:ember",
		"cargo store contains taught spell stable key"
	)
	local manualCargo = Item.cargoArgs({ args = { stablekey = "item:sword_mastery_manual" } })
	assertEqual(
		manualCargo.TeachesSkillKey,
		"skill:sword_mastery",
		"cargo store contains taught skill stable key"
	)
	local draughtCargo = Item.cargoArgs({ args = { stablekey = "item:healing_draught" } })
	assertEqual(
		draughtCargo.ClickEffectKey,
		"spell:minor_heal",
		"cargo store contains click effect stable key"
	)
	local auraCargo = Item.cargoArgs({ args = { stablekey = "item:ember_aura" } })
	assertEqual(auraCargo.AuraKey, "spell:ancient_presence", "cargo store contains aura stable key")
	local obtained = Item.cargoObtainedFromRows({ args = { stablekey = "item:magical_bag" } })
	assertEqual(#obtained, 3, "obtainedFrom rows cover every source")
	assertEqual(obtained[1].ItemKey, "item:magical_bag", "obtainedFrom carries item key")
	assertEqual(obtained[1].SourceType, "drop", "obtainedFrom stores source type")
	assertEqual(obtained[1].SourceKey, "character:a_grizzly_bear", "obtainedFrom stores source key")
	assertEqual(obtained[1].Probability, "12.5", "obtainedFrom stores probability")
	assertEqual(obtained[1].IsGuaranteed, "yes", "obtainedFrom stores guaranteed flag")
	assertEqual(obtained[2].SourceType, "fishing", "obtainedFrom stores fishing source type")
	assertEqual(
		obtained[2].SourceKey,
		"water:brake:287.10:7.50:247.80",
		"obtainedFrom preserves the water identity"
	)
	assertEqual(obtained[2].SourceCondition, "day", "obtainedFrom stores fishing condition")
	assertEqual(obtained[2].IsGuaranteed, "no", "obtainedFrom leaves fishing unguaranteed")
	assertEqual(obtained[3].SourceType, "starting", "obtainedFrom stores starting source type")
	assertEqual(obtained[3].SourceKey, "class:Arcanist", "obtainedFrom stores starting source key")
	local used = Item.cargoUsedInRows({ args = { stablekey = "item:magical_bag" } })
	assertEqual(#used, 2, "usedIn rows cover every usage")
	assertEqual(used[1].ItemKey, "item:magical_bag", "usedIn carries item key")
	assertEqual(used[1].UseType, "craft_material", "usedIn stores craft usage type")
	assertEqual(
		used[1].TargetKey,
		"item:template - copper armor mold",
		"usedIn stores craft target"
	)
	assertEqual(used[1].Quantity, "2", "usedIn stores craft quantity")
	assertEqual(used[1].Slot, "1", "usedIn stores craft slot")
	assertEqual(used[2].UseType, "quest_requirement", "usedIn stores quest usage type")
	assertEqual(used[2].TargetKey, "quest:an ore for the forge", "usedIn stores quest target")
	assertEqual(used[2].Quantity, "1", "usedIn stores quest quantity")
	assertEqual(used[2].Slot, nil, "usedIn omits nullable quest slot")
	assertEqual(
		Item.fieldValue({ stablekey = "item:healing_draught" }, "Healing Draught", "disposable"),
		"Yes",
		"consumable disposable field renders Yes"
	)
	assertEqual(
		Item.fieldValue({ stablekey = "item:ember_longsword" }, "Ember Longsword", "dps"),
		"8",
		"weapon dps is computed from base damage and delay"
	)
	local procEffect =
		Item.fieldValue({ stablekey = "item:ember_longsword" }, "Ember Longsword", "proceffect")
	assertContains(
		procEffect,
		"erenshor-link--ability",
		"weapon proc effect renders semantic ability link"
	)
	assertContains(procEffect, "[[Ember Burst]]", "weapon proc effect renders linked ability page")
	local wornEffect =
		Item.fieldValue({ stablekey = "item:abyssal_plate" }, "Abyssal Plate", "worneffect")
	assertContains(
		wornEffect,
		"erenshor-link--ability",
		"worn effect renders semantic ability link"
	)
	assertContains(wornEffect, "[[Minor Lightning]]", "worn effect renders linked ability page")
	local clickEffect =
		Item.fieldValue({ stablekey = "item:healing_draught" }, "Healing Draught", "effect")
	assertContains(
		clickEffect,
		"erenshor-link--ability",
		"activatable effect renders semantic ability link"
	)
	assertContains(clickEffect, "[[Minor Heal]]", "activatable effect renders linked ability page")
	local taughtSpell =
		Item.fieldValue({ stablekey = "item:scroll_of_ember" }, "Scroll of Ember", "taughtspell")
	assertContains(
		taughtSpell,
		"erenshor-link--ability",
		"taught spell renders semantic ability link"
	)
	assertContains(taughtSpell, "[[Ember]]", "taught spell renders linked ability page")
	local taughtSkill = Item.fieldValue(
		{ stablekey = "item:sword_mastery_manual" },
		"Sword Mastery Manual",
		"taughtskill"
	)
	assertContains(
		taughtSkill,
		"erenshor-link--ability",
		"taught skill renders semantic ability link"
	)
	assertContains(taughtSkill, "[[Sword Mastery]]", "taught skill renders linked ability page")
	assertEqual(
		Item.fieldValue({ stablekey = "item:scroll_of_ember" }, "Scroll of Ember", "spelltype"),
		"Damage",
		"spell scroll type derives from taught spell data"
	)
	assertEqual(
		Item.fieldValue(
			{ stablekey = "item:sword_mastery_manual" },
			"Sword Mastery Manual",
			"skilltype"
		),
		"Passive",
		"skill book type derives from taught skill data"
	)
	local produces =
		Item.fieldValue({ stablekey = "item:copper_armor_mold" }, "Copper Armor Mold", "produces")
	assertContains(produces, "1x ", "produces includes quantity")
	assertContains(produces, "erenshor-link--item", "produces renders semantic item link")
	assertContains(
		produces,
		"[[Copper Breastplate]]",
		"produces maps to generated crafting rewards"
	)
	assertEqual(
		Item.fieldValue(
			{ stablekey = "item:healing_draught", disposable = "no" },
			"Healing Draught",
			"disposable"
		),
		"",
		"non-consumable disposable row hides like live"
	)

	local stableLegacyItem = Item.resolve({ stablekey = "item:ember_longsword" }, "Ember Longsword")
	assertEqual(
		#stableLegacyItem.stats,
		3,
		"stable-key fixture starts with three legacy quality rows"
	)
	local stableLegacyTooltip =
		Item.renderTooltip({ stablekey = "item:ember_longsword" }, "Ember Longsword")
	assertEqual(
		countOccurrences(stableLegacyTooltip, 'class="item-tooltip item-tooltip-weapon"'),
		8,
		"stable-key legacy rows expand to exactly eight quality cards"
	)
	local previousQualityPosition = 0
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
		local marker = 'data-erenshor-quality="' .. quality .. '"'
		local markerPosition = string.find(stableLegacyTooltip, marker, 1, true)
		if markerPosition == nil or markerPosition <= previousQualityPosition then
			error("stable-key qualities are not in canonical progression order", 2)
		end
		previousQualityPosition = markerPosition
		assertEqual(
			countOccurrences(stableLegacyTooltip, marker),
			1,
			"stable-key quality card appears once: " .. quality
		)
	end
	local expectedImproved = {
		{ quality = "Improved +1", str = 6, dex = 3, mr = 3 },
		{ quality = "Improved +2", str = 6, dex = 3, mr = 3 },
		{ quality = "Improved +3", str = 7, dex = 4, mr = 4 },
		{ quality = "Improved +4", str = 7, dex = 4, mr = 4 },
		{ quality = "Improved +5", str = 8, dex = 5, mr = 4 },
	}
	for _, expected in ipairs(expectedImproved) do
		local quality = expected.quality
		local card = qualityCard(stableLegacyTooltip, quality)
		assertContains(
			card,
			statFragment("Str", expected.str),
			quality .. " derives Standard strength"
		)
		assertContains(
			card,
			statFragment("Dex", expected.dex),
			quality .. " derives Standard dexterity"
		)
		assertContains(
			card,
			statFragment("Magic", "+" .. expected.mr .. "%"),
			quality .. " derives Standard magic resist"
		)
	end
	assertContains(
		qualityCard(stableLegacyTooltip, "Blessed"),
		statFragment("Str", 8),
		"exported Blessed strength is preserved verbatim"
	)
	assertContains(
		qualityCard(stableLegacyTooltip, "Blessed"),
		statFragment("Damage", 23),
		"exported Blessed damage is preserved verbatim"
	)
	assertContains(
		qualityCard(stableLegacyTooltip, "Ascended"),
		statFragment("Str", 10),
		"exported Ascended strength is preserved verbatim"
	)
	assertContains(
		qualityCard(stableLegacyTooltip, "Ascended"),
		statFragment("Damage", 28),
		"exported Ascended damage is preserved verbatim"
	)
	local explicitImprovedTooltip = Item.renderTooltip(
		{ stablekey = "item:ember_longsword", quality = "Improved +1" },
		"Ember Longsword"
	)
	assertEqual(
		countOccurrences(explicitImprovedTooltip, 'class="item-tooltip item-tooltip-weapon"'),
		1,
		"explicit derived Improved quality selects one stable-key card"
	)
	assertContains(
		explicitImprovedTooltip,
		statFragment("Str", 6),
		"explicit Improved +1 selection uses the derived row"
	)
	assertAbsent(
		explicitImprovedTooltip,
		"item-tooltip-quality-set",
		"explicit Improved selection omits quality wrapper"
	)

	local previousPlanarMarchEnabled = Quality.planarMarchEnabled
	local disabledOk, disabledTooltip = pcall(function()
		Quality.planarMarchEnabled = function()
			return false
		end
		return Item.renderTooltip({ stablekey = "item:ember_longsword" }, "Ember Longsword")
	end)
	Quality.planarMarchEnabled = previousPlanarMarchEnabled
	if not disabledOk then
		error(disabledTooltip, 2)
	end
	assertEqual(
		countOccurrences(disabledTooltip, 'class="item-tooltip item-tooltip-weapon"'),
		3,
		"disabled quality mode retains three legacy stable-key cards"
	)
	local weaponTooltip = stableLegacyTooltip
	assertContains(
		weaponTooltip,
		"item-tooltip-weapon",
		"weapon tooltip carries the weapon CSS class"
	)
	assertContains(weaponTooltip, "Ember Longsword", "weapon tooltip shows the item name")
	assertContains(
		weaponTooltip,
		"item-tooltip-tier-0",
		"weapon tooltip colors the Standard quality"
	)
	assertContains(
		weaponTooltip,
		"item-tooltip-tier-2",
		"weapon tooltip colors the Ascended quality"
	)
	if string.find(weaponTooltip, 'item-tooltip-quality-label">Ascended', 1, true) ~= nil then
		error("weapon tooltip must not render an Ascended quality label", 2)
	end
	assertContains(
		weaponTooltip,
		'data-erenshor-quality="Standard"',
		"weapon tooltip exposes Standard quality metadata"
	)
	assertContains(
		weaponTooltip,
		'data-erenshor-quality="Blessed"',
		"weapon tooltip exposes Blessed quality metadata"
	)
	assertContains(
		weaponTooltip,
		'data-erenshor-quality="Ascended"',
		"weapon tooltip exposes Ascended quality metadata"
	)
	assertContains(weaponTooltip, "Base DPS:", "weapon tooltip shows base DPS")
	assertContains(weaponTooltip, "Paladin", "weapon tooltip shows class restrictions")
	assertContains(
		weaponTooltip,
		'class="item-tooltip-class">Windblade',
		"weapon tooltip resolves the internal Duelist name to Windblade"
	)
	assertContains(
		weaponTooltip,
		"item-tooltip-two-column",
		"weapon tooltip uses the two-column body"
	)
	assertContains(weaponTooltip, "Vitals", "weapon tooltip shows the Vitals section")
	assertContains(weaponTooltip, "Resists", "weapon tooltip shows the Resists section")
	assertContains(weaponTooltip, "+0%", "weapon tooltip shows resists in +N% form")
	assertContains(
		weaponTooltip,
		"Slot: [[Weapons#Primary|Primary]]",
		"weapon shows the game slot prefix"
	)
	assertContains(weaponTooltip, "Range", "weapon shows the range row (melee = 1)")
	assertContains(
		weaponTooltip,
		"item-tooltip-quality-set",
		"weapon quality variants use a wrapping horizontal container"
	)
	assertContains(
		weaponTooltip,
		"flex-wrap:wrap",
		"weapon quality variants wrap when horizontal space is constrained"
	)
	assertContains(
		weaponTooltip,
		"width:calc(100% - 360px)",
		"weapon quality variants reserve horizontal space for the infobox"
	)
	assertContains(
		weaponTooltip,
		"min-width:350px",
		"weapon quality variants keep one full tooltip visible beside the infobox"
	)

	local standardOnlyTooltip = Item.renderTooltip(
		{ stablekey = "item:ember_longsword", quality = " standard " },
		"Ember Longsword"
	)
	assertEqual(
		countOccurrences(standardOnlyTooltip, 'class="item-tooltip item-tooltip-weapon"'),
		1,
		"explicit Standard selection renders one card"
	)
	assertContains(
		standardOnlyTooltip,
		"item-tooltip-tier-0",
		"explicit Standard selection renders Standard"
	)
	assertAbsent(
		standardOnlyTooltip,
		"item-tooltip-quality-set",
		"explicit Standard selection omits quality wrapper"
	)
	local blessedOnlyTooltip = Item.renderTooltip(
		{ stablekey = "item:ember_longsword", quality = " blessed " },
		"Ember Longsword"
	)
	assertEqual(
		countOccurrences(blessedOnlyTooltip, 'class="item-tooltip item-tooltip-weapon"'),
		1,
		"explicit Blessed selection renders one card"
	)
	assertContains(
		blessedOnlyTooltip,
		"item-tooltip-tier-1",
		"explicit Blessed selection renders Blessed"
	)
	assertAbsent(
		blessedOnlyTooltip,
		"item-tooltip-quality-set",
		"explicit Blessed selection omits quality wrapper"
	)
	local encodedBlessedTooltip = Item.renderTooltip(
		{ stablekey = "item:ember_longsword", quality = "Blessed%20" },
		"Ember Longsword"
	)
	assertEqual(
		countOccurrences(encodedBlessedTooltip, 'class="item-tooltip item-tooltip-weapon"'),
		1,
		"encoded Blessed selection renders one card"
	)
	assertContains(
		encodedBlessedTooltip,
		"item-tooltip-tier-1",
		"encoded Blessed selection is decoded"
	)
	local encodedImprovedItem =
		Item.resolve({ stablekey = "item:ember_longsword" }, "Ember Longsword")
	encodedImprovedItem.stats = {
		{ quality = "Improved +3", weaponDamage = 18, str = 5, dex = 2, mr = 3 },
	}
	local encodedImprovedTooltip = Tooltip.render(encodedImprovedItem, "Improved%20%2B3")
	assertContains(
		encodedImprovedTooltip,
		"item-tooltip-tier-5",
		"encoded Improved selection is decoded"
	)
	assertAbsent(
		encodedImprovedTooltip,
		"item-tooltip-quality-set",
		"encoded Improved selection omits quality wrapper"
	)
	local invalidQualityOk, invalidQualityError = pcall(function()
		Item.renderTooltip(
			{ stablekey = "item:ember_longsword", quality = "Uncommon" },
			"Ember Longsword"
		)
	end)
	assertEqual(invalidQualityOk, false, "invalid item quality fails fast")
	assertContains(
		tostring(invalidQualityError),
		"Invalid item quality",
		"invalid quality error is useful"
	)
	local standardWithoutStats =
		Item.renderTooltip({ stablekey = "item:magical_bag", quality = "Standard" }, "Magical Bag")
	assertContains(
		standardWithoutStats,
		"item-tooltip-general",
		"Standard selection works when item has no explicit stats"
	)

	local clickArmor = Item.resolve({ stablekey = "item:abyssal_plate" }, "Abyssal Plate")
	clickArmor.wornEffect = nil
	clickArmor.clickEffect = "spell:minor_heal"
	local clickArmorTooltip = Tooltip.render(clickArmor, "Standard")
	assertContains(
		clickArmorTooltip,
		"Activatable: Minor Heal",
		"equipment click effect renders activatable name"
	)
	assertContains(
		clickArmorTooltip,
		"Right click or assign to hotkey to use.",
		"equipment click effect renders usage line"
	)
	assertContains(
		clickArmorTooltip,
		"item-spell-details",
		"equipment click effect renders spell details"
	)
	assertContains(
		clickArmorTooltip,
		"Healing: 150",
		"equipment click effect renders spell detail content"
	)

	local charm = Item.renderTooltip({ stablekey = "item:lucky_charm" }, "Lucky Charm")
	assertContains(charm, "item-tooltip-charm", "charm tooltip carries the charm CSS class")
	assertContains(charm, "Charm Item", "charm tooltip shows the charm label")
	assertContains(charm, "Arcanism: +10 / 40", "charm scaling uses the game attribute names")
	assertContains(weaponTooltip, "item-spell-details", "weapon proc shows spell details")
	assertContains(
		weaponTooltip,
		"20% chance on ATTACK:",
		"weapon proc header uses the game trigger style"
	)
	assertContains(
		weaponTooltip,
		"[[Ember Burst]]",
		"weapon proc spell name links without an inline icon"
	)
	assertContains(
		weaponTooltip,
		"[[File:Ember Burst.png|48px]]",
		"weapon proc spell box carries the spell icon"
	)
	if string.find(weaponTooltip, "{{AbilityLink|Ember Burst", 1, true) ~= nil then
		error("weapon proc spell name must not render through icon-bearing AbilityLink", 2)
	end
	if string.find(weaponTooltip, "[[File:Ember Burst.png|30px", 1, true) ~= nil then
		error("weapon proc spell name must not render an inline ability icon", 2)
	end

	local consumable = Item.renderTooltip({ stablekey = "item:healing_draught" }, "Healing Draught")
	assertContains(consumable, "item-tooltip-consumable", "consumable tooltip CSS class")
	assertContains(
		consumable,
		"Item Consumed Upon Use.",
		"disposable consumable shows the consumed notice"
	)
	assertContains(consumable, "Activatable: Minor Heal", "consumable shows the activatable effect")
	assertContains(consumable, "item-spell-details", "consumable shows spell details")
	assertContains(consumable, "Healing: 150", "consumable spell details show healing")

	local mold = Item.renderTooltip({ stablekey = "item:copper_armor_mold" }, "Copper Armor Mold")
	assertContains(mold, "Ingredients:", "mold tooltip shows ingredients")
	assertContains(mold, "Creates:", "mold tooltip shows created items")

	local aura = Item.renderTooltip({ stablekey = "item:ember_aura" }, "Ember Aura")
	assertContains(aura, "Aura Item", "aura tooltip shows the aura label")
	assertContains(aura, "Auras effect entire party", "aura tooltip shows the party note")
	assertContains(aura, "item-spell-details", "aura shows spell details")
	assertContains(aura, "Group Effect", "aura spell details show the group-effect flag")

	local skillBook =
		Item.renderTooltip({ stablekey = "item:sword_mastery_manual" }, "Sword Mastery Manual")
	assertContains(skillBook, "item-tooltip-book", "skill book carries the book CSS class")
	assertContains(skillBook, "Required Level:", "skill book shows the requirement header")
	assertContains(
		skillBook,
		"Windblade: 3",
		"skill book shows per-class levels with display names"
	)
	assertContains(skillBook, "Skill Type: Passive", "skill book shows the public skill type")
	assertContains(
		skillBook,
		"SimPlayers DO NOT automatically learn",
		"skill book warns when not auto-learned"
	)

	local spellScroll =
		Item.renderTooltip({ stablekey = "item:scroll_of_ember" }, "Scroll of Ember")
	assertContains(spellScroll, "item-tooltip-book", "spell scroll carries the book CSS class")
	assertContains(
		spellScroll,
		"Arcanist: 8",
		"spell scroll shows the required level per usable class"
	)
	assertContains(spellScroll, "Mana Cost: 25", "spell scroll shows the mana cost")
	assertContains(spellScroll, "Spell Type: Damage", "spell scroll shows the spell type")

	assertContains(weaponTooltip, "[[Category:Weapons]]", "weapon emits the weapon category")
	assertContains(weaponTooltip, "[[Category:Primary Weapons]]", "weapon emits the slot category")
	assertContains(
		weaponTooltip,
		"[[Category:Proc Items]]",
		"weapon proc emits the proc-effect category"
	)
	assertContains(charm, "[[Category:Charms]]", "charm emits the charm category")
	assertContains(mold, "[[Category:Molds]]", "mold emits the mold category")
	assertContains(
		skillBook,
		"[[Category:Skill Books]]",
		"skill book emits the skill book category"
	)
	assertContains(
		spellScroll,
		"[[Category:Spell Scrolls]]",
		"spell scroll emits the spell scroll category"
	)

	local link = Item.renderLink({ item = "Ember Longsword" }, "Any Page")
	assertContains(link, "[[Ember Longsword]]", "manual link defaults to item page")
	assertContains(link, "[[File:Ember Longsword.png", "manual link defaults image")

	local stableKeyLink = Item.renderLink({ stablekey = "item:abyssal_plate" }, "Ember Longsword")
	assertContains(stableKeyLink, "[[Ember Longsword]]", "stable key link keeps page fallback")
	assertContains(
		stableKeyLink,
		"[[File:Ember Longsword.png",
		"stable key link keeps image fallback"
	)
	assertContains(
		stableKeyLink,
		'data-erenshor-key="item:abyssal_plate"',
		"stable key link preserves identity metadata"
	)

	local imageOnly = Item.renderLink({ item = "Ember Longsword", imageonly = "yes" }, "Any Page")
	assertContains(imageOnly, "[[File:Ember Longsword.png", "image-only link keeps image")
	if string.find(imageOnly, "[[Ember Longsword", 1, true) ~= nil then
		error("image-only link must not append a text link", 2)
	end

	assertEqual(
		Item.fieldValue({}, "Unknown Prototype", "name"),
		"",
		"missing item fields are blank"
	)
	local missing = Item.statusText({}, "Unknown Prototype")
	assertContains(missing, "Missing item data: Unknown Prototype", "missing item is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor item data]]",
		"missing item is tracked"
	)

	return "PASS Erenshor Item testcases"
end

return p
