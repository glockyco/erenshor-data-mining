using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using HtmlAgilityPack;
using UnityEngine;

public class WikiComparator
{
    private static readonly HttpClient httpClient = new HttpClient();

    // Keep TierRegex as it's used on the extracted template content
    private static readonly Regex TierRegex = new Regex(
        @"\|\s*tier\s*=\s*(\d+)\s*",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    // Template start markers
    private const string FancyArmorStart = "{{Fancy-armor";
    private const string FancyWeaponStart = "{{Fancy-weapon";


    /// <summary>
    /// Fetches the content of the wiki edit page's main textarea.
    /// </summary>
    private async Task<(string? FullRawContent, string? ErrorMessage)> GetWikiEditTextAsync(string wikiEditUrl)
    {
        HttpResponseMessage? response = null;
        try
        {
            if (httpClient.DefaultRequestHeaders.UserAgent.Count == 0)
            {
                httpClient.DefaultRequestHeaders.UserAgent.ParseAdd(
                    "Mozilla/5.0 (compatible; ErenshorWikiTool/1.0; UnityEditor)");
            }

            Debug.Log($"[WikiComparator] Fetching edit content from: {wikiEditUrl}");
            response = await httpClient.GetAsync(wikiEditUrl).ConfigureAwait(false);

            if (!response.IsSuccessStatusCode)
            {
                string errorMsg =
                    $"[WikiComparator] Error fetching URL {wikiEditUrl}: Status Code {response.StatusCode} ({response.ReasonPhrase})";
                Debug.LogError(errorMsg);
                if (response.StatusCode == HttpStatusCode.NotFound)
                {
                    return (null,
                        $"Page not found on wiki ({response.StatusCode}). Does '{wikiEditUrl.Replace("?action=edit", "")}' exist?");
                }

                return (null, $"HTTP Error: {response.StatusCode}. Check wiki accessibility.");
            }

            string htmlContent = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
            HtmlDocument doc = new HtmlDocument();
            doc.LoadHtml(htmlContent);

            HtmlNode? textAreaNode = doc.DocumentNode.SelectSingleNode("//textarea[@id='wpTextbox1']")
                                     ?? doc.DocumentNode.SelectSingleNode(
                                         "//div[contains(@class, 'wikiEditor-ui-text')]//textarea")
                                     ?? doc.DocumentNode.SelectSingleNode(
                                         "//div[contains(@class, 'wikiEditor-ui')]//textarea");

            if (textAreaNode != null)
            {
                Debug.Log($"[WikiComparator] Successfully found textarea and extracted content.");
                // Return the full raw content fetched
                return (HtmlEntity.DeEntitize(textAreaNode.InnerText), null);
            }
            else
            {
                string errorMsg =
                    $"[WikiComparator] Error: Could not find the wiki edit textarea in the HTML structure at {wikiEditUrl}. The wiki page structure might have changed.";
                Debug.LogError(errorMsg);
                return (null, "Could not parse wiki page structure (textarea not found).");
            }
        }
        catch (HttpRequestException e)
        {
            string errorMsg = $"[WikiComparator] Network Error fetching URL {wikiEditUrl}: {e.Message}";
            Debug.LogError($"{errorMsg}\n{e.StackTrace}");
            return (null, $"Network error: {e.Message}. Check connection and URL.");
        }
        catch (TaskCanceledException e)
        {
            string errorMsg = $"[WikiComparator] Request timed out for URL {wikiEditUrl}: {e.Message}";
            Debug.LogError($"{errorMsg}\n{e.StackTrace}");
            return (null, $"Request timed out. The wiki might be slow or unreachable.");
        }
        catch (Exception ex)
        {
            string errorMsg =
                $"[WikiComparator] Error processing HTML or during request for {wikiEditUrl}: {ex.Message}";
            Debug.LogError($"{errorMsg}\n{ex.StackTrace}");
            return (null, $"An unexpected error occurred: {ex.Message}");
        }
        finally
        {
            response?.Dispose();
        }
    }

    /// <summary>
    /// Parses wiki text to find Fancy-armor/weapon templates using start markers and brace counting.
    /// </summary>
    /// <param name="wikiText">The raw wiki text to parse.</param>
    /// <returns>A dictionary where the key is the tier (int, 0 default) and the value is the full template text (string).</returns>
    private Dictionary<int, string> ParseWikiTemplates(string? wikiText)
    {
        var templatesByTier = new Dictionary<int, string>();
        if (string.IsNullOrWhiteSpace(wikiText))
        {
            return templatesByTier;
        }

        int currentIndex = 0;
        while (currentIndex < wikiText.Length)
        {
            // Find the next occurrence of either template start marker
            int armorIndex = wikiText.IndexOf(FancyArmorStart, currentIndex, StringComparison.OrdinalIgnoreCase);
            int weaponIndex = wikiText.IndexOf(FancyWeaponStart, currentIndex, StringComparison.OrdinalIgnoreCase);

            int startIndex = -1;
            string templateStartMarker = "";

            // Determine which marker comes first, or if none are found
            if (armorIndex != -1 && (weaponIndex == -1 || armorIndex < weaponIndex))
            {
                startIndex = armorIndex;
                templateStartMarker = FancyArmorStart;
            }
            else if (weaponIndex != -1)
            {
                startIndex = weaponIndex;
                templateStartMarker = FancyWeaponStart;
            }
            else
            {
                // No more template starts found
                break;
            }

            // Find the end of the template using brace counting
            int braceLevel = 0;
            int endIndex = -1;
            int searchIndex = startIndex;
            bool firstBraceFound = false; // Ensure we find the initial {{

            while (searchIndex < wikiText.Length - 1)
            {
                if (wikiText.Substring(searchIndex, 2) == "{{")
                {
                    if (searchIndex == startIndex) // The very first {{
                    {
                        braceLevel = 1;
                        firstBraceFound = true;
                    }
                    else if (firstBraceFound) // Subsequent {{
                    {
                        braceLevel++;
                    }

                    searchIndex += 2;
                }
                else if (wikiText.Substring(searchIndex, 2) == "}}")
                {
                    if (!firstBraceFound) // Found }} before {{ ? Malformed, ignore.
                    {
                        searchIndex++; // Advance past first }
                        continue;
                    }

                    braceLevel--;
                    if (braceLevel == 0) // Found the matching closing brace
                    {
                        endIndex = searchIndex + 2; // Include the closing braces
                        break;
                    }

                    searchIndex += 2;
                }
                else
                {
                    searchIndex++; // Move to the next character
                }
            }


            if (endIndex != -1) // Successfully found a complete template
            {
                string fullTemplateText = wikiText.Substring(startIndex, endIndex - startIndex);

                // Extract tier (defaulting to 0)
                int tier = 0;
                Match tierMatch = TierRegex.Match(fullTemplateText); // Search within the extracted template
                if (tierMatch.Success && int.TryParse(tierMatch.Groups[1].Value, out int parsedTier))
                {
                    tier = parsedTier;
                }

                if (templatesByTier.ContainsKey(tier))
                {
                    // Log warning but overwrite, using the last one found for that tier
                    Debug.LogWarning(
                        $"[WikiComparator] Duplicate template found for tier {tier} in the *same source*. Using the last one encountered (starts at index {startIndex}).");
                }

                templatesByTier[tier] = fullTemplateText;

                // Continue searching after the end of the found template
                currentIndex = endIndex;
            }
            else
            {
                // Found a start but no valid end? Log error or break?
                // Advance past the start index to avoid infinite loops on malformed text.
                Debug.LogWarning(
                    $"[WikiComparator] Found template start at index {startIndex} but could not find matching closing braces '}}'. Skipping.");
                currentIndex = startIndex + 2; // Move past the '{{'
            }
        }

        return templatesByTier;
    }


    /// <summary>
    /// Normalizes wiki template text for comparison by trimming whitespace and standardizing line endings.
    /// </summary>
    private string NormalizeTemplateText(string templateText)
    {
        // Normalize line endings and trim start/end.
        return templateText.Replace("\r\n", "\n").Trim();
    }

    /// <summary>
    /// Parses the content of a wiki template (text between the first | and final }}) into key-value pairs.
    /// </summary>
    /// <param name="templateContent">The raw text content inside the template.</param>
    /// <returns>A dictionary of parameter names (lowercase, trimmed) to their values (trimmed).</returns>
    private Dictionary<string, string> ParseTemplateParameters(string templateText)
    {
        var parameters = new Dictionary<string, string>();
        // Find the first pipe '|' which usually separates the template name from parameters
        int firstPipe = templateText.IndexOf('|');
        if (firstPipe == -1) // No parameters
        {
            return parameters;
        }

        // Get the content part (after the first pipe, before the final '}}')
        string content = templateText.Substring(firstPipe + 1);
        // Remove the closing braces, handling potential whitespace before them
        if (content.EndsWith("}}"))
        {
            content = content.Substring(0, content.Length - 2).TrimEnd();
        }

        // Split by pipe, respecting potential pipes within values (though less common in this format)
        // A more robust parser might be needed for complex cases, but this handles typical key=value pairs.
        string[] pairs = content.Split('|');

        foreach (string pair in pairs)
        {
            if (string.IsNullOrWhiteSpace(pair)) continue;

            string trimmedPair = pair.Trim();
            int equalsIndex = trimmedPair.IndexOf('=');

            if (equalsIndex > 0) // Ensure '=' is present and not the first character
            {
                string key = trimmedPair.Substring(0, equalsIndex).Trim().ToLowerInvariant(); // Normalize key
                string value = trimmedPair.Substring(equalsIndex + 1).Trim(); // Trim value whitespace

                if (!string.IsNullOrEmpty(key)) // Ensure key is not empty
                {
                    if (parameters.ContainsKey(key))
                    {
                        Debug.LogWarning(
                            $"[WikiComparator] Duplicate parameter key '{key}' found in template. Using last value encountered: '{value}'");
                    }

                    parameters[key] = value;
                }
            }
            else
            {
                // Handle unnamed parameters if necessary, or log a warning
                // For Fancy-armor/weapon, usually all parameters are named.
                Debug.LogWarning($"[WikiComparator] Parameter without '=' found: '{trimmedPair}'. Skipping.");
            }
        }

        return parameters;
    }


    /// <summary>
    /// Compares local and online wiki text assuming the local text contains at most one Fancy-armor/weapon template.
    /// It finds the local template (if any), determines its tier, and compares it to the online template of the same tier.
    /// If a mismatch occurs, it details the differing parameters.
    /// Handles special cases for Tier 0 and ignores missing local 'base_dps'.
    /// </summary>
    /// <param name="itemWikiUrl">The full URL to the wiki page.</param>
    /// <param name="localWikiStringRaw">The raw WikiString value from the local database.</param>
    /// <returns>A tuple containing:
    ///     bool AreEqual (true if local template matches corresponding online tier, or if local has no template, or if Tier 0 is missing online),
    ///     string? DisplayOnlineText (the specific online template matching the local tier, or a status message),
    ///     string? DisplayLocalText (the specific local template found, or a status message),
    ///     string? ErrorMessage (fetch/parse errors or specific comparison failure details including parameter differences).
    /// </returns>
    public async Task<(bool AreEqual, string? DisplayOnlineText, string? DisplayLocalText, string? ErrorMessage)>
        CompareWikiStringAsync(string itemWikiUrl, string? localWikiStringRaw)
    {
        string editUrl = itemWikiUrl.Contains("?") ? itemWikiUrl + "&action=edit" : itemWikiUrl + "?action=edit";

        // Fetch the full raw content from the wiki edit page
        (string? onlineWikiTextRaw, string? fetchError) = await GetWikiEditTextAsync(editUrl).ConfigureAwait(false);

        if (fetchError != null)
        {
            // Distinguish between 'Not Found' and other fetch errors for status reporting
            string displayLocal = string.IsNullOrWhiteSpace(localWikiStringRaw) ? "<Local WikiString is empty>" : localWikiStringRaw;
            if (fetchError.Contains("not found on wiki"))
            {
                // Page itself not found - this is a 'Missing' case
                return (false, "<Page Not Found>", displayLocal, fetchError);
            }
            else
            {
                // Other fetch errors are still 'Error'
                return (false, "<Fetch Failed>", displayLocal, fetchError);
            }
        }

        if (onlineWikiTextRaw == null)
        {
            // Should not happen if fetchError is null, but handle defensively
            Debug.LogError("[WikiComparator] GetWikiEditTextAsync succeeded but returned null content.");
            return (false, "<Internal Error>", localWikiStringRaw,
                "Internal error: Fetch succeeded but content was null.");
        }

        // Parse templates from both sources
        Dictionary<int, string> onlineTemplates = ParseWikiTemplates(onlineWikiTextRaw);
        Dictionary<int, string> localTemplates = ParseWikiTemplates(localWikiStringRaw);

        // --- Handle Local Template ---
        string? localTemplateToCompare = null;
        int localTier = 0; // Default tier

        if (!localTemplates.Any())
        {
            // No template found locally. This is considered a success state (LocalEmpty).
            string noLocalTemplateMsg = string.IsNullOrWhiteSpace(localWikiStringRaw)
                ? "<Local WikiString is empty>"
                : "<No Fancy-armor/weapon template found in local WikiString>";
            // Show full online text for context when local is empty/no template.
            return (true, onlineWikiTextRaw, noLocalTemplateMsg, null);
        }
        else
        {
            if (localTemplates.Count > 1)
            {
                Debug.LogWarning(
                    $"[WikiComparator] Found {localTemplates.Count} templates locally, but expected only one. Using the first one found (Tier: {localTemplates.First().Key}).");
            }

            // Use the first template found locally
            var firstLocal = localTemplates.First();
            localTier = firstLocal.Key;
            localTemplateToCompare = firstLocal.Value;
        }

        // --- Find Matching Online Template and Compare ---
        bool overallMatch = false;
        string? errorMessage = null;
        string? displayOnlineText = null;

        if (onlineTemplates.TryGetValue(localTier, out string? onlineTemplateForTier))
        {
            // Found the corresponding tier online, now compare content
            displayOnlineText = onlineTemplateForTier; // Set display text regardless of match outcome
            string normalizedLocal = NormalizeTemplateText(localTemplateToCompare);
            string normalizedOnline = NormalizeTemplateText(onlineTemplateForTier);

            if (string.Equals(normalizedOnline, normalizedLocal, StringComparison.Ordinal))
            {
                // Quick check passed - templates are identical after normalization
                overallMatch = true;
                errorMessage = null; // Success
            }
            else
            {
                // Normalization shows a difference, perform detailed parameter comparison
                overallMatch = false;
                var localParams = ParseTemplateParameters(localTemplateToCompare);
                var onlineParams = ParseTemplateParameters(onlineTemplateForTier);
                var differences = new List<string>();

                var allKeys = localParams.Keys.Union(onlineParams.Keys).OrderBy(k => k);

                foreach (var key in allKeys)
                {
                    localParams.TryGetValue(key, out string? localValue);
                    onlineParams.TryGetValue(key, out string? onlineValue);

                    // Trim values again just before comparison to ignore only whitespace diffs
                    string trimmedLocalValue = (localValue ?? "").Trim();
                    string trimmedOnlineValue = (onlineValue ?? "").Trim();

                    if (localValue != null && onlineValue != null)
                    {
                        // Key exists in both, compare trimmed values
                        if (trimmedLocalValue != trimmedOnlineValue)
                        {
                            differences.Add($"'{key}': local='{localValue}' | online='{onlineValue}'");
                        }
                    }
                    else if (localValue != null) // Only in local
                    {
                        // Only report missing online if local value is not empty/whitespace
                        if (!string.IsNullOrWhiteSpace(trimmedLocalValue))
                        {
                            differences.Add($"'{key}': local='{localValue}' | missing online");
                        }
                    }
                    else // Only in online (onlineValue must be non-null here)
                    {
                        // Ignore if the key is 'base_dps' and it's only present online
                        if (key == "base_dps")
                        {
                            Debug.Log($"[WikiComparator] Ignoring missing local 'base_dps' parameter (present online).");
                            continue; // Skip adding this difference
                        }

                        // Only report missing locally if online value is not empty/whitespace
                        if (!string.IsNullOrWhiteSpace(trimmedOnlineValue))
                        {
                            differences.Add($"'{key}': online='{onlineValue}' | missing locally");
                        }
                    }
                }

                if (differences.Any())
                {
                    errorMessage = $"Tier {localTier}: Mismatch. Differences -> " + string.Join("; ", differences);
                }
                else
                {
                    // This case might happen if the only difference was whitespace within the template structure
                    // itself, or ignored parameters like base_dps. Consider it a match.
                    overallMatch = true;
                    errorMessage = null; // Success (differences were whitespace or ignored parameters)
                    Debug.Log(
                        $"[WikiComparator] Tier {localTier}: Normalized text differed, but parameter values matched after trimming/ignoring. Considering it a match.");
                }
            }
        }
        else // Corresponding Tier NOT found online
        {
            // Special case: If local tier is 0 and it's missing online, treat as Match (ignore)
            if (localTier == 0)
            {
                overallMatch = true;
                errorMessage = null; // No error, just ignoring missing tier 0 online
                displayOnlineText = $"<Tier 0 template missing online (Ignored)>";
                Debug.Log($"[WikiComparator] Local Tier 0 template found, but no Tier 0 template online. Treating as Match (Ignored).");
            }
            else
            {
                // Tier exists locally but is missing online - this is a 'Missing' case
                overallMatch = false;
                errorMessage = $"Tier {localTier}: Exists locally, missing online";
                // Show the full online text for context when the specific tier is missing
                displayOnlineText =
                    $"<Template for Tier {localTier} not found online>\n\nFull Online Text:\n{onlineWikiTextRaw}";
            }
        }

        // Return comparison result, the specific local template, the specific online template (or message), and error details
        return (overallMatch, displayOnlineText, localTemplateToCompare, errorMessage);
    }
}
