using System;
using System.Net; // Added for HttpStatusCode
using System.Net.Http;
using System.Threading.Tasks;
using HtmlAgilityPack; // Make sure you have added the NuGet package HtmlAgilityPack to your project
using UnityEngine; // Added for Debug.Log/Warning/Error

// Assuming ItemDBRecord is accessible from Assets/Editor/ExportSystem/Database/ItemDBRecord.cs
// If not, you might need to adjust using statements or include the definition here.

public class WikiComparator
{
    // It's good practice to reuse HttpClient instances
    private static readonly HttpClient httpClient = new HttpClient();

    /// <summary>
    /// Fetches the content of the wiki edit page's main textarea.
    /// </summary>
    /// <param name="wikiEditUrl">The full URL to the wiki page with ?action=edit.</param>
    /// <returns>A tuple containing the text content and an error message (null if successful).</returns>
    private async Task<(string? Content, string? ErrorMessage)> GetWikiEditTextAsync(string wikiEditUrl)
    {
        HttpResponseMessage response = null;
        try
        {
            // Set a User-Agent header, as some sites might block requests without one
            if (httpClient.DefaultRequestHeaders.UserAgent.Count == 0)
            {
                 httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (compatible; ErenshorWikiTool/1.0; UnityEditor)"); // More specific UA
            }

            Debug.Log($"[WikiComparator] Fetching edit content from: {wikiEditUrl}");
            response = await httpClient.GetAsync(wikiEditUrl);

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

            string htmlContent = await response.Content.ReadAsStringAsync();

            HtmlDocument doc = new HtmlDocument();
            doc.LoadHtml(htmlContent);

            // --- Locate the textarea ---
            // Try the most specific selector first
            HtmlNode textAreaNode = doc.DocumentNode.SelectSingleNode("//textarea[@id='wpTextbox1']"); // MediaWiki default ID

            // Fallback selectors if the ID isn't present
            if (textAreaNode == null)
            {
                 Debug.LogWarning($"[WikiComparator] Textarea with id='wpTextbox1' not found at {wikiEditUrl}. Trying class-based selectors...");
                 textAreaNode = doc.DocumentNode.SelectSingleNode("//div[contains(@class, 'wikiEditor-ui-text')]//textarea");
            }
            if (textAreaNode == null)
            {
                 Debug.LogWarning($"[WikiComparator] Textarea not found within '.wikiEditor-ui-text'. Trying broader '.wikiEditor-ui' search...");
                 textAreaNode = doc.DocumentNode.SelectSingleNode("//div[contains(@class, 'wikiEditor-ui')]//textarea");
            }

            if (textAreaNode != null)
            {
                // The content is the inner text of the textarea node.
                // Use DeEntitize to convert HTML entities (like &amp;) back to characters.
                Debug.Log($"[WikiComparator] Successfully found textarea and extracted content.");
                return (HtmlEntity.DeEntitize(textAreaNode.InnerText), null); // Success
            }
            else
            {
                string errorMsg = $"[WikiComparator] Error: Could not find the wiki edit textarea in the HTML structure at {wikiEditUrl}. The wiki page structure might have changed.";
                Debug.LogError(errorMsg);
                // Log first part of HTML for debugging
                // Debug.Log($"HTML Structure (start): {htmlContent.Substring(0, Math.Min(htmlContent.Length, 1000))}");
                return (null, "Could not parse wiki page structure (textarea not found).");
            }
        }
        catch (HttpRequestException e)
        {
            // Network errors, DNS errors, etc.
            string errorMsg = $"[WikiComparator] Network Error fetching URL {wikiEditUrl}: {e.Message}";
            Debug.LogError($"{errorMsg}\n{e.StackTrace}");
            return (null, $"Network error: {e.Message}. Check connection and URL.");
        }
        catch (TaskCanceledException e) // Handle timeouts
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
            // Dispose response content if it exists, response itself is disposed implicitly by using
             response?.Dispose();
        }
    }

    /// <summary>
    /// Compares the local WikiString with the content fetched from the online wiki edit page.
    /// Normalizes line endings to \n before comparison.
    /// </summary>
    /// <param name="itemWikiUrl">The full URL to the wiki page (e.g., https://erenshor.wiki.gg/wiki/Item_Name).</param>
    /// <param name="localWikiString">The WikiString value from your ItemDBRecord.</param>
    /// <returns>A tuple containing: bool AreEqual, string? OnlineText, string? LocalText, string? ErrorMessage.</returns>
    public async Task<(bool AreEqual, string? OnlineText, string? LocalText, string? ErrorMessage)> CompareWikiStringAsync(string itemWikiUrl, string? localWikiString)
    {
        // Construct the edit URL
        string editUrl = itemWikiUrl.Contains("?")
            ? itemWikiUrl + "&action=edit"
            : itemWikiUrl + "?action=edit";

        (string? onlineWikiTextRaw, string? fetchError) = await GetWikiEditTextAsync(editUrl);

        if (fetchError != null)
        {
            // Indicate failure to retrieve or parse online text, passing the error message
            return (false, null, localWikiString, fetchError);
        }

        // If fetch succeeded, onlineWikiTextRaw should not be null, but check defensively
        if (onlineWikiTextRaw == null)
        {
             Debug.LogError("[WikiComparator] GetWikiEditTextAsync succeeded but returned null content. This should not happen.");
             return (false, null, localWikiString, "Internal error: Fetch succeeded but content was null.");
        }

        // --- Comparison ---
        // Normalize line endings to \n and trim whitespace for a more robust comparison.
        string normalizedOnline = onlineWikiTextRaw.Replace("\r\n", "\n").Trim();
        string normalizedLocal = (localWikiString ?? "").Replace("\r\n", "\n").Trim(); // Handle potential null local string

        bool areEqual = string.Equals(normalizedOnline, normalizedLocal, StringComparison.Ordinal);

        // Return the *original* raw online text and local text for inspection if needed,
        // even though the comparison was done on the normalized versions. No error message means success.
        return (areEqual, onlineWikiTextRaw, localWikiString, null);
    }

    // --- Example Usage (Can be placed in a separate test class or utility) ---
    // Note: This example assumes ItemDBRecord is defined elsewhere and accessible.
    public static async Task RunComparisonExample()
    {
        // Example ItemDBRecord (replace with how you access your actual data)
        var itemRecord = new ItemDBRecord
        {
            Id = "Charm_of_The_Shield", // Used to construct URL
            ItemName = "Charm of The Shield",
            // Make sure this matches your actual DB value, including line endings!
            // Using a verbatim string literal @"" helps preserve line endings as typed.
            WikiString = @"{{Armor
|title={{PAGENAME}}
|sell=
|source=
|othersource=
|itemid=
}}
 Effect does not work.
{{Fancy-armor
| image = [[File:{{PAGENAME}}.png|80px]]
| name = {{PAGENAME}}
| slot = Charm
| relic  = True
| str  = 0
| end  = 0
| dex  = 0
| agi  = 0
| int  = 0
| wis  = 0
| cha  = 0
| res  = 0
| health  = 0
| mana  = 0
| armor  = 0
| magic  = 0
| poison  = 0
| elemental  = 0
| void  = 0
| description  = EFFECT: Gain a 7% chance to fully mitigate any incoming physical blow
| arcanist  = True
| duelist  = True
| druid  = True
| paladin  = True
| proc_name  =
| proc_desc  =
| proc_chance =
| proc_style  =
}}"
        };

        // Construct the base URL (adjust if your naming convention differs)
        // Ensure page names are correctly URL-encoded
        string wikiPageName = itemRecord.ItemName.Replace(" ", "_");
        string baseUrl = $"https://erenshor.wiki.gg/wiki/{Uri.EscapeDataString(wikiPageName)}";

        WikiComparator comparator = new WikiComparator();
        var result = await comparator.CompareWikiStringAsync(baseUrl, itemRecord.WikiString);

        Console.WriteLine($"--- Comparing: {itemRecord.ItemName} ---");
        if (result.ErrorMessage != null)
        {
            Console.WriteLine($"  Result: FAILED. Error: {result.ErrorMessage}");
        }
        else if (result.AreEqual)
        {
            Console.WriteLine("  Result: WikiString MATCHES the online version (after normalizing line endings).");
        }
        else
        {
            Console.WriteLine("  Result: DIFFERENCE DETECTED (after normalizing line endings)!");
            Console.WriteLine("\n  --- Online Text (Raw) ---");
            Console.WriteLine(result.OnlineText ?? "<NULL>"); // Should not be null if ErrorMessage is null
            Console.WriteLine("  -------------------------");
            Console.WriteLine("\n  --- Local WikiString (Raw) ---");
            Console.WriteLine(result.LocalText ?? "<NULL>"); // Handle potential null local string
            Console.WriteLine("  ----------------------------");

            // Optional: Add more detailed diff output here using a diff library if needed
        }
        Console.WriteLine("--- Comparison Complete ---");
        Console.WriteLine(); // Add a blank line for readability between items
    }
}
