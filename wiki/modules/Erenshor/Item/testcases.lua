local Item = require("Module:Erenshor/Item")
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
	local currentFrame = mw.getCurrentFrame()
	local args = input.args or input
	return ParameterizedTooltip.render({
		args = args,
		expandTemplate = function(_, specification)
			return currentFrame:expandTemplate(specification)
		end,
		callParserFunction = function(_, name, values)
			return currentFrame:callParserFunction(name, values)
		end,
		preprocess = function(_, source)
			return currentFrame:preprocess(source)
		end,
	})
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
	assertEqual(Quality.roundToInt(1.5), 2, "Unity rounding rounds 1.5 up")
	assertEqual(#Quality.variants({}), 3, "release gate hides Improved variants")
	assertEqual(#Quality.variants({}, true), 8, "quality gate enables all variants")

	assertVariantFields(
		Quality.variants(
			{ ac = 2, hp = 0, mana = 0, res = 0, mr = 0, er = 0, pr = 0, vr = 0 },
			true
		),
		{
			{
				quality = "Normal",
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
				quality = "Normal",
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
		3,
		"release gate emits Normal, Blessed, and Ascended armor variants"
	)
	for _, quality in ipairs({
		"Normal",
		"Blessed",
		"Ascended",
	}) do
		assertContains(armorTooltip, quality, "armor output labels " .. quality)
	end
	assertAbsent(armorTooltip, "Improved +1", "release gate hides Improved armor variants")
	assertAbsent(
		armorTooltip,
		"item-tooltip-quality-sparkle-improved",
		"release gate hides Improved sparkles"
	)
	assertContains(
		armorTooltip,
		'item-tooltip-stat-value">10</span>',
		"Ascended armor uses the game maximum"
	)

	local weaponTooltipFromParams = renderParameterized({
		args = {
			kind = "Weapon",
			image = "Oldenbow",
			name = "Oldenbow",
			type = "Primary",
			damage = "38",
			health = "225",
			mana = "200",
			str = "25",
			dex = "30",
			agi = "15",
			int = "20",
			res = "1",
			proc_chance = "25",
			proc_style = "Cast",
			proc_spell_name = "Ember Burst",
		},
	})
	assertEqual(
		countOccurrences(weaponTooltipFromParams, 'class="item-tooltip item-tooltip-weapon"'),
		3,
		"release gate emits Normal, Blessed, and Ascended weapon variants"
	)
	assertAbsent(
		weaponTooltipFromParams,
		"Improved +1",
		"release gate hides Improved weapon variants"
	)
	assertContains(
		weaponTooltipFromParams,
		'item-tooltip-stat-value">38</span>',
		"Normal weapon damage remains unchanged"
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
	local customImageTooltip = renderParameterized({
		args = { kind = "Armor", image = "Manual.webp", name = "Manual", armor = "1" },
	})
	assertContains(customImageTooltip, "Manual.webp", "custom image extensions are preserved")

	local weapon = Item.resolve({ stablekey = "item:ember_longsword" }, "Anything")
	assertEqual(weapon.name, "Ember Longsword", "stable key resolves item")
	assertEqual(weapon.type, "Weapon", "weapon type resolves")
	assertEqual(weapon.damage, 18, "weapon damage resolves")

	local pageWeapon = Item.resolve({}, "Ember Longsword")
	assertEqual(pageWeapon.missing, true, "page title does not resolve item without stable key")

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

	local weaponTooltip =
		Item.renderTooltip({ stablekey = "item:ember_longsword" }, "Ember Longsword")
	assertContains(
		weaponTooltip,
		"item-tooltip-weapon",
		"weapon tooltip carries the weapon CSS class"
	)
	assertContains(weaponTooltip, "Ember Longsword", "weapon tooltip shows the item name")
	assertContains(weaponTooltip, "item-tooltip-tier-0", "weapon tooltip colors the Normal quality")
	assertContains(
		weaponTooltip,
		"item-tooltip-tier-2",
		"weapon tooltip colors the Ascended quality"
	)
	if string.find(weaponTooltip, "Ascended", 1, true) ~= nil then
		error("weapon tooltip must not expose the Ascended quality label", 2)
	end
	assertContains(weaponTooltip, "Base DPS:", "weapon tooltip shows base DPS")
	assertContains(weaponTooltip, "Paladin", "weapon tooltip shows class restrictions")
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
	assertContains(stableKeyLink, "[[Abyssal Plate]]", "stable key link uses generated page")
	assertContains(
		stableKeyLink,
		"[[File:Abyssal Plate.png",
		"stable key link uses generated image"
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
