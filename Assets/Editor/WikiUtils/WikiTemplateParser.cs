using System;
using System.Collections.Generic;
using System.Globalization;

public static class WikiTemplateParser
{
    /// <summary>
    /// Parses the parameters from a MediaWiki template string.
    /// Assumes a flat structure like {{TemplateName|key1=value1|key2=value2}}.
    /// Handles potential template name at the beginning.
    /// </summary>
    /// <param name="wikiText">The raw wiki text containing the template.</param>
    /// <param name="expectedTemplateName">Optional. If provided, verifies the template name (case-insensitive).</param>
    /// <returns>A dictionary of parameter keys (lowercase) and their corresponding values.</returns>
    public static Dictionary<string, string> ParseParameters(string wikiText, string expectedTemplateName = null)
    {
        var parameters = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (string.IsNullOrWhiteSpace(wikiText))
            return parameters;

        int startBrace = wikiText.IndexOf("{{", StringComparison.Ordinal);
        int endBrace = wikiText.LastIndexOf("}}", StringComparison.Ordinal);
        if (startBrace == -1 || endBrace == -1 || endBrace <= startBrace)
            return parameters;

        string content = wikiText.Substring(startBrace + 2, endBrace - startBrace - 2).Trim();

        // Split on top-level pipes only
        var parts = new List<string>();
        int braceLevel = 0, bracketLevel = 0;
        int lastSplit = 0;
        for (int i = 0; i < content.Length; i++)
        {
            // Track nesting
            if (content[i] == '{' && i + 1 < content.Length && content[i + 1] == '{')
            {
                braceLevel++;
                i++;
            }
            else if (content[i] == '}' && i + 1 < content.Length && content[i + 1] == '}')
            {
                braceLevel = Math.Max(0, braceLevel - 1);
                i++;
            }
            else if (content[i] == '[' && i + 1 < content.Length && content[i + 1] == '[')
            {
                bracketLevel++;
                i++;
            }
            else if (content[i] == ']' && i + 1 < content.Length && content[i + 1] == ']')
            {
                bracketLevel = Math.Max(0, bracketLevel - 1);
                i++;
            }
            else if (content[i] == '|' && braceLevel == 0 && bracketLevel == 0)
            {
                // Top-level pipe: split here
                parts.Add(content.Substring(lastSplit, i - lastSplit));
                lastSplit = i + 1;
            }
        }

        // Add last part
        if (lastSplit < content.Length)
            parts.Add(content.Substring(lastSplit));

        // Template name
        int parameterStartIndex = 0;
        if (parts.Count > 0 && !string.IsNullOrWhiteSpace(parts[0]) && parts[0].IndexOf('=') == -1)
        {
            string templateName = parts[0].Trim();
            parameterStartIndex = 1;
            if (expectedTemplateName != null &&
                !expectedTemplateName.Equals(templateName, StringComparison.OrdinalIgnoreCase))
                return parameters;
        }

        // Parse parameters
        for (int i = parameterStartIndex; i < parts.Count; i++)
        {
            string part = parts[i];
            if (string.IsNullOrWhiteSpace(part)) continue;
            int equalsIndex = part.IndexOf('=');
            if (equalsIndex > 0)
            {
                string key = part.Substring(0, equalsIndex).Trim();
                string value = part.Substring(equalsIndex + 1).Trim();
                if (!string.IsNullOrEmpty(key))
                    parameters[key.ToLowerInvariant()] = value;
            }
        }

        return parameters;
    }

    // --- HELPER METHODS ---

    /// <summary>
    /// Safely parses an integer value from the parameters dictionary.
    /// Uses CultureInfo.InvariantCulture.
    /// </summary>
    /// <param name="parameters">The dictionary returned by ParseParameters.</param>
    /// <param name="key">The case-insensitive key to look up.</param>
    /// <param name="defaultValue">The value to return if the key is not found or parsing fails.</param>
    /// <returns>The parsed integer or the default value.</returns>
    public static int GetInt(Dictionary<string, string> parameters, string key, int defaultValue = 0) =>
        parameters.TryGetValue(key.ToLowerInvariant(), out var val) && int.TryParse(val, NumberStyles.Integer, CultureInfo.InvariantCulture, out var result)
            ? result
            : defaultValue;

    /// <summary>
    /// Safely parses a float value from the parameters dictionary.
    /// Uses CultureInfo.InvariantCulture.
    /// </summary>
    /// <param name="parameters">The dictionary returned by ParseParameters.</param>
    /// <param name="key">The case-insensitive key to look up.</param>
    /// <param name="defaultValue">The value to return if the key is not found or parsing fails.</param>
    /// <returns>The parsed integer or the default value.</returns>
    public static float GetFloat(Dictionary<string, string> parameters, string key, float defaultValue = 0) =>
        parameters.TryGetValue(key.ToLowerInvariant(), out var val) && float.TryParse(val, NumberStyles.Any, CultureInfo.InvariantCulture, out var result)
            ? result
            : defaultValue;

    /// <summary>
    /// Safely parses a boolean value from the parameters dictionary.
    /// Considers "True" (case-insensitive) as true, otherwise false.
    /// </summary>
    /// <param name="parameters">The dictionary returned by ParseParameters.</param>
    /// <param name="key">The case-insensitive key to look up.</param>
    /// <returns>True if the value is "True" (case-insensitive), otherwise false.</returns>
    public static bool GetBool(Dictionary<string, string> parameters, string key) =>
        parameters.TryGetValue(key.ToLowerInvariant(), out var val) && "True".Equals(val, StringComparison.OrdinalIgnoreCase);

    /// <summary>
    /// Safely retrieves a string value from the parameters dictionary.
    /// </summary>
    /// <param name="parameters">The dictionary returned by ParseParameters.</param>
    /// <param name="key">The case-insensitive key to look up.</param>
    /// <param name="defaultValue">The value to return if the key is not found.</param>
    /// <returns>The string value or the default value.</returns>
    public static string GetString(Dictionary<string, string> parameters, string key, string defaultValue = "") =>
        parameters.TryGetValue(key.ToLowerInvariant(), out var val) ? val : defaultValue;
}
