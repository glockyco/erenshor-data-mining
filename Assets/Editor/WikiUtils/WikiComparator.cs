using System;
using System.Net; // Added for HttpStatusCode
using System.Net.Http;
using System.Threading.Tasks;
using HtmlAgilityPack; // Make sure you have added the NuGet package HtmlAgilityPack to your project
using UnityEngine; // Added for Debug.Log/Warning/Error

// Assuming ItemDBRecord is accessible via 'using Database;' or similar.

namespace Erenshor.Editor.WikiUtils
{
    public class WikiComparator
    {
        // Reuse HttpClient instances for performance and resource management
        private static readonly HttpClient httpClient = new HttpClient();

        /// <summary>
        /// Fetches the content of the wiki edit page's main textarea.
        /// </summary>
        /// <param name="wikiEditUrl">The full URL to the wiki page with ?action=edit.</param>
        /// <returns>A tuple containing the text content and an error message (null if successful).</returns>
        private async Task<(string? Content, string? ErrorMessage)> GetWikiEditTextAsync(string wikiEditUrl)
        {
            HttpResponseMessage? response = null;
            try
            {
                // Set a User-Agent header if not already set
                if (httpClient.DefaultRequestHeaders.UserAgent.Count == 0)
                {
                    httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (compatible; ErenshorWikiTool/1.0; UnityEditor)");
                }

                Debug.Log($"[WikiComparator] Fetching edit content from: {wikiEditUrl}");
                // Use ConfigureAwait(false) for library-like async code
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

                // Use ConfigureAwait(false) for library-like async code
                string htmlContent = await response.Content.ReadAsStringAsync().ConfigureAwait(false);

                HtmlDocument doc = new HtmlDocument();
                doc.LoadHtml(htmlContent);

                // Locate the textarea using various selectors
                HtmlNode? textAreaNode = doc.DocumentNode.SelectSingleNode("//textarea[@id='wpTextbox1']") // MediaWiki default ID
                                        ?? doc.DocumentNode.SelectSingleNode("//div[contains(@class, 'wikiEditor-ui-text')]//textarea")
                                        ?? doc.DocumentNode.SelectSingleNode("//div[contains(@class, 'wikiEditor-ui')]//textarea");

                if (textAreaNode != null)
                {
                    // Use DeEntitize to convert HTML entities (like &amp;) back to characters.
                    Debug.Log($"[WikiComparator] Successfully found textarea and extracted content.");
                    return (HtmlEntity.DeEntitize(textAreaNode.InnerText), null); // Success
                }
                else
                {
                    string errorMsg = $"[WikiComparator] Error: Could not find the wiki edit textarea in the HTML structure at {wikiEditUrl}. The wiki page structure might have changed.";
                    Debug.LogError(errorMsg);
                    // Consider logging a snippet of HTML if debugging is needed frequently
                    // Debug.Log($"HTML Structure (start): {htmlContent.Substring(0, Math.Min(htmlContent.Length, 1000))}");
                    return (null, "Could not parse wiki page structure (textarea not found).");
                }
            }
            catch (HttpRequestException e)
            {
                string errorMsg = $"[WikiComparator] Network Error fetching URL {wikiEditUrl}: {e.Message}";
                Debug.LogError($"{errorMsg}\n{e.StackTrace}");
                return (null, $"Network error: {e.Message}. Check connection and URL.");
            }
            catch (TaskCanceledException e) // Handle timeouts specifically
            {
                string errorMsg = $"[WikiComparator] Request timed out for URL {wikiEditUrl}: {e.Message}";
                Debug.LogError($"{errorMsg}\n{e.StackTrace}");
                return (null, $"Request timed out. The wiki might be slow or unreachable.");
            }
            catch (Exception ex) // Catch other potential parsing or unexpected errors
            {
                string errorMsg = $"[WikiComparator] Error processing HTML or during request for {wikiEditUrl}: {ex.Message}";
                Debug.LogError($"{errorMsg}\n{ex.StackTrace}");
                return (null, $"An unexpected error occurred: {ex.Message}");
            }
            finally
            {
                // Dispose response content if it exists
                response?.Dispose();
            }
        }

        /// <summary>
        /// Compares the local WikiString with the content fetched from the online wiki edit page.
        /// Normalizes line endings to \n and trims whitespace before comparison.
        /// </summary>
        /// <param name="itemWikiUrl">The full URL to the wiki page (e.g., https://erenshor.wiki.gg/wiki/Item_Name).</param>
        /// <param name="localWikiString">The WikiString value from your ItemDBRecord.</param>
        /// <returns>A tuple containing: bool AreEqual, string? OnlineText, string? LocalText, string? ErrorMessage.</returns>
        public async Task<(bool AreEqual, string? OnlineText, string? LocalText, string? ErrorMessage)> CompareWikiStringAsync(string itemWikiUrl, string? localWikiString)
        {
            // Construct the edit URL safely
            string editUrl = itemWikiUrl.Contains("?")
                ? itemWikiUrl + "&action=edit"
                : itemWikiUrl + "?action=edit";

            (string? onlineWikiTextRaw, string? fetchError) = await GetWikiEditTextAsync(editUrl).ConfigureAwait(false);

            if (fetchError != null)
            {
                // Indicate failure to retrieve or parse online text, passing the error message
                return (false, null, localWikiString, fetchError);
            }

            // Defensive check, although GetWikiEditTextAsync should ensure non-null content on success
            if (onlineWikiTextRaw == null)
            {
                Debug.LogError("[WikiComparator] GetWikiEditTextAsync succeeded but returned null content. This should not happen.");
                return (false, null, localWikiString, "Internal error: Fetch succeeded but content was null.");
            }

            // Normalize line endings to \n and trim whitespace for a robust comparison.
            string normalizedOnline = onlineWikiTextRaw.Replace("\r\n", "\n").Trim();
            string normalizedLocal = (localWikiString ?? "").Replace("\r\n", "\n").Trim(); // Handle potential null local string

            bool areEqual = string.Equals(normalizedOnline, normalizedLocal, StringComparison.Ordinal);

            // Return the original raw online text and local text for inspection,
            // even though the comparison used normalized versions. Null error message indicates success.
            return (areEqual, onlineWikiTextRaw, localWikiString, null);
        }

        // Removed the RunComparisonExample method as it's not suitable for direct use within the Editor tool
        // and uses Console.WriteLine. Testing should be done separately or via the EditorWindow.
    }
}
