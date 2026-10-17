return {
	["item:arm - 19  - ancient guardian sleeve"] = {
		references = {
			["character:captain_rowan"] = {
				key = "character:captain_rowan",
				name = "Captain Rowan",
				page = "Captain Rowan",
			},
			['character:captain  rowan "copy" & <test>'] = {
				key = 'character:captain  rowan "copy" & <test>',
				name = "Captain Rowan",
			},
			["zone:PortAzure"] = {
				key = "zone:PortAzure",
				name = "Port Azure",
				page = "Port Azure",
			},
			["item:arm - 19  - ancient guardian sleeve"] = {
				key = "item:arm - 19  - ancient guardian sleeve",
				name = "Ancient Guardian Sleeve",
				page = "ItemData Key Fixture",
			},
			["item:furniture - stone training"] = {
				key = "item:furniture - stone training",
				name = "Stone Training Set",
				page = "Stone Training Set",
			},
		},
		["acquisitions"] = {
			{
				["acquisition_key"] = "acq:key  fixture",
				["conditions"] = {
					{
						["atom_index"] = 0,
						["gate_key"] = "key-input",
						["group_index"] = 0,
						["minimum"] = 1,
						["phase"] = "operation_input",
						["predicate"] = "item_held",
						["reference_stable_key"] = "item:arm - 19  - ancient guardian sleeve",
						["scope"] = 'scope  "input" & <test>',
					},
					{
						["atom_index"] = 0,
						["gate_key"] = "key-room",
						["group_index"] = 0,
						["phase"] = "availability",
						["predicate"] = "room_furnished",
						["reference_slot"] = "L1",
						["reference_stable_key"] = "item:furniture - stone training",
						["scope"] = "source",
					},
				},
				["evidence"] = {},
				["item_stable_key"] = "item:arm - 19  - ancient guardian sleeve",
				["kind"] = "vendor",
				["locations"] = {
					{
						["conditions"] = {},
						["entry_zone_line_keys"] = {
							'zone_line:entry  "one" & <test>',
						},
						["gate_scope"] = 'gate  "scope" & <test>',
						["location_key"] = 'location  "quoted" & <test>',
						["relation"] = "fixed",
						["x"] = 1,
						["y"] = 2,
						["z"] = 3,
						["zone_stable_key"] = "zone:PortAzure",
					},
				},
				["player_access_state"] = "verified_player",
				["probability_kind"] = "not_applicable",
				["probability_stage"] = "final_acquisition",
				["quantity_kind"] = "exact",
				["quantity_max"] = 1,
				["quantity_min"] = 1,
				["source_copy_stable_key"] = 'character:captain  rowan "copy" & <test>',
				["source_group_key"] = "character:captain_rowan",
				["source_stable_key"] = "character:captain_rowan",
				["variant_key"] = 'variant  "quoted" & <test>',
			},
		},
		["disposition"] = {
			["disposition"] = "current",
			["item_stable_key"] = "item:arm - 19  - ancient guardian sleeve",
		},
		["uses"] = {},
	},
}
