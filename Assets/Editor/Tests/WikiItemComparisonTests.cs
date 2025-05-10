#nullable enable

using System.Linq;
using NUnit.Framework;

public class WikiFancyArmorComparisonTests
{
    [Test]
    public void Test()
    {
        using var db = Repository.CreateConnection();
        
        var item = db.Table<ItemDBRecord>().ToList().FirstOrDefault(i => i.WikiString.Contains("Fancy-armor"));
        
        if (item == null) return;
        
        var factory = new WikiFancyArmorFactory(db);
        WikiFancyArmor fancyArmor1 = factory.Create(item);
        WikiFancyArmor fancyArmor2 = factory.Create(item.WikiString);
        
        ObjectComparisonResult result = ObjectComparer.Compare(fancyArmor1, fancyArmor2);
        Assert.IsTrue(result.AreEqual, result.ToString());
        Assert.AreEqual(fancyArmor1.ToString(), fancyArmor2.ToString());
    }
}