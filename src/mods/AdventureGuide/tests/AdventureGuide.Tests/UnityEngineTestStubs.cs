namespace UnityEngine;

public enum KeyCode
{
    None,
    J,
    K,
    L,
    P,
}

public static class Input
{
    public static bool GetKey(KeyCode key) => false;

    public static bool GetKeyDown(KeyCode key) => false;
}
