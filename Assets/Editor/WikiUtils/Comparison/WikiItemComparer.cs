#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using HtmlAgilityPack;
using SQLite;

public class WikiItemComparer
{
    private readonly SQLiteConnection _db;
    private readonly WikiFancyArmorFactory _armorFactory;
    private readonly WikiFancyWeaponFactory _weaponFactory;

    public WikiItemComparer(SQLiteConnection db)
    {
        _db = db;
        _armorFactory = new WikiFancyArmorFactory(_db);
        _weaponFactory = new WikiFancyWeaponFactory(_db);
    }

    public void CompareAndPersist(ItemRecord item, List<ItemStatsRecord> itemStats)
    {
        var comparisonRecords = Compare(item, itemStats);
        foreach (var comparisonRecord in comparisonRecords)
        {
            _db.Insert(comparisonRecord);
        }
    }

    private List<WikiComparisonDBRecord> Compare(ItemRecord item, List<ItemStatsRecord> itemStats)
    {
        var comparisonRecords = new List<WikiComparisonDBRecord>();
        
        if (itemStats.Any())
        {
            return comparisonRecords;
        }

        var wikiPageName = item.ItemName.Replace(" ", "_");
        var wikiUrl = $"https://erenshor.wiki.gg/wiki/{Uri.EscapeDataString(wikiPageName)}?action=edit";
        var wikiContent = FetchWikiContent(wikiUrl);

        var itemName = item.ItemName;
        
        if (itemStats.First().WikiString.Contains("Fancy-armor"))
        {
            var currentWikiStrings = WikiTemplateExtractor.ExtractTemplates(wikiContent, "Fancy-armor");
            var currentFancyArmors = currentWikiStrings.Select(_armorFactory.Create).ToDictionary(w => w.Tier);
            var suggestedFancyArmors = itemStats.Select(stats => _armorFactory.Create(item, stats)).ToDictionary(w => w.Tier);

            foreach (var suggestedFancyArmor in suggestedFancyArmors.Values)
            {
                currentFancyArmors.TryGetValue(suggestedFancyArmor.Tier, out var currentFancyArmor);
                var comparisonResult = ObjectComparer.Compare(currentFancyArmor, suggestedFancyArmor);

                comparisonRecords.Add(new WikiComparisonDBRecord
                {
                    WikiUrl = wikiUrl,
                    Type = "Fancy-armor",
                    Name = itemName,
                    Tier = suggestedFancyArmor.Tier,
                    ComparisonResult = comparisonResult.ToString(),
                    CurrentWikiString = currentFancyArmor?.OriginalWikiString ?? "",
                    SuggestedWikiString = suggestedFancyArmor.ToString(),
                    ComparisonTimestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss")
                });
            }
        }
        else if (itemStats.First().WikiString.Contains("Fancy-weapon"))
        {
            var currentWikiStrings = WikiTemplateExtractor.ExtractTemplates(wikiContent, "Fancy-weapon");
            var currentFancyWeapons = currentWikiStrings.Select(_weaponFactory.Create).ToDictionary(w => w.Tier);
            var suggestedFancyWeapons = itemStats.Select(stats => _weaponFactory.Create(item, stats)).ToDictionary(w => w.Tier);

            foreach (var suggestedFancyWeapon in suggestedFancyWeapons.Values)
            {
                currentFancyWeapons.TryGetValue(suggestedFancyWeapon.Tier, out var currentFancyWeapon);
                var comparisonResult = ObjectComparer.Compare(currentFancyWeapon, suggestedFancyWeapon);

                comparisonRecords.Add(new WikiComparisonDBRecord
                {
                    WikiUrl = wikiUrl,
                    Type = "Fancy-weapon",
                    Name = itemName,
                    Tier = suggestedFancyWeapon.Tier,
                    ComparisonResult = comparisonResult.ToString(),
                    CurrentWikiString = currentFancyWeapon?.OriginalWikiString ?? "",
                    SuggestedWikiString = suggestedFancyWeapon.ToString(),
                    ComparisonTimestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss")
                });
            }
        }
        
        return comparisonRecords;
    }

    private string FetchWikiContent(string wikiUrl)
    {
        var httpClient = new HttpClient();
        httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (compatible; ErenshorWikiTool/1.0; UnityEditor)");
        var response = httpClient.GetAsync(wikiUrl).GetAwaiter().GetResult();
        response.EnsureSuccessStatusCode();
        var content = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();

        var doc = new HtmlDocument();
        doc.LoadHtml(content);

        var textAreaNode = doc.DocumentNode.SelectSingleNode("//textarea[@id='wpTextbox1']");

        if (textAreaNode is null)
        {
            throw new Exception($"Failed to identify text area for {wikiUrl}.");
        }
        
        return HtmlEntity.DeEntitize(textAreaNode.InnerText);
    }
}