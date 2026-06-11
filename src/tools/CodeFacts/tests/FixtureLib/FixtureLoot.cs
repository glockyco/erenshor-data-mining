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

        public bool Auctionable(int level, int value)
        {
            return level > 0 && level < 40 && value > 0;
        }
    }
}
