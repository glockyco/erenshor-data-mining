using System;
using System.Net.Http;
using System.Threading.Tasks;
using HtmlAgilityPack; // Make sure you have added the NuGet package HtmlAgilityPack to your project

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
    /// <returns>The text content of the textarea, or null if an error occurs or the textarea isn't found.</returns>
    private async Task<string> GetWikiEditTextAsync(string wikiEditUrl)
    {
        try
        {
            // Set a User-Agent header, as some sites might block requests without one
            // Using a generic bot-like agent. Consider customizing if needed.
            if (httpClient.DefaultRequestHeaders.UserAgent.Count == 0)
            {
                 httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (compatible; WikiBot/1.0; +https://yourdomain.com/botinfo)"); // Replace with your info if desired
            }

            string htmlContent = await httpClient.GetStringAsync(wikiEditUrl);

            HtmlDocument doc = new HtmlDocument();
            doc.LoadHtml(htmlContent);

            // --- Locate the textarea ---
            // Based on the provided HTML, the textarea seems to be within a div with class 'wikiEditor-ui-text'.
            // We'll use XPath to find it. You might need to adjust this if the structure varies.
            // XPath: //div[contains(@class, 'wikiEditor-ui-text')]//textarea
            // A potentially more robust selector if the direct parent isn't always 'wikiEditor-ui-text':
            // //div[contains(@class, 'wikiEditor-ui')]//textarea
            HtmlNode textAreaNode = doc.DocumentNode.SelectSingleNode("//div[contains(@class, 'wikiEditor-ui-text')]//textarea");

            // Fallback selector if the first one fails
            if (textAreaNode == null)
            {
                 Console.WriteLine($"Warning: Textarea not found within '.wikiEditor-ui-text' at {wikiEditUrl}. Trying broader search...");
                 textAreaNode = doc.DocumentNode.SelectSingleNode("//div[contains(@class, 'wikiEditor-ui')]//textarea");
            }

            if (textAreaNode != null)
            {
                // The content is the inner text of the textarea node.
                // Use DeEntitize to convert HTML entities (like &amp;) back to characters.
                return HtmlEntity.DeEntitize(textAreaNode.InnerText);
            }
            else
            {
                Console.WriteLine($"Error: Textarea not found within '.wikiEditor-ui' structure at {wikiEditUrl}");
                // Optionally log the HTML structure here for debugging if the textarea isn't found
                // Console.WriteLine($"HTML Structure: {doc.DocumentNode.OuterHtml.Substring(0, Math.Min(doc.DocumentNode.OuterHtml.Length, 1000))}"); // Log first 1000 chars
                return null;
            }
        }
        catch (HttpRequestException e)
        {
            Console.WriteLine($"Error fetching URL {wikiEditUrl}: {e.Message}");
            return null;
        }
        catch (Exception ex) // Catch other potential parsing errors
        {
             Console.WriteLine($"Error processing HTML from {wikiEditUrl}: {ex.Message}");
             return null;
        }
    }

    /// <summary>
    /// Compares the local WikiString with the content fetched from the online wiki edit page.
    /// Normalizes line endings to \n before comparison.
    /// </summary>
    /// <param name="itemWikiUrl">The full URL to the wiki page (e.g., https://erenshor.wiki.gg/wiki/Item_Name).</param>
    /// <param name="localWikiString">The WikiString value from your ItemDBRecord.</param>
    /// <returns>A tuple containing: bool AreEqual, string OnlineText, string LocalText.</returns>
    public async Task<(bool AreEqual, string OnlineText, string LocalText)> CompareWikiStringAsync(string itemWikiUrl, string localWikiString)
    {
        // Construct the edit URL
        string editUrl = itemWikiUrl.Contains("?")
            ? itemWikiUrl + "&action=edit"
            : itemWikiUrl + "?action=edit";

        string onlineWikiTextRaw = await GetWikiEditTextAsync(editUrl);

        if (onlineWikiTextRaw == null)
        {
            // Indicate failure to retrieve or parse online text
            return (false, null, localWikiString);
        }

        // --- Comparison ---
        // Normalize line endings to \n and trim whitespace for a more robust comparison.
        string normalizedOnline = onlineWikiTextRaw.Replace("\r\n", "\n").Trim();
        string normalizedLocal = (localWikiString ?? "").Replace("\r\n", "\n").Trim(); // Handle potential null local string

        bool areEqual = string.Equals(normalizedOnline, normalizedLocal, StringComparison.Ordinal);

        // Return the *original* raw online text and local text for inspection if needed,
        // even though the comparison was done on the normalized versions.
        return (areEqual, onlineWikiTextRaw, localWikiString);
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
        string wikiPageName = itemRecord.Id; // Assuming Id matches the wiki page title
        string baseUrl = $"https://erenshor.wiki.gg/wiki/{Uri.EscapeDataString(wikiPageName)}";

        WikiComparator comparator = new WikiComparator();
        var result = await comparator.CompareWikiStringAsync(baseUrl, itemRecord.WikiString);

        Console.WriteLine($"--- Comparing: {itemRecord.ItemName} ---");
        if (result.OnlineText == null)
        {
            Console.WriteLine("  Result: FAILED to retrieve or parse online wiki text.");
        }
        else if (result.AreEqual)
        {
            Console.WriteLine("  Result: WikiString MATCHES the online version (after normalizing line endings).");
        }
        else
        {
            Console.WriteLine("  Result: DIFFERENCE DETECTED (after normalizing line endings)!");
            Console.WriteLine("\n  --- Online Text (Raw) ---");
            Console.WriteLine(result.OnlineText);
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
