using System.Collections.Generic;

namespace FixtureLib
{
    public class FixtureItemOperations
    {
        public void Grants(string operation)
        {
            switch (operation)
            {
                case "Break Fossil":
                {
                    Item selectedFossil = GameData.Misc.FossilGame[
                        Random.Range(0, GameData.Misc.FossilGame.Count)
                    ];
                    UpdateSocialLog.LogAdd("A fossil opens");
                    if (!GameData.PlayerInv.AddItemToInv(selectedFossil))
                    {
                        GameData.PlayerInv.ForceItemToInv(selectedFossil);
                    }
                    break;
                }
                case "Offering Stone":
                    if (!GameData.PlayerInv.AddItemToInv(GameData.ItemDB.GetItemByID("340104")))
                    {
                        GameData.PlayerInv.ForceItemToInv(GameData.ItemDB.GetItemByID("340104"));
                    }
                    break;
                case "Other":
                    UpdateSocialLog.LogAdd("Other operation");
                    break;
                default:
                    UpdateSocialLog.LogAdd("Unknown operation");
                    break;
            }
        }

        public class Item { }

        public class MiscData
        {
            public List<Item> FossilGame = new List<Item>();
        }

        public class Inventory
        {
            public bool AddItemToInv(Item item) => false;

            public void ForceItemToInv(Item item) { }
        }

        public class ItemDatabase
        {
            public Item GetItemByID(string id) => new Item();
        }

        public static class GameData
        {
            public static MiscData Misc = new MiscData();
            public static Inventory PlayerInv = new Inventory();
            public static ItemDatabase ItemDB = new ItemDatabase();
        }

        public static class Random
        {
            public static int Range(int minimum, int maximum) => minimum;
        }

        public static class UpdateSocialLog
        {
            public static void LogAdd(string message) { }
        }
    }
}
