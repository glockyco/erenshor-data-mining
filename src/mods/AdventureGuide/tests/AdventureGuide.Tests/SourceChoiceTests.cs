using AdventureGuide.Data;

namespace AdventureGuide.Tests;

public sealed class SourceChoiceTests
{
    private const string Actor = "character:a rift vendor:reliquary:269.02:1.44:338.50";
    private const string Acquisition = "acquisition:vendor:octorunner:L2";

    private static ItemSource Located(
        string id,
        string acquisition = Acquisition,
        string actor = Actor,
        string slot = "L2"
    )
    {
        var location = new SourceLocation
        {
            LocationKey = id,
            PlacementKey = id,
            GateScope = id,
            SourceCopyStableKey = actor,
            Relation = "fixed",
            Scene = "Reliquary",
            ZoneStableKey = "zone:reliquary",
            X = 269.0176086425781f,
            Y = 1.4423997402191162f,
            Z = 338.504638671875f,
            Conditions = [Atom(id, slot)],
        };
        var fact = new SourceFact
        {
            AcquisitionKey = acquisition,
            ItemStableKey = "item:fish - octorunner",
            SourceGroupKey = "character:vendor:shared presentation group",
            SourceCopyStableKey = actor,
            Locations = [location],
            ProbabilityKind = "exact",
            ProbabilityMin = 0.00001,
            ProbabilityMax = 0.00001,
            ProbabilityBasis = "per_purchase",
        };
        return new ItemSource
        {
            Type = "vendor",
            Name = "Summoned: Pocket Vendor",
            AcquisitionKey = acquisition,
            LocationKey = id,
            SourceKey = actor,
            CanonicalSourceId = acquisition + "|" + id,
            ItemStableKey = fact.ItemStableKey,
            Scene = location.Scene,
            Zone = "Reliquary",
            X = location.X,
            Y = location.Y,
            Z = location.Z,
            Level = 16,
            Instruction = "Buy An Octorunner.",
            CanonicalFact = fact,
            CanonicalLocation = location,
        };
    }

    private static SourceCondition Atom(string scope, string slot = "L2") =>
        new()
        {
            GateKey = "furniture",
            Predicate = "room_furnished",
            ReferenceStableKey = "item:furniture - stone vendor",
            ReferenceSlot = slot,
            Scope = scope,
            Phase = "availability",
        };

    private static SourceChoice Pair(ItemSource a, ItemSource b) =>
        Assert.Single(SourceChoice.ForSources([a, b]));

    [Fact]
    public void OneAcquisitionKeepsEveryPlacementAndOriginalReference()
    {
        var sources = new List<ItemSource>();
        for (int i = 0; i < 46; i++)
        {
            var source = Located("placement:priel:" + i, "acquisition:priel", "character:priel");
            source.CanonicalLocation!.X = source.X = i;
            sources.Add(source);
        }

        var choices = SourceChoice.ForSources(sources);
        var choice = Assert.Single(choices);
        Assert.Same(sources[0], choice.Primary);
        Assert.Equal(46, choice.Members.Count);
        Assert.Equal(46, choice.Locations.Count);
        for (int i = 0; i < sources.Count; i++)
        {
            Assert.Same(sources[i], choice.Members[i]);
            Assert.Same(sources[i], choice.Locations[i].Primary);
            Assert.True(choice.Contains(sources[i]));
            Assert.Same(choice, SourceChoice.FindContaining(sources, sources[i]));
        }
        Assert.False(
            choice.Contains(Located("placement:priel:0", "acquisition:priel", "character:priel"))
        );
    }

