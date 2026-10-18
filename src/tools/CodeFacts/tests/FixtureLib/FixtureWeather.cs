namespace FixtureLib
{
    public sealed class FixtureWeather
    {
        public bool isRaining;
        public float ColorWeight;
        public float SinceRain;
        public Light Sun = new Light();
        public string spell = "";

        public void RainStart()
        {
            if (!isRaining && ColorWeight > 0.55f && Sun.enabled && SinceRain <= 0f)
                isRaining = true;
        }

        public void RainWithoutSun()
        {
            if (!isRaining && ColorWeight > 0.55f && SinceRain <= 0f)
                isRaining = true;
        }

        public void WeatherSpells()
        {
            switch (spell)
            {
                case "Invoke Storm":
                    GameData.Atmos.SinceRain = -1f;
                    GameData.Atmos.WeightGoal = 0.9f;
                    GameData.Atmos.CloudAmt = 0.4f;
                    break;
                case "Dissipate Storm":
                    GameData.Atmos.WeightGoal = 0f;
                    GameData.Atmos.CloudAmt = 0.1f;
                    break;
                case "Other":
                    GameData.Atmos.CloudAmt = 0.3f;
                    break;
                default:
                    GameData.Atmos.CloudAmt = 0.2f;
                    break;
            }
        }

        public void ChangedSpell()
        {
            switch (spell)
            {
                case "Invoke Storm":
                    GameData.Atmos.SinceRain = -1f;
                    GameData.Atmos.WeightGoal = ColorWeight + 0.9f;
                    GameData.Atmos.CloudAmt = 0.4f;
                    break;
                case "Dissipate Storm":
                    GameData.Atmos.WeightGoal = 0f;
                    break;
                case "Other":
                    GameData.Atmos.CloudAmt = 0.3f;
                    break;
                default:
                    GameData.Atmos.CloudAmt = 0.2f;
                    break;
            }
        }

        public sealed class Light
        {
            public bool enabled;
        }

        private static class GameData
        {
            public static readonly Atmosphere Atmos = new Atmosphere();
        }

        private sealed class Atmosphere
        {
            public float SinceRain;
            public float WeightGoal;
            public float CloudAmt;
        }
    }
}
