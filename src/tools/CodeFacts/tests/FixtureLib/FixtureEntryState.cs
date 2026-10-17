namespace FixtureLib
{
    public class FixtureEntryState
    {
        public bool Ready;

        public void Play()
        {
            GameData.GM.LoadReliquary();
            Prepare();
            GameData.InCharSelect = false;
        }

        public void PlayAlternate()
        {
            Prepare();
            GameData.GM.LoadReliquary();
            GameData.InCharSelect = false;
            Prepare();
        }

        public void Reversed()
        {
            GameData.InCharSelect = false;
            GameData.GM.LoadReliquary();
        }

        public void MissingLoad()
        {
            GameData.InCharSelect = false;
        }

        public void MissingEntry()
        {
            GameData.GM.LoadReliquary();
        }

        public void DuplicateLoad()
        {
            GameData.GM.LoadReliquary();
            GameData.GM.LoadReliquary();
            GameData.InCharSelect = false;
        }

        public void DuplicateEntry()
        {
            GameData.GM.LoadReliquary();
            GameData.InCharSelect = false;
            Prepare();
            GameData.InCharSelect = false;
        }

        public void ConditionalLoad()
        {
            if (Ready)
            {
                GameData.GM.LoadReliquary();
            }
            GameData.InCharSelect = false;
        }

        public void ConditionalEntry()
        {
            GameData.GM.LoadReliquary();
            if (Ready)
            {
                GameData.InCharSelect = false;
            }
        }

        public void NestedDuplicateLoad()
        {
            GameData.GM.LoadReliquary();
            if (Ready)
            {
                GameData.GM.LoadReliquary();
            }
            GameData.InCharSelect = false;
        }

        public void NestedDuplicateEntry()
        {
            GameData.GM.LoadReliquary();
            GameData.InCharSelect = false;
            if (Ready)
            {
                GameData.InCharSelect = false;
            }
        }

        public void LambdaDuplicateLoad()
        {
            GameData.GM.LoadReliquary();
            Prepare(() =>
            {
                GameData.GM.LoadReliquary();
            });
            GameData.InCharSelect = false;
        }

        private void Prepare() { }

        private void Prepare(System.Action action)
        {
            action();
        }

        public sealed class Manager
        {
            public void LoadReliquary() { }
        }

        public static class GameData
        {
            public static Manager GM = new Manager();
            public static bool InCharSelect;
        }
    }
}