    [Fact]
    public void DirectAndSpawnBoundL2PairFoldsWithoutRewritingAnyIdentity()
    {
        string spawnedId = "placement:[\"" + Actor + "\",\"spawn:reliquary:269.02:1.44:338.50\",1]";
        string directId = "placement:[\"" + Actor + "\",null,1]";
        var spawned = Located(spawnedId);
        var direct = Located(directId);
        spawned.CanonicalLocation!.CoordinateStableKey = "spawn:reliquary:269.02:1.44:338.50";
        spawned.CanonicalLocation.Conditions[0].GateKey =
            "gate:[spawn_point,spawn:reliquary:269.02:1.44:338.50,furnishing]";
        direct.CanonicalLocation!.CoordinateStableKey = Actor;
        direct.CanonicalLocation.Conditions[0].GroupIndex = 17;
        direct.CanonicalLocation.Conditions[0].AtomIndex = 22;
        var fact = spawned.CanonicalFact;
        var originalLocation = spawned.CanonicalLocation;
        var originalCondition = spawned.CanonicalLocation.Conditions[0];
        var child = new ItemSource { UseKey = "use:material:0" };
        spawned.Children = [child];
        direct.Children = [new() { UseKey = child.UseKey }];

        var choice = Pair(spawned, direct);
        var location = Assert.Single(choice.Locations);
        Assert.Same(spawned, location.Primary);
        Assert.Collection(
            location.Members,
            member => Assert.Same(spawned, member),
            member => Assert.Same(direct, member)
        );
        Assert.Same(fact, spawned.CanonicalFact);
        Assert.Same(originalLocation, spawned.CanonicalLocation);
        Assert.Same(originalCondition, spawned.CanonicalLocation.Conditions[0]);
        Assert.Same(child, choice.Primary.Children![0]);
        Assert.Equal(spawnedId, spawned.LocationKey);
        Assert.Equal(directId, direct.LocationKey);
        Assert.Equal(spawnedId, originalCondition.Scope);
        Assert.Equal(directId, direct.CanonicalLocation.Conditions[0].Scope);
        Assert.Equal(Acquisition + "|" + spawnedId, spawned.MakeSourceId());
        Assert.Equal(Acquisition + "|" + directId, direct.MakeSourceId());
        Assert.Equal(0.00001, fact!.ProbabilityMin);
        Assert.Equal("per_purchase", fact.ProbabilityBasis);
    }

    [Fact]
    public void EightFurnishedRoomActorsStayEightChoicesEvenWithIdenticalNamesAndGroupKeys()
    {
        var sources = new List<ItemSource>();
        foreach (string slot in new[] { "L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4" })
        {
            string actor = "character:vendor:" + slot;
            string acquisition = "acquisition:vendor:" + slot;
            sources.Add(Located("placement:" + slot + ":spawn", acquisition, actor, slot));
            sources.Add(Located("placement:" + slot + ":direct", acquisition, actor, slot));
        }

        var choices = SourceChoice.ForSources(sources);
        Assert.Equal(8, choices.Count);
        foreach (var choice in choices)
        {
            Assert.Equal(2, choice.Members.Count);
            Assert.Equal(2, Assert.Single(choice.Locations).Members.Count);
        }
        Assert.Equal(16, choices.Sum(choice => choice.Members.Count));
        Assert.Equal(
            8,
            choices
                .Select(choice => choice.Primary.CanonicalLocation!.Conditions[0].ReferenceSlot)
                .Distinct()
                .Count()
        );
    }

    [Theory]
    [InlineData("use")]
    [InlineData("quality")]
    [InlineData("quantity")]
    [InlineData("condition")]
    [InlineData("item")]
    [InlineData("operation_input")]
    [InlineData("child_use")]
    [InlineData("child_quantity")]
    [InlineData("child_quality")]
    public void MaterialUseContextsDoNotCollapse(string difference)
    {
        var a = Located("a");
        var b = Located("b");
        a.Children =
        [
            new()
            {
                UseKey = "use:material:0",
                Quantity = 1,
                OutputQuality = "normal",
            },
        ];
        b.Children =
        [
            new()
            {
                UseKey = "use:material:0",
                Quantity = 1,
                OutputQuality = "normal",
            },
        ];
        switch (difference)
        {
            case "use":
                b.UseKey = "use:material:1";
                break;
            case "quality":
                b.OutputQuality = "superior";
                break;
            case "quantity":
                b.Quantity = 2;
                break;
            case "condition":
                b.Condition = 2;
                break;
            case "item":
                b.ItemStableKey = "item:other";
                break;
            case "operation_input":
                b.OperationUseKeys = ["use:operation:1"];
                break;
            case "child_use":
                b.Children[0].UseKey = "use:material:1";
                break;
            case "child_quantity":
                b.Children[0].Quantity = 2;
                break;
            case "child_quality":
                b.Children[0].OutputQuality = "superior";
                break;
        }
        Assert.Equal(2, SourceChoice.ForSources([a, b]).Count);
    }

    [Theory]
    [InlineData("actor")]
    [InlineData("scene")]
    [InlineData("zone")]
    [InlineData("relation")]
    [InlineData("position")]
    [InlineData("player_level_min")]
    [InlineData("player_level_max")]
    [InlineData("level")]
    [InlineData("level_max")]
    [InlineData("entries")]
    [InlineData("location_entries")]
    [InlineData("preparation")]
    [InlineData("keyword")]
    [InlineData("time")]
    [InlineData("chance")]
    [InlineData("chance_max")]
    [InlineData("day_chance")]
    [InlineData("night_chance")]
    public void PhysicalOrPreparationDifferencesKeepBothLocations(string difference)
    {
        var a = Located("a");
        var b = Located("b");
        var location = b.CanonicalLocation!;
        switch (difference)
        {
            case "actor":
                location.SourceCopyStableKey = "character:other vendor";
                break;
            case "scene":
                location.Scene = "Other";
                break;
            case "zone":
                location.ZoneStableKey = "zone:other";
                break;
            case "relation":
                location.Relation = "interaction";
                break;
            case "position":
                location.X = b.X = location.X!.Value + 0.0001f;
                break;
            case "player_level_min":
                location.PlayerLevelMin = 10;
                break;
            case "player_level_max":
                location.PlayerLevelMax = 20;
                break;
            case "level":
                b.Level = 17;
                break;
            case "level_max":
                b.LevelMax = 18;
                break;
            case "entries":
                b.EntryZoneLineKeys = ["zoneline:restricted"];
                break;
            case "location_entries":
                location.EntryZoneLineKeys = ["zoneline:restricted"];
                break;
            case "preparation":
                b.Instruction = "Complete the preparation first.";
                break;
            case "keyword":
                b.Keyword = "offer";
                break;
            case "time":
                b.TimeRestriction = "night";
                break;
            case "chance":
                b.Chance = 0.00001;
                break;
            case "chance_max":
                b.ChanceMax = 2;
                break;
            case "day_chance":
                b.DayChance = 0;
                break;
            case "night_chance":
                b.NightChance = 1;
                break;
        }
        Assert.Equal(2, Pair(a, b).Locations.Count);
    }

    [Theory]
    [InlineData("predicate")]
    [InlineData("reference")]
    [InlineData("slot")]
    [InlineData("actor")]
    [InlineData("value")]
    [InlineData("minimum")]
    [InlineData("maximum")]
    [InlineData("minimum_inclusive")]
    [InlineData("maximum_inclusive")]
    [InlineData("phase")]
    [InlineData("scope")]
    public void EverySemanticConditionFieldMatters(string difference)
    {
        var a = Located("a");
        var b = Located("b");
        var atom = b.CanonicalLocation!.Conditions[0];
        switch (difference)
        {
            case "predicate":
                atom.Predicate = "planning_slot_item";
                break;
            case "reference":
                atom.ReferenceStableKey = "item:other furniture";
                break;
            case "slot":
                atom.ReferenceSlot = "R2";
                break;
            case "actor":
                atom.Actor = "account";
                break;
            case "value":
                atom.Value = "false";
                break;
            case "minimum":
                atom.Minimum = 2;
                break;
            case "maximum":
                atom.Maximum = 4;
                break;
            case "minimum_inclusive":
                atom.MinimumInclusive = false;
                break;
            case "maximum_inclusive":
                atom.MaximumInclusive = false;
                break;
            case "phase":
                atom.Phase = "operation_outcome";
                break;
            case "scope":
                atom.Scope = "encounter:another actor";
                break;
        }
        Assert.Equal(2, Pair(a, b).Locations.Count);
    }

    [Theory]
    [InlineData("location")]
    [InlineData("placement")]
    [InlineData("gate_scope")]
    public void OnlyExactOwnScopeBindingsAreNormalized(string binding)
    {
        var a = Located("a");
        var b = Located("b");
        a.CanonicalLocation!.PlacementKey = "placement:a";
        b.CanonicalLocation!.PlacementKey = "placement:b";
        a.CanonicalLocation.GateScope = "gate-scope:a";
        b.CanonicalLocation.GateScope = "gate-scope:b";
        foreach (var source in new[] { a, b })
        {
            var location = source.CanonicalLocation!;
            location.Conditions[0].Scope = binding switch
            {
                "placement" => location.PlacementKey!,
                "gate_scope" => location.GateScope!,
                _ => location.LocationKey,
            };
        }
        Assert.Single(Pair(a, b).Locations);
    }

