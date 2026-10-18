public static class GameData
{
    public static System.Collections.Generic.List<string> CompletedQuests =
        new System.Collections.Generic.List<string>();
    public static System.Collections.Generic.List<string> HasQuest =
        new System.Collections.Generic.List<string>();
    public static bool AccountClaimedReliquary;

    public static bool IsQuestDone(string quest) => quest.Length > 0;

    public static void FinishQuest(string quest) => System.Console.WriteLine(quest);

    public static void AssignQuest(string quest) => System.Console.WriteLine(quest);
}

public class Inventory
{
    public bool HasItem() => true;

    public bool HasCosmetic() => true;
}

public class Character
{
    public bool Invulnerable;
}

public class AtmosphereColors
{
    public bool isRaining;
    public float WeightGoal;
    public float SinceRain;
}

public class SceneChange
{
    public void ChangeScene() => System.Console.WriteLine("scene");

    public void ChangeSceneSafe() => System.Console.WriteLine("safe");
}

namespace BehaviourFixtures
{
    public class AllApis
    {
        public bool Use(
            global::Inventory inventory,
            global::Character character,
            global::AtmosphereColors weather,
            global::SceneChange scene
        )
        {
            global::GameData.FinishQuest("done");
            global::GameData.AssignQuest("new");
            character.Invulnerable = false;
            weather.WeightGoal += 1;
            weather.SinceRain--;
            scene.ChangeScene();
            scene.ChangeSceneSafe();
            return global::GameData.IsQuestDone("q")
                && global::GameData.CompletedQuests.Count > 0
                && global::GameData.HasQuest.Count > 0
                && inventory.HasItem()
                && inventory.HasCosmetic()
                && global::GameData.AccountClaimedReliquary
                && weather.isRaining;
        }
    }

    public class WrongDirection
    {
        public bool Use(global::Character character, global::AtmosphereColors weather)
        {
            global::GameData.AccountClaimedReliquary = true;
            weather.isRaining = true;
            return character.Invulnerable || weather.WeightGoal > weather.SinceRain;
        }
    }

    public class Unrelated
    {
        public bool Invulnerable;

        public bool IsQuestDone() => Invulnerable;

        public bool Use() => IsQuestDone();
    }

    public class Outer
    {
        public class Nested
        {
            public bool Use() => global::GameData.IsQuestDone("nested");
        }
    }
}
