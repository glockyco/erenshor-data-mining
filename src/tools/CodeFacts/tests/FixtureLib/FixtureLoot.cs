using System;
using System.Collections.Generic;

namespace FixtureLib
{
    public class FixtureLoot
    {
        public List<string> PoolA = new List<string>();
        public List<string> Drops = new List<string>();
        public string SingletonB = "b";
        public int Level;
        private static readonly Random Rng = new Random();
        private static float Roll => (float)Rng.NextDouble();

        public void Init()
        {
            float rate = 2f;
            if (Roll < 0.005f * rate)
            {
                Drops.Add(PoolA[Rng.Next(0, PoolA.Count)]);
            }
            if (Level > 20 && Roll < 0.0125f * rate)
            {
                Drops.Add(SingletonB);
            }
        }

        public bool Combine(string template, string fuel)
        {
            return template == "31377423" && fuel == "46289586";
        }

        public void GuaranteeLike()
        {
            if (PoolA.Count > 0)
            {
                Drops.Add(PoolA[Rng.Next(0, PoolA.Count)]);
            }
        }

        public void GuaranteeRetryLike(int numberOfGuaranteedDrops)
        {
            for (int i = 0; i < numberOfGuaranteedDrops; i++)
            {
                string item = null;
                int attempts = 0;
                do
                {
                    item = PoolA[Rng.Next(0, PoolA.Count)];
                    attempts++;
                } while (attempts < 10 && (item == null || Drops.Contains(item)));
                if (item != null)
                {
                    Drops.Add(item);
                }
            }
        }

        public bool Auctionable(int level, int value)
        {
            return level > 0 && level < 40 && value > 0;
        }

        public int Scale(int value)
        {
            return value * 2;
        }

        public int Scale(int value, int factor)
        {
            return value * factor;
        }

        public void Recalculate(bool again)
        {
            Level++;
            if (again)
            {
                Level++;
            }
        }

        public bool AmbiguousBounds(int level) => level < 35 || level < 40;

        public void OffsetDraw(FixtureLoot empty, FixtureLoot stats)
        {
            do
            {
                SingletonB = empty.SingletonB;
            } while (Level > stats.Level + 3);
            if (stats.Level + 6 > 0)
            {
                Level++;
            }
        }

        public void BrokerNames(string name, out bool isAuctionHouse, out bool isBanker)
        {
            isAuctionHouse = false;
            isBanker = false;
            if (name == "Broker A" || name == "Broker B")
            {
                isAuctionHouse = true;
            }
            if (name == "Banker")
            {
                isBanker = true;
            }
        }

        public void LevelCap(int level)
        {
            if (level < 35)
            {
                Level++;
                if (level < 10)
                {
                    Level++;
                }
            }
        }

        public void Storage(bool compatible)
        {
            if (compatible)
            {
                Level++;
            }
            else
            {
                SingletonB = "stored";
            }
        }
    }
}
