#nullable enable

using UnityEditor;
using UnityEngine;

/// <summary>
/// Finds the texture that an icon sprite draws.
///
/// The game shows an icon by drawing its sprite's texture, so the export
/// records the texture asset that the sprite references, not the sprite's
/// name: AssetRipper names sprites and textures independently, and in some
/// sprite families a sprite's name is not its texture's name. The texture is
/// recorded whole. At runtime every icon sprite covers its whole texture, while
/// AssetRipper reconstructs the sprites of the ripped project with rects that
/// can be tighter, so the rect of an editor sprite is not evidence of what the
/// game draws.
/// </summary>
public static class IconTextures
{
    /// <summary>
    /// The project path of the texture that <paramref name="icon"/> draws,
    /// such as <c>Assets/Texture2D/4_8.png</c>, or null without an icon.
    /// </summary>
    /// <exception cref="System.InvalidOperationException">
    /// The sprite references no texture asset of the project.
    /// </exception>
    public static string? PathOf(Sprite? icon, string owner)
    {
        if (icon == null)
        {
            return null;
        }
        var path = icon.texture != null ? AssetDatabase.GetAssetPath(icon.texture) : string.Empty;
        if (string.IsNullOrEmpty(path))
        {
            throw new System.InvalidOperationException(
                $"The icon sprite {AssetDatabase.GetAssetPath(icon)} of {owner} references no texture asset."
            );
        }
        return path;
    }
}
