#nullable enable

using System.Linq;
using NUnit.Framework;

public class WikiItemComparisonTests
{
    [Test]
    public void Compare_SameArmorAndWikiString_AreEqual()
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
    
    [Test]
    public void Compare_SameWeaponAndWikiString_AreEqual()
    {
        using var db = Repository.CreateConnection();
        var item = db.Table<ItemDBRecord>().ToList().FirstOrDefault(i => i.WikiString.Contains("Fancy-weapon"));
        if (item == null) return;
        
        var factory = new WikiFancyWeaponFactory(db);
        WikiFancyWeapon fancyWeapon1 = factory.Create(item);
        WikiFancyWeapon fancyWeapon2 = factory.Create(item.WikiString);
        
        ObjectComparisonResult result = ObjectComparer.Compare(fancyWeapon1, fancyWeapon2);
        Assert.IsTrue(result.AreEqual, result.ToString());
        Assert.AreEqual(fancyWeapon1.ToString(), fancyWeapon2.ToString());
    }
}