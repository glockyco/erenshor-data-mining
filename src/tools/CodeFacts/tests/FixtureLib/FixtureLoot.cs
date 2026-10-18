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

        public void AssignString()
        {
            SingletonB = "start,scene";
        }

        public void AssignStringTwice(bool again)
        {
            SingletonB = "first";
            if (again)
                SingletonB = "second";
        }

        public void AssignNonliteral(string value)
        {
            SingletonB = value;
        }

        public void InvokeString()
        {
            Drops.Add("called");
        }

        public void InvokeStringTwice()
        {
            Drops.Add("first");
            Drops.Add("second");
        }

        public void InvokeNonliteral(string value)
        {
            Drops.Add(value);
        }

        public void CreateString()
        {
            Level = new Version("1.2").Major;
        }

        public void CreateNonliteral(string value)
        {
            Level = new Version(value).Major;
        }

        public void CreateStringTwice()
        {
            Level = new Version("1.2").Major + new Version("3.4").Major;
        }

        public void InvokeSecondString()
        {
            Drops.Insert(0, "inserted");
        }

        public void CreateSecondString()
        {
            SingletonB = new KeyValuePair<int, string>(7, "created").Value;
        }

        public void IteratePool()
        {
            foreach (var item in PoolA)
            {
                Drops.Add(item);
            }
        }

        public void IteratePoolTwice()
        {
            foreach (var item in PoolA)
            {
                Drops.Add(item);
            }
            foreach (var item in PoolA)
            {
                Drops.Remove(item);
            }
        }

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

        // Two bounds on one operand. The decompiler turns short-circuit forms into
        // inverted guards, so each bound is its own comparison.
        public bool AmbiguousBounds(int level)
        {
            bool belowLow = level < 35;
            bool belowHigh = level < 40;
            return belowLow != belowHigh;
        }

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

        public void ShiverGate(bool active)
        {
            if (!active && Drops.Contains("SHIVER-GLASSES"))
            {
                SingletonB = "visible";
            }
        }

        public void ShiverGateChangedLiteral(bool active)
        {
            if (!active && Drops.Contains("SHIVER-TORCH"))
            {
                SingletonB = "visible";
            }
        }

        public void ShiverGateChangedActivation(bool active)
        {
            if (!active && Drops.Contains("SHIVER-GLASSES"))
            {
                SingletonB = "hidden";
            }
        }

        public void ShiverReset()
        {
            if (Drops.Contains("SHIVER-TORCH"))
            {
                Level = 2;
            }
            if (Drops.Contains("SHIVER-FLAMELIT"))
            {
                Level = 3;
            }
        }

        public void ShiverResetChangedBranching()
        {
            if (Drops.Contains("SHIVER-TORCH"))
            {
                Level = 2;
            }
            else if (Drops.Contains("SHIVER-FLAMELIT"))
            {
                Level = 3;
            }
        }
    }
}
