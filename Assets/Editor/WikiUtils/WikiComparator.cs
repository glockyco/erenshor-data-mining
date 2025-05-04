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

        // Regex to find Fancy-armor or Fancy-weapon templates and capture their content.
        // Handles potentially nested braces using balancing groups.
        private static readonly Regex FancyTemplateRegex = new Regex(
            @"\{\{\s*(Fancy-armor|Fancy-weapon)\s*(\|(?<content>(?>\{\{ (?<DEPTH>) | \}\} (?<-DEPTH>) | [^\{\}] | \{ (?!\{) | \} (?!\}) )+? (?(DEPTH)(?!)) ))? \}\}",
            RegexOptions.IgnoreCase | RegexOptions.Singleline | RegexOptions.Compiled);

        // Regex to find the tier value within a template's content.
        private static readonly Regex TierRegex = new Regex(
            @"\|\s*tier\s*=\s*(\d+)\s*",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);


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
        /// Parses wiki text to find Fancy-armor/weapon templates and extracts their tier.
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

            MatchCollection matches = FancyTemplateRegex.Matches(wikiText);
            foreach (Match match in matches)
            {
                if (match.Success)
                {
                    string fullTemplateText = match.Value;
                    string content = match.Groups["content"].Value; // Get content inside the template for tier parsing
                    int tier = 0; // Default tier

                    Match tierMatch = TierRegex.Match(content);
                    if (tierMatch.Success && int.TryParse(tierMatch.Groups[1].Value, out int parsedTier))
                    {
                        tier = parsedTier;
                    }

                    if (templatesByTier.ContainsKey(tier))
                    {
                        // Handle duplicate tiers if necessary - currently overwrites with the last one found
                        Debug.LogWarning($"[WikiComparator] Duplicate template found for tier {tier}. Using the last one encountered.");
                    }
                    // Store the *full* matched template text, including {{...}}
                    templatesByTier[tier] = fullTemplateText;
                }
            }
            return templatesByTier;
        }

        /// <summary>
        /// Normalizes wiki template text for comparison by trimming whitespace and standardizing line endings.
        /// </summary>
        private string NormalizeTemplateText(string templateText)
        {
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

            // Parse templates from both sources
            Dictionary<int, string> onlineTemplates = ParseWikiTemplates(onlineWikiTextRaw);
            Dictionary<int, string> localTemplates = ParseWikiTemplates(localWikiString);

            // Get all unique tiers found in either source
            var allTiers = onlineTemplates.Keys.Union(localTemplates.Keys).OrderBy(t => t).ToList();

            bool overallMatch = true;
            List<string> comparisonDetails = new List<string>();

            if (!allTiers.Any() && (!string.IsNullOrWhiteSpace(onlineWikiTextRaw) || !string.IsNullOrWhiteSpace(localWikiString)))
            {
                // If there's text but no templates were found in either, consider it a potential difference
                // unless both are truly empty/whitespace.
                 if (string.IsNullOrWhiteSpace(onlineWikiTextRaw) && string.IsNullOrWhiteSpace(localWikiString))
                 {
                     // Both effectively empty, consider it a match
                     overallMatch = true;
                 }
                 else if (string.IsNullOrWhiteSpace(onlineWikiTextRaw?.Trim()) && string.IsNullOrWhiteSpace(localWikiString?.Trim()))
                 {
                     // Both contain only whitespace after trimming, consider it a match
                     overallMatch = true;
                 }
                 else
                 {
                    // One or both have content, but no templates found. This is treated as a difference if the raw text differs.
                    // Fallback to simple string comparison if no templates are involved.
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
                // Both sources are empty or contain no templates, consider it a match.
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
                            // Optionally add info about matches
                            // comparisonDetails.Add($"Tier {tier}: Match");
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
                finalErrorMessage = "Differences found: " + string.Join("; ", comparisonDetails);
            }
            else if (comparisonDetails.Any()) // Add details even on match if needed (e.g., "No templates found...")
            {
                 finalErrorMessage = comparisonDetails.First(); // Show the first detail message (e.g., about no templates)
            }


            // Return overall match status, raw texts, and potential comparison details/errors
            return (overallMatch, onlineWikiTextRaw, localWikiString, finalErrorMessage);
        }
    }
}