    [Fact]
    public void EqualExternalScopesStayEqualButUnrelatedScopesAreNotRebound()
    {
        var a = Located("a");
        var b = Located("b");
        a.CanonicalLocation!.Conditions[0].Scope = "account:shared";
        b.CanonicalLocation!.Conditions[0].Scope = "account:shared";
        Assert.Single(Pair(a, b).Locations);

        var other = Located("other");
        other.CanonicalLocation!.Conditions[0].Scope = "account:other";
        Assert.Equal(2, Pair(a, other).Locations.Count);

        var crossBound = Located("cross");
        crossBound.CanonicalLocation!.Conditions[0].Scope = a.LocationKey!;
        Assert.Equal(2, Pair(Located("a"), crossBound).Locations.Count);
    }

    [Fact]
    public void DnfProvenanceAndOrderingDisappearWithoutFlatteningFamiliesOrGroups()
    {
        var a = Located("a");
        var b = Located("b");
        a.CanonicalLocation!.Conditions =
        [
            Condition("a", "first", 0, "A"),
            Condition("a", "first", 0, "B"),
            Condition("a", "first", 1, "C"),
            Condition("a", "second", 0, "D"),
        ];
        b.CanonicalLocation!.Conditions =
        [
            Condition("b", "renamed-second", 33, "D"),
            Condition("b", "renamed-first", 12, "C"),
            Condition("b", "renamed-first", 19, "B"),
            Condition("b", "renamed-first", 19, "A"),
        ];
        Assert.Single(Pair(a, b).Locations);

        var differentGroups = Located("c");
        differentGroups.CanonicalLocation!.Conditions =
        [
            Condition("c", "first", 0, "A"),
            Condition("c", "first", 1, "B"),
            Condition("c", "first", 1, "C"),
            Condition("c", "second", 0, "D"),
        ];
        Assert.Equal(2, Pair(a, differentGroups).Locations.Count);

        var flattenedFamily = Located("d");
        flattenedFamily.CanonicalLocation!.Conditions =
        [
            Condition("d", "one", 0, "A"),
            Condition("d", "one", 0, "B"),
            Condition("d", "one", 1, "C"),
            Condition("d", "one", 2, "D"),
        ];
        Assert.Equal(2, Pair(a, flattenedFamily).Locations.Count);
    }

    private static SourceCondition Condition(
        string scope,
        string gate,
        int group,
        string reference
    ) =>
        new()
        {
            Scope = scope,
            GateKey = gate,
            GroupIndex = group,
            AtomIndex = reference[0],
            Predicate = "quest_done",
            ReferenceStableKey = "quest:" + reference,
            Phase = "availability",
        };

    [Theory]
    [InlineData("fact")]
    [InlineData("use")]
    public void NonAvailabilityAnnotationsAlsoDistinguishLocations(string owner)
    {
        var a = Located("a");
        var b = Located("b");
        var first = Atom("encounter:global");
        first.Phase = "initialization";
        var second = Atom("encounter:global");
        second.Phase = "operation_outcome";
        if (owner == "fact")
        {
            a.CanonicalFact!.Conditions = [first];
            b.CanonicalFact!.Conditions = [second];
        }
        else
        {
            a.CanonicalUse = new() { Conditions = [first] };
            b.CanonicalUse = new() { Conditions = [second] };
        }
        Assert.Equal(2, Pair(a, b).Locations.Count);
    }

    [Fact]
    public void NoncanonicalAndUnlocatedSourcesNeverAcquireInventedPhysicalIdentity()
    {
        var first = new ItemSource { Name = "Same name", SourceKey = "same key" };
        var second = new ItemSource { Name = first.Name, SourceKey = first.SourceKey };
        Assert.Equal(2, SourceChoice.ForSources([first, second]).Count);

        first.AcquisitionKey = second.AcquisitionKey = "acquisition:unlocated";
        var choice = Pair(first, second);
        Assert.Equal(2, choice.Locations.Count);
        Assert.Null(first.LocationKey);
        Assert.Null(second.LocationKey);
        Assert.Equal("same key", first.MakeSourceId());
    }

    [Theory]
    [InlineData(float.NaN)]
    [InlineData(float.PositiveInfinity)]
    [InlineData(float.NegativeInfinity)]
    public void InvalidCoordinatesCannotProvePhysicalEquivalence(float coordinate)
    {
        var a = Located("a");
        var b = Located("b");
        a.CanonicalLocation!.X = b.CanonicalLocation!.X = coordinate;
        Assert.Equal(2, Pair(a, b).Locations.Count);
    }

    [Fact]
    public void MissingActorCopyCannotProvePhysicalEquivalence()
    {
        var a = Located("a");
        var b = Located("b");
        a.CanonicalLocation!.SourceCopyStableKey = b.CanonicalLocation!.SourceCopyStableKey = null;
        Assert.Equal(2, Pair(a, b).Locations.Count);
    }

    [Fact]
    public void RebindingOwnScopeAliasesDoesNotMergeIndependentGateFamilies()
    {
        var a = Located("a");
        var b = Located("b");
        a.CanonicalLocation!.PlacementKey = "placement:a";
        b.CanonicalLocation!.PlacementKey = "placement:b";
        a.CanonicalLocation.Conditions =
        [
            Condition("a", "same-label", 0, "A"),
            Condition("placement:a", "same-label", 1, "B"),
        ];
        b.CanonicalLocation.Conditions =
        [
            Condition("b", "same-label", 0, "A"),
            Condition("b", "same-label", 1, "B"),
        ];
        Assert.Equal(2, Pair(a, b).Locations.Count);
    }

    [Fact]
    public void EquivalentInputContextsAndEntryOrderDoNotCreateExtraChoicesOrLocations()
    {
        var a = Located("a");
        var b = Located("b");
        a.OperationUseKeys = ["use:input:0", "use:input:1"];
        b.OperationUseKeys = ["use:input:1", "use:input:0"];
        a.Children =
        [
            new() { AcquisitionKey = "acquisition:input:a", UseKey = "use:input:0" },
            new() { AcquisitionKey = "acquisition:input:b", UseKey = "use:input:1" },
        ];
        b.Children =
        [
            new() { AcquisitionKey = "acquisition:alternative:b", UseKey = "use:input:1" },
            new() { AcquisitionKey = "acquisition:alternative:a", UseKey = "use:input:0" },
        ];
        a.EntryZoneLineKeys = ["line:1", "line:2"];
        b.EntryZoneLineKeys = ["line:2", "line:1"];
        a.CanonicalLocation!.EntryZoneLineKeys = ["line:1", "line:2"];
        b.CanonicalLocation!.EntryZoneLineKeys = ["line:2", "line:1"];

        var choice = Pair(a, b);
        Assert.Single(choice.Locations);
        Assert.Same(a.Children[0], choice.Members[0].Children![0]);
        Assert.Same(b.Children[0], choice.Members[1].Children![0]);
        Assert.Equal("acquisition:alternative:b", choice.Members[1].Children![0].AcquisitionKey);
    }

    [Fact]
    public void ContainsDoesNotAllocateOnRepeatedMembershipLookups()
    {
        var source = Located("a");
        var choice = Assert.Single(SourceChoice.ForSources([source]));
        Assert.True(choice.Contains(source));
        long before = GC.GetAllocatedBytesForCurrentThread();
        bool found = false;
        for (int i = 0; i < 1000; i++)
            found |= choice.Contains(source);
        long allocated = GC.GetAllocatedBytesForCurrentThread() - before;
        Assert.True(found);
        Assert.Equal(0, allocated);
    }

    [Fact]
    public void FindContainingUsesOriginalChildListsAndExactReferences()
    {
        var first = Located("child:a");
        var second = Located("child:b");
        var children = new List<ItemSource> { first, second };
        var parent = new ItemSource { Type = "crafting", Children = children };
        var sources = new List<ItemSource> { parent };
        var childChoice = Assert.Single(SourceChoice.ForSources(children));
        Assert.Same(childChoice, SourceChoice.FindContaining(sources, second));
        Assert.Same(
            Assert.Single(SourceChoice.ForSources(sources)),
            SourceChoice.FindContaining(sources, parent)
        );
        Assert.Null(SourceChoice.FindContaining(sources, Located("child:b")));
        Assert.Null(SourceChoice.FindContaining(null, first));
        Assert.Empty(SourceChoice.ForSources(null));
        Assert.Same(children, parent.Children);
    }
}
