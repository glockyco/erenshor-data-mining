namespace FixtureLib
{
    public sealed class FixtureTravel
    {
        public string spell = "";
        public float Timer;
        public bool Released;
        public System.Collections.Generic.List<string> Raiders =
            new System.Collections.Generic.List<string>();

        public void Spells()
        {
            switch (spell)
            {
                case "Portal to Windwashed":
                    GameData.Save();
                    GameData.SceneChange.ChangeScene(
                        "Windwashed",
                        new Vector3(755.27f, 66f, -474.4f),
                        _useSun: true,
                        90f
                    );
                    break;
                case "Returning Wish":
                    GameData.SceneChange.ChangeScene(
                        GameData.BindZone,
                        GameData.BindLoc,
                        GameData.SunInBindZone,
                        180f
                    );
                    break;
                case "Portal to Reliquary":
                    if (SceneManager.GetActiveScene().name == "Reliquary")
                    {
                        GameData.Save();
                        break;
                    }
                    if (GameData.usingSun)
                    {
                        GameData.Save();
                    }
                    GameData.SceneChange.ChangeScene(
                        "Reliquary",
                        new Vector3(275f, 1.82f, 309f),
                        _useSun: false,
                        0f
                    );
                    break;
                case "Dimensional Rift":
                    if (SceneManager.GetActiveScene().name == "Azynthi")
                    {
                        GameData.SceneChange.ChangeScene(
                            "AzynthiClear",
                            Position,
                            _useSun: true,
                            180f
                        );
                    }
                    else if (SceneManager.GetActiveScene().name == "AzynthiClear")
                    {
                        GameData.SceneChange.ChangeScene("Azynthi", Position, _useSun: false, 180f);
                    }
                    break;
            }
        }

        public void Release()
        {
            Timer -= 1f;
            foreach (string raider in Raiders)
            {
                if (raider.Length > 0)
                    break;
            }
            if (Timer <= 1f)
            {
                if (!Released)
                {
                    GameData.SceneChange.ChangeScene(
                        "Azure",
                        new Vector3(226f, 11f, 455f),
                        _useSun: true,
                        180f
                    );
                    return;
                }
                Released = false;
                GameData.SceneChange.ChangeScene(
                    "Stowaway",
                    new Vector3(831.2f, 16.5f, 473f),
                    _useSun: true,
                    0f
                );
            }
        }

        public void InLoop()
        {
            foreach (string raider in Raiders)
            {
                GameData.SceneChange.ChangeScene(raider, Position, _useSun: true, 0f);
            }
        }

        public void UnreadableExit()
        {
            if (Timer > 1f)
            {
                if (Released)
                {
                    return;
                }
                GameData.Save();
            }
            GameData.SceneChange.ChangeScene("Azure", Position, _useSun: true, 0f);
        }

        public Vector3 Position => new Vector3(0f, 0f, 0f);

        public struct Vector3
        {
            public Vector3(float x, float y, float z)
            {
                X = x;
                Y = y;
                Z = z;
            }

            public float X;
            public float Y;
            public float Z;
        }

        private static class SceneManager
        {
            public static Scene GetActiveScene() => new Scene();
        }

        private sealed class Scene
        {
            public string name = "";
        }

        private static class GameData
        {
            public static readonly Changer SceneChange = new Changer();
            public static string BindZone = "";
            public static Vector3 BindLoc;
            public static bool SunInBindZone;
            public static bool usingSun;

            public static void Save() { }
        }

        private sealed class Changer
        {
            public void ChangeScene(string _dest, Vector3 _landing, bool _useSun, float yRot) { }
        }
    }
}
