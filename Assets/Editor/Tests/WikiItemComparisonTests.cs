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

    [Test]
    public void Compare_Wiki()
    {
        var db = Repository.CreateConnection();
        var comparer = new WikiItemComparer(db);

        var itemsByBaseItemId = db.Table<ItemDBRecord>().ToList()
            .Where(i => !string.IsNullOrEmpty(i.WikiString))
            .GroupBy(i => i.BaseItemId)
            .ToDictionary(g => g.Key, g => g.ToList());

        db.DropTable<WikiComparisonDBRecord>();
        db.CreateTable<WikiComparisonDBRecord>();

        const int maxConcurrency = 10;
        const int delayMs = 500;
        var semaphore = new SemaphoreSlim(maxConcurrency);

        var itemGroups = itemsByBaseItemId.Values.ToList();
        var tasks = new List<Task>();
        var exceptions = new ConcurrentBag<Exception>();

        for (var i = 0; i < itemGroups.Count; i++)
        {
            var items = itemGroups[i];
            TestContext.Progress.WriteLine($"Processing item group {i} of {itemGroups.Count} ({items.First().ItemName})...");

            semaphore.Wait();

            var task = Task.Run(() =>
            {
                try
                {
                    comparer.CompareAndPersist(items);
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