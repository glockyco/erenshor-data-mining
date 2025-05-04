using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using HtmlAgilityPack;
using UnityEngine;

namespace Erenshor.Editor.WikiUtils
{
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
        private async Task<(string? Content, string? ErrorMessage)> GetWikiEditTextAsync(string wikiEditUrl)
        {
            HttpResponseMessage? response = null;
            try
            {
                if (httpClient.DefaultRequestHeaders.UserAgent.Count == 0)
                {
                    httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (compatible; ErenshorWikiTool/1.0; UnityEditor)");
                }

                Debug.Log($"[WikiComparator] Fetching edit content from: {wikiEditUrl}");
                response = await httpClient.GetAsync(wikiEditUrl).ConfigureAwait(false);

                if (!response.IsSuccessStatusCode)
                {
                    string errorMsg = $"[WikiComparator] Error fetching URL {wikiEditUrl}: Status Code {response.StatusCode} ({response.ReasonPhrase})";
                    Debug.LogError(errorMsg);
                    if (response.StatusCode == HttpStatusCode.NotFound)
                    {
                        return (null, $"Page not found on wiki ({response.StatusCode}). Does '{wikiEditUrl.Replace("?action=edit", "")}' exist?");
                    }
                    return (null, $"HTTP Error: {response.StatusCode}. Check wiki accessibility.");
                }

                string htmlContent = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                HtmlDocument doc = new HtmlDocument();
                doc.LoadHtml(htmlContent);

                HtmlNode? textAreaNode = doc.DocumentNode.SelectSingleNode("//textarea[@id='wpTextbox1']")
                                        ?? doc.DocumentNode.SelectSingleNode("//div[contains(@class, 'wikiEditor-ui-text')]//textarea")
                                        ?? doc.DocumentNode.SelectSingleNode("//div[contains(@class, 'wikiEditor-ui')]//textarea");

                if (textAreaNode != null)
                {
                    Debug.Log($"[WikiComparator] Successfully found textarea and extracted content.");
                    return (HtmlEntity.DeEntitize(textAreaNode.InnerText), null);
                }
                else
                {
                    string errorMsg = $"[WikiComparator] Error: Could not find the wiki edit textarea in the HTML structure at {wikiEditUrl}. The wiki page structure might have changed.";
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
                string errorMsg = $"[WikiComparator] Error processing HTML or during request for {wikiEditUrl}: {ex.Message}";
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

                // Determine which marker comes first, or if none are found
                if (armorIndex != -1 && weaponIndex != -1)
                {
                    startIndex = Math.Min(armorIndex, weaponIndex);
                }
                else if (armorIndex != -1)
                {
                    startIndex = armorIndex;
                }
                else if (weaponIndex != -1)
                {
                    startIndex = weaponIndex;
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

                while (searchIndex < wikiText.Length - 1)
                {
                    if (wikiText.Substring(searchIndex, 2) == "{{")
                    {
                        braceLevel++;
                        searchIndex += 2; // Skip the characters we just checked
                    }
                    else if (wikiText.Substring(searchIndex, 2) == "}}")
                    {
                        braceLevel--;
                        if (braceLevel == 0) // Found the matching closing brace for the initial opening brace
                        {
                            endIndex = searchIndex + 2; // Include the closing braces
                            break;
                        }
                        searchIndex += 2; // Skip the characters we just checked
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
                        Debug.LogWarning($"[WikiComparator] Duplicate template found for tier {tier}. Using the last one encountered at index {startIndex}.");
                    }
                    templatesByTier[tier] = fullTemplateText;

                    // Continue searching after the end of the found template
                    currentIndex = endIndex;
                }
                else
                {
                    // Found a start but no valid end? Log error or break?
                    // For now, just advance past the start index to avoid infinite loops on malformed text.
                    Debug.LogWarning($"[WikiComparator] Found template start at index {startIndex} but could not find matching closing braces '}}'. Skipping.");
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
            // Also remove leading/trailing whitespace from each line within the template for robustness?
            // For now, keep it simple: normalize line endings and trim start/end.
            return templateText.Replace("\r\n", "\n").Trim();
        }

        /// <summary>
        /// Compares local and online wiki text by parsing Fancy-armor/weapon templates and comparing them tier by tier.
        /// </summary>
        /// <param name="itemWikiUrl">The full URL to the wiki page.</param>
        /// <param name="localWikiString">The WikiString value from the local database.</param>
        /// <returns>A tuple containing: bool AreEqual (true if all corresponding tiers match), string? OnlineText (full raw text), string? LocalText (full raw text), string? ErrorMessage (fetch/parse errors or comparison details).</returns>
        public async Task<(bool AreEqual, string? OnlineText, string? LocalText, string? ErrorMessage)> CompareWikiStringAsync(string itemWikiUrl, string? localWikiString)
        {
            string editUrl = itemWikiUrl.Contains("?") ? itemWikiUrl + "&action=edit" : itemWikiUrl + "?action=edit";

            (string? onlineWikiTextRaw, string? fetchError) = await GetWikiEditTextAsync(editUrl).ConfigureAwait(false);

            if (fetchError != null)
            {
                return (false, null, localWikiString, fetchError);
            }

            if (onlineWikiTextRaw == null)
            {
                Debug.LogError("[WikiComparator] GetWikiEditTextAsync succeeded but returned null content.");
                return (false, null, localWikiString, "Internal error: Fetch succeeded but content was null.");
            }

            // Parse templates from both sources using the new brace-counting method
            Dictionary<int, string> onlineTemplates = ParseWikiTemplates(onlineWikiTextRaw);
            Dictionary<int, string> localTemplates = ParseWikiTemplates(localWikiString);

            // Get all unique tiers found in either source
            var allTiers = onlineTemplates.Keys.Union(localTemplates.Keys).OrderBy(t => t).ToList();

            bool overallMatch = true;
            List<string> comparisonDetails = new List<string>();

            if (!allTiers.Any() && (!string.IsNullOrWhiteSpace(onlineWikiTextRaw) || !string.IsNullOrWhiteSpace(localWikiString)))
            {
                 if (string.IsNullOrWhiteSpace(onlineWikiTextRaw) && string.IsNullOrWhiteSpace(localWikiString))
                 {
                     overallMatch = true;
                 }
                 else if (string.IsNullOrWhiteSpace(onlineWikiTextRaw?.Trim()) && string.IsNullOrWhiteSpace(localWikiString?.Trim()))
                 {
                     overallMatch = true;
                 }
                 else
                 {
                    string normalizedOnline = (onlineWikiTextRaw ?? "").Replace("\r\n", "\n").Trim();
                    string normalizedLocal = (localWikiString ?? "").Replace("\r\n", "\n").Trim();
                    overallMatch = string.Equals(normalizedOnline, normalizedLocal, StringComparison.Ordinal);
                    if (!overallMatch)
                    {
                         comparisonDetails.Add("No Fancy-armor/weapon templates found, and raw text differs.");
                    }
                    else
                    {
                        comparisonDetails.Add("No Fancy-armor/weapon templates found, raw text matches.");
                    }
                 }
            }
            else if (!allTiers.Any())
            {
                overallMatch = true;
                comparisonDetails.Add("No Fancy-armor/weapon templates found in either source.");
            }
            else
            {
                // Compare tier by tier
                foreach (int tier in allTiers)
                {
                    bool onlineHasTier = onlineTemplates.TryGetValue(tier, out string? onlineTemplate);
                    bool localHasTier = localTemplates.TryGetValue(tier, out string? localTemplate);

                    if (onlineHasTier && localHasTier)
                    {
                        // Tier exists in both, compare normalized content
                        string normalizedOnline = NormalizeTemplateText(onlineTemplate!);
                        string normalizedLocal = NormalizeTemplateText(localTemplate!);
                        if (!string.Equals(normalizedOnline, normalizedLocal, StringComparison.Ordinal))
                        {
                            overallMatch = false;
                            comparisonDetails.Add($"Tier {tier}: Mismatch");
                        }
                        else
                        {
                            // comparisonDetails.Add($"Tier {tier}: Match"); // Optional: Add match details
                        }
                    }
                    else if (onlineHasTier)
                    {
                        overallMatch = false;
                        comparisonDetails.Add($"Tier {tier}: Exists online, missing locally");
                    }
                    else // Must be localHasTier only
                    {
                        overallMatch = false;
                        comparisonDetails.Add($"Tier {tier}: Exists locally, missing online");
                    }
                }
            }

            string? finalErrorMessage = null;
            if (!overallMatch)
            {
                // Combine details if mismatch occurred
                finalErrorMessage = "Differences found: " + string.Join("; ", comparisonDetails);
            }
            else if (comparisonDetails.Any())
            {
                 // If match is true, but there are details (like "No templates found..."), show the first one.
                 finalErrorMessage = comparisonDetails.First();
            }


            // Return overall match status, raw texts, and potential comparison details/errors
            return (overallMatch, onlineWikiTextRaw, localWikiString, finalErrorMessage);
        }
    }
}
