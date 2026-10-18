using System.Collections.Generic;

namespace FixtureLib
{
    public sealed class FixtureItemActions
    {
        public Item MyItem = new Item();
        public bool VendorSlot;
        public bool LootSlot;
        public Item.SlotType ThisSlotType;
        public Slot equipmentSlot = new Slot();
        public Slot equipmentSlot2 = new Slot();
        public int Used;

        public void Actions()
        {
            if (
                MyItem.Classes.Contains(GameData.PlayerStats.CharacterClass)
                || MyItem.Classes.Count == 0
            )
            {
                if (MyItem.TeachSpell != null && !VendorSlot && !LootSlot)
                {
                    Used += 2;
                    if (
                        MyItem.TeachSpell.RequiredLevel
                        <= GameData.PlayerControl.Myself.MyStats.Level
                    )
                    {
                        GameData
                            .PlayerControl.GetComponent<CastSpell>()
                            .KnownSpells.Add(MyItem.TeachSpell);
                    }
                    Used += 3;
                }
                equipmentSlot.MyItem = MyItem;
                equipmentSlot2.MyItem = MyItem;
                GameData.PlayerInv.AuraSlot.MyItem = MyItem;
            }
            if (!MyItem.MustBeEquippedToClick || ThisSlotType != Item.SlotType.General)
            {
                Used++;
                if (
                    MyItem.RequiredSlot == Item.SlotType.General
                    || MyItem.Classes.Contains(GameData.PlayerStats.CharacterClass)
                )
                {
                    UseConsumable();
                }
            }
        }

        private void UseConsumable()
        {
            Used++;
        }

        public sealed class Item
        {
            public enum SlotType
            {
                General,
                Ring,
            }

            public List<string> Classes = new List<string>();
            public Spell TeachSpell;
            public bool MustBeEquippedToClick;
            public SlotType RequiredSlot;
        }

        public sealed class Spell
        {
            public int RequiredLevel;
        }

        public sealed class Slot
        {
            public Item MyItem;
        }

        public sealed class Stats
        {
            public string CharacterClass;
            public int Level;
        }

        public sealed class Character
        {
            public Stats MyStats = new Stats();
        }

        public sealed class Player
        {
            public Character Myself = new Character();

            public T GetComponent<T>()
                where T : new()
            {
                return new T();
            }
        }

        public sealed class CastSpell
        {
            public List<Spell> KnownSpells = new List<Spell>();
        }

        public sealed class Inventory
        {
            public Slot AuraSlot = new Slot();
        }

        private static class GameData
        {
            public static Stats PlayerStats = new Stats();
            public static Player PlayerControl = new Player();
            public static Inventory PlayerInv = new Inventory();
        }
    }
}
