namespace FixtureLib
{
    public sealed class FixtureFaction
    {
        public sealed class Standing
        {
            public float FactionValue;
        }

        public sealed class Slot
        {
            public string ItemName = "";
        }

        public sealed class Faction
        {
            public float Value;
        }

        public static class Factions
        {
            public static Faction FindFactionData(string name) => new Faction();
        }

        public Standing Mine = new Standing();
        public Slot Charm = new Slot();
        public string Reply = "";

        public void Threshold()
        {
            if (Mine.FactionValue < 0f)
                Reply = "...";
        }

        public void TwoThresholds()
        {
            if (Mine.FactionValue < 0f)
                Reply = "...";
            if (Mine.FactionValue < 5f)
                Reply = "!";
        }

        public void Override()
        {
            if (Charm.ItemName == "Pin")
                Factions.FindFactionData("School").Value = 10f;
            else
                Factions.FindFactionData("School").Value = -10f;
        }

        public void SplitOverride()
        {
            if (Charm.ItemName == "Pin")
                Factions.FindFactionData("School").Value = 10f;
            else
                Factions.FindFactionData("Other").Value = -10f;
        }

        public void ExtraOverride()
        {
            if (Charm.ItemName == "Pin")
            {
                Factions.FindFactionData("School").Value = 10f;
                Reply = "worn";
            }
            else
                Factions.FindFactionData("School").Value = -10f;
        }
    }
}
