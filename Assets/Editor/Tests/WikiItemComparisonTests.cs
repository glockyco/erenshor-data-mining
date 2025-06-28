#nullable enable

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using NUnit.Framework;

public class WikiItemComparisonTests
{
    [Test]
    public void Compare_SameArmorAndWikiString_AreEqual()
    {
        using var db = Repository.CreateConnection();
        var itemStats = db.Table<ItemStatsRecord>().ToList().FirstOrDefault(s => s.WikiString.Contains("Fancy-armor"));
        if (itemStats == null) return;
        var item = db.Table<ItemRecord>().FirstOrDefault(i => i.Id == itemStats.ItemId);
        if (item == null) return;
        
        var factory = new WikiFancyArmorFactory(db);
        WikiFancyArmor fancyArmor1 = factory.Create(item, itemStats);
        WikiFancyArmor fancyArmor2 = factory.Create(itemStats.WikiString);
        
        ObjectComparisonResult result = ObjectComparer.Compare(fancyArmor1, fancyArmor2);
        Assert.IsTrue(result.AreEqual, result.ToString());
        Assert.AreEqual(fancyArmor1.ToString(), fancyArmor2.ToString());
    }
    
    [Test]
    public void Compare_SameWeaponAndWikiString_AreEqual()
    {
        using var db = Repository.CreateConnection();
        var itemStats = db.Table<ItemStatsRecord>().ToList().FirstOrDefault(s => s.WikiString.Contains("Fancy-weapon"));
        if (itemStats == null) return;
        var item = db.Table<ItemRecord>().FirstOrDefault(i => i.Id == itemStats.ItemId);
        if (item == null) return;
        
        var factory = new WikiFancyWeaponFactory(db);
        WikiFancyWeapon fancyWeapon1 = factory.Create(item, itemStats);
        WikiFancyWeapon fancyWeapon2 = factory.Create(itemStats.WikiString);
        
        ObjectComparisonResult result = ObjectComparer.Compare(fancyWeapon1, fancyWeapon2);
        Assert.IsTrue(result.AreEqual, result.ToString());
        Assert.AreEqual(fancyWeapon1.ToString(), fancyWeapon2.ToString());
    }

    [Test]
    public void Compare_Wiki()
    {
        var db = Repository.CreateConnection();
        var comparer = new WikiItemComparer(db);

        db.DropTable<WikiComparisonRecord>();
        db.CreateTable<WikiComparisonRecord>();

        const int maxConcurrency = 10;
        const int delayMs = 500;
        var semaphore = new SemaphoreSlim(maxConcurrency);

        var tasks = new List<Task>();
        var exceptions = new ConcurrentBag<Exception>();

        var items = db.Table<ItemRecord>().ToList();
        for (var i = 0; i < items.Count; i++)
        {
            var item = items[i];
            var itemStats = db.Table<ItemStatsRecord>().Where(stats => stats.ItemId == item.Id).ToList();
            TestContext.Progress.WriteLine($"Processing item group {i} of {items.Count} ({item.ItemName})...");

            semaphore.Wait();

            var task = Task.Run(() =>
            {
                try
                {
                    comparer.CompareAndPersist(item, itemStats);
                    Thread.Sleep(delayMs);
                }
                catch (Exception ex)
                {
                    exceptions.Add(ex);
                }
                finally
                {
                    semaphore.Release();
                }
            });

            tasks.Add(task);
        }

        Task.WaitAll(tasks.ToArray());

        if (!exceptions.IsEmpty)
        {
            throw new AggregateException(exceptions);
        }
    }
}