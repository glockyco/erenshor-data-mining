using NUnit.Framework;

public class WikiItemFactoryTests
{
    private WikiFancyArmorFactory _armorFactory;
    private WikiFancyWeaponFactory _weaponFactory;
    
    [SetUp]
    public void Setup()
    {
        using var db = Repository.CreateConnection();
        _armorFactory = new WikiFancyArmorFactory(db);
        _weaponFactory = new WikiFancyWeaponFactory(db);
    }
    
    [Test]
    public void CreateArmor_FromNullItem_ReturnsNull()
    {
        var armor = _armorFactory.Create((ItemDBRecord) null);
        Assert.IsNull(armor);
    }
    
    [Test]
    public void CreateArmor_FromNullString_ReturnsNull()
    {
        var armor = _armorFactory.Create((string) null);
        Assert.IsNull(armor);
    }

    [Test]
    public void CreateArmor_FromEmptyString_ReturnsNull()
    {
        var armor = _armorFactory.Create("");
        Assert.IsNull(armor);
    }

    [Test]
    public void CreateArmor_FromInvalidString_ReturnsNull()
    {
        var armor = _armorFactory.Create("abc");
        Assert.IsNull(armor);
    }

    [Test]
    public void CreateWeapon_FromNullItem_ReturnsNull()
    {
        var weapon = _weaponFactory.Create((string) null);
        Assert.IsNull(weapon);
    }
    
    [Test]
    public void CreateWeapon_FromNullString_ReturnsNull()
    {
        var weapon = _weaponFactory.Create((string) null);
        Assert.IsNull(weapon);
    }

    [Test]
    public void CreateWeapon_FromEmptyString_ReturnsNull()
    {
        var weapon = _weaponFactory.Create("");
        Assert.IsNull(weapon);
    }

    [Test]
    public void CreateWeapon_FromInvalidString_ReturnsNull()
    {
        var weapon = _weaponFactory.Create("abc");
        Assert.IsNull(weapon);
    }
}