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
        // Use case-insensitive keys internally for easier lookup, but preserve original casing if needed?
        // Let's stick to lowercase keys for simplicity, matching common wiki practice.
        var parameters = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (string.IsNullOrWhiteSpace(wikiText))
        {
            return parameters;
        }

        // 1. Find the content inside the main braces {{ ... }}
        int startBrace = wikiText.IndexOf("{{", StringComparison.Ordinal);
        int endBrace = wikiText.LastIndexOf("}}", StringComparison.Ordinal);
        if (startBrace == -1 || endBrace == -1 || endBrace <= startBrace)
        {
            // Not a valid template structure or empty
            // Consider logging a warning or throwing an exception if strict format is required
            return parameters;
        }
        string content = wikiText.Substring(startBrace + 2, endBrace - startBrace - 2).Trim();

        // 2. Split the content by the parameter separator '|'
        //    Note: This simple split doesn't handle nested templates or pipes within parameter values correctly.
        //    For complex cases, a more sophisticated parser (e.g., regex or state machine) would be needed.
        var parts = content.Split('|');

        // 3. Identify and optionally validate the template name (first part if it doesn't contain '=')
        int parameterStartIndex = 0;
        if (parts.Length > 0 && !string.IsNullOrWhiteSpace(parts[0]) && parts[0].IndexOf('=') == -1)
        {
            string templateName = parts[0].Trim();
            parameterStartIndex = 1; // Parameters start from the second part

            // Optional validation
            if (expectedTemplateName != null && !expectedTemplateName.Equals(templateName, StringComparison.OrdinalIgnoreCase))
            {
                // Template name mismatch - return empty or throw? Let's return empty for now.
                // Consider logging: $"Warning: Expected template '{expectedTemplateName}' but found '{templateName}'."
                return parameters;
            }
        }

        // 4. Process each parameter part (key=value pairs)
        for (int i = parameterStartIndex; i < parts.Length; i++)
        {
            string part = parts[i];
            if (string.IsNullOrWhiteSpace(part)) continue;

            // Find the *first* equals sign to separate key and value
            int equalsIndex = part.IndexOf('=');
            if (equalsIndex > 0) // Ensure '=' is present and not the first character
            {
                string key = part.Substring(0, equalsIndex).Trim();
                // The rest is the value, trim it.
                string value = part.Substring(equalsIndex + 1).Trim();

                if (!string.IsNullOrEmpty(key))
                {
                    // Store with a consistent key format (e.g., lowercase)
                    parameters[key.ToLowerInvariant()] = value;
                }
            }
            // Optional: Handle parameters without '=' (flags) if needed.
            // else if (!string.IsNullOrEmpty(part.Trim())) { parameters[part.Trim().ToLowerInvariant()] = "true"; }
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
    /// Safely parses a nullable integer value from the parameters dictionary.
    /// Returns null if the key is not found, parsing fails, or the value is 0.
    /// Uses CultureInfo.InvariantCulture.
    /// </summary>
    /// <param name="parameters">The dictionary returned by ParseParameters.</param>
    /// <param name="key">The case-insensitive key to look up.</param>
    /// <returns>The parsed integer or null.</returns>
    public static int? GetNullableInt(Dictionary<string, string> parameters, string key) =>
        parameters.TryGetValue(key.ToLowerInvariant(), out var val) && int.TryParse(val, NumberStyles.Integer, CultureInfo.InvariantCulture, out var result) && result != 0
            ? result
            : null;


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
    /// Safely parses a nullable float value from the parameters dictionary.
    /// Returns null if the key is not found, parsing fails, or the value is 0.
    /// Uses CultureInfo.InvariantCulture.
    /// </summary>
    /// <param name="parameters">The dictionary returned by ParseParameters.</param>
    /// <param name="key">The case-insensitive key to look up.</param>
    /// <returns>The parsed float or null.</returns>
    public static float? GetNullableFloat(Dictionary<string, string> parameters, string key) =>
        parameters.TryGetValue(key.ToLowerInvariant(), out var val) && float.TryParse(val, NumberStyles.Any, CultureInfo.InvariantCulture, out var result) && result != 0
            ? result
            : null;

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
