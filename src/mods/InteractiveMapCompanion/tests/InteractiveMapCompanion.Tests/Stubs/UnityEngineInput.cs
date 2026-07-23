namespace UnityEngine;

public enum KeyCode
{
    None = 0,
    K,
    F2,
    F3,
    LeftControl,
    LeftShift,
    RightShift,
}

public static class Input
{
    public static bool GetKey(KeyCode key) => false;

    public static bool GetKeyDown(KeyCode key) => false;
}
