characters:

has_modify_faction
  faction modifications are applied when a character is killed
  the exact changes are stored in `modify_factions`

my_world_faction vs my_faction
  both are factions the character belongs to
  world faction is more about heritage (kinda "which area of the world is the character originally from")
  faction is more about attitude (good vs. evil type of stuff, related to allies and agression)
  world faction is the Factions.REFNAME
    
ER is ELEMENTAL resistance, not energy resistance
VR is VOID resistance, not vitality resistance

the ability relationships are, unfortunately, not as clean as they should be in the DB
if you use the junction tables, you should be fine with IDs
but the (legacy) fields in the characters table itself still contain all kinds of weird combinations of values 
=> USE THE DATA FROM THE JUNCTION TABLES

proc on hit is a PERCENTAGE value (0-100)

for items for sale, as with the abilties, legacy fields are not ideal
=> USE THE DATA FROM THE JUNCTION TABLES

---

factions:

factions do NOT represent guilds!
what's displayed in-game is usually the faction description (not the name)

---

items:

item level only is a rough representation of how powerful an item is
it is not tied to any character level requirements -> all characters can equip items of all levels

shield is a boolean (basically "is_shield"")

weapon proce chance is a percentage value (0-100)
wand proce chance is a percentage value (0-100)
bow proc chance is a percentage value (0-100)

item_effect_on_click triggers a _spell_ when right-clicking the item
item_skill_use triggers a _skill_ when right-clicking the item
aura can ONLY contain spells (never skills)
worn_effect can ONLY contain spells (never skills)

item_value is basically the cost to BUY from a vendor
sell_value is how much you get when SELLING to a vendor
disposable marks whether an item is CONSUMED when clicking it
relic marks whether multiple of the same item can be equipped at once (e.g., 2x the same ring, 2x the same weapon in main+offhand) (relic -> can only equip one, non-relic -> can equip multiple)
unique marks whether duplicates of an item drop when the player already has the item in their inventory (unique -> item won't drop again, non-unique -> item will drop again)
mining is the mining power of an item (only used for pickaxes, but not currently tied to any in-game mechanics)
equipment_to_active determines which model will be shown on the player character when equipping the item

---

loot tables:

character_prefab_guid is kinda misleading; non-prefab characters also have guids, though prefab and non-prefab characters have different GUID formats
drop_probability is a PERCENTAGE (0-100)
is_actual -> if true, the item always drops on kill
is_guaranteed -> one of the guaranteed items always drops on kill (NOT all of them)
is_unique -> item only drops if it's not already in the player's inventory (NOT a rarity class)
is_visible -> when true, shows the item on the dropping character's model when it drops (i.e., you know that the item will drop if the character is wearing it)

---

quests:

required_item_ids actualy uses comma-separated "Small Cat Statue (24575054), ..."
=> USE THE DATA FROM THE JUNCTION TABLES
complete_other_quest_db_names, assign_new_quest_on_complete_db_name -> use a format like "Destroying Aragath (Aragath2)", i.e., "QuestName (DBName)"
affected_factions -> "Fernalla, Sivakayans", i.e., "Factions.REFNAME, ..."

---

skills:

effect_to_apply_id -> can only contain spell IDs
automate_attack -> causes the character to start auto-attacking when used
player_uses -> message shown in the combat log when skill is used by the player
npc_uses -> message shown in the combat log when skill is used by an npc

---

spawn points:

spawn_delay_1-4: respawn delay when the player is in a group with 1-2/3/4 simplayers (i.e., group size 2-3/4/5)

---

spells:

spell_decs and special_descriptor are both just descriptions of the spell that are shown at different places in the UI
energy_resist -> elemental_resist
vitality_resist -> void_resist
damage_shield -> basically a thorns effect (how much damage attackers take)
automate_attack -> causes the character to start auto-attacking when used
status_effect_message_on_player -> message shown in the combat log when used on the player
status_effect_message_on_npc -> message shown in the combat log when used on an npc

---

zones:

not sure why you're including all the coordinate columns here (character_id, door_id, etc.)?
please remove those. zones are defined by ZoneAnnounces and, to some degree, ZoneAtlasEntries
ZoneLines show connections to other zones

---

others:

seems like entities don't contain item stats anywhere (table: ItemStats)

