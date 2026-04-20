// Polyfill for System.Runtime.CompilerServices.IsExternalInit so C# 9+
// `init` setters and `record` types compile on netstandard2.1, which the
// Unity-facing mod assembly targets. The attribute is never referenced
// directly; the compiler looks it up by fully-qualified name.
namespace System.Runtime.CompilerServices;

internal static class IsExternalInit { }
