public static class TooltipCapture
{
    public static string Collect(string kind, int start, int end)
    {
        try
        {
            return CollectBatch(kind, start, end);
        }
        catch (Exception error)
        {
            return "error\t" + error.ToString();
        }
    }

    private static string CollectBatch(string kind, int start, int end)
    {
        var window = GameData.ItemInfoWindow;
        if (
            window == null
            || GameData.PlayerStats == null
            || GameData.PlayerInv == null
            || GameData.InCharSelect
        )
            throw new InvalidOperationException("Load a character before capturing tooltips.");
        var items = GameData.ItemDB.ItemDB;
        var spells = GameData.SpellDatabase.SpellDatabase;
        var skills = GameData.SkillDatabase.SkillDatabase;
        if (kind == "counts")
            return items.Length + "\t" + spells.Length + "\t" + skills.Length;
        var output = new System.Text.StringBuilder();
        Func<string, string> encode = value =>
            Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(value ?? ""));
        Action<string, TMPro.TextMeshProUGUI, Transform> field = (name, text, root) =>
        {
            if (text == null)
                return;
            var active = text.enabled;
            for (var node = text.transform; node != null && node != root; node = node.parent)
                active &= node.gameObject.activeSelf;
            output
                .Append(name)
                .Append('\t')
                .Append(active ? "1" : "0")
                .Append('\t')
                .Append(UnityEngine.ColorUtility.ToHtmlStringRGBA(text.color))
                .Append('\t')
                .Append(UnityEngine.ColorUtility.ToHtmlStringRGBA(text.faceColor))
                .Append('\t')
                .Append((text.fontStyle & TMPro.FontStyles.Italic) != 0 ? "1" : "0")
                .Append('\t')
                .Append(encode(text.text))
                .Append('\n');
        };
        var flags =
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
        var effectField = typeof(ItemInfoWindow).GetField("ItemSpellForDisplay", flags);
        var wornField = typeof(ItemInfoWindow).GetField("EffectWorn", flags);
        Action<Spell, bool> details = (spell, worn) =>
        {
            window.CloseSpellDetailsWindow();
            window.LoadSpellDetails(spell, worn);
            output
                .Append("details\t")
                .Append(encode(spell.Id))
                .Append('\t')
                .Append(worn ? "1" : "0")
                .Append('\t')
                .Append(spell.LevelScaledManaRestoration != 0 ? "1" : "0")
                .Append('\n');
            field("SpellDetailsName", window.SpellDetailsName, window.SpellDetailsWindow.transform);
            field("SpellDetailsDesc", window.SpellDetailsDesc, window.SpellDetailsWindow.transform);
        };
        var originalItem = window.CurrentlyDisplaying;
        var originalEffect = (Spell)effectField.GetValue(window);
        var originalWorn = (bool)wornField.GetValue(window);
        var quantityField = typeof(ItemInfoWindow).GetField("CurrentDispQuant", flags);
        var homeField = typeof(ItemInfoWindow).GetField("HomeInv", flags);
        var originalQuantity = (int)quantityField.GetValue(window);
        var originalHome = (Inventory)homeField.GetValue(window);
        var originalItemOpen = window.ParentWindow.activeSelf;
        var originalDetailsOpen = window.SpellDetailsWindow.activeSelf;
        var itemPosition = window.ParentWindow.transform.position;
        var detailPosition = window.SpellDetailsWindow.transform.position;
        var compareOne = window.Compare1Script.gameObject.activeSelf;
        var compareTwo = window.Compare2Script.gameObject.activeSelf;
        var book =
            kind == "spells" ? GameData.PlayerSpellBook.Slots.First(slot => !slot.HKOnly) : null;
        var skillbook =
            kind == "skills" ? GameData.PlayerSkillBook.Slots.First(slot => !slot.HKOnly) : null;
        var bookOpen = book != null && book.SB.Spellbook.activeSelf;
        var skillbookOpen = skillbook != null && skillbook.SB.Skillbook.activeSelf;
        var bookSelection = book == null ? null : book.SB.CurrentSelection;
        var skillSelection = skillbook == null ? null : skillbook.SB.CurrentSelection;
        var assignedSpell = book == null ? null : book.AssignedSpell;
        var assignedSkill = skillbook == null ? null : skillbook.AssignedSkill;
        var bookColor = book == null ? Color.clear : book.SlotBG.color;
        var skillColor = skillbook == null ? Color.clear : skillbook.SlotBG.color;
        var bookName = book == null ? null : book.Name.text;
        var bookDesc = book == null ? null : book.Desc.text;
        var skillName = skillbook == null ? null : skillbook.Name.text;
        var skillDesc = skillbook == null ? null : skillbook.Desc.text;
        var hotkey =
            (book != null || skillbook != null) ? GameData.GM.HKManager.AllHotkeys.First() : null;
        var hoverPanel = GameData.Misc.SpellTT.transform;
        var songHover =
            book != null
                ? UnityEngine.Object.FindObjectsOfType<MouseOverSpellTooltip>(true).First()
                : null;
        var oldHotkeyType = hotkey == null ? Hotkeys.HKType.Spell : hotkey.thisHK;
        var oldHotkeySpell = hotkey == null ? null : hotkey.AssignedSpell;
        var oldHotkeySkill = hotkey == null ? null : hotkey.AssignedSkill;
        var hotkeyNameField = typeof(Hotkeys).GetField("HKName", flags);
        var oldHotkeyName = hotkey == null ? null : hotkeyNameField.GetValue(hotkey);
        var oldSongSpell = songHover == null ? null : songHover.reference;
        var hoverPosition = hoverPanel.position;
        var hoverSibling = hoverPanel.GetSiblingIndex();
        var hoverFields = new[]
        {
            GameData.Misc.SpellName,
            GameData.Misc.HKSubtext,
            GameData.Misc.SpellDesc,
            GameData.Misc.SpellLvl,
            GameData.Misc.SpellType,
        };
        var hoverFieldNames = new[] { "Name", "Kind", "Desc", "Mana", "Type" };
        var oldHoverText = hotkey == null ? null : hoverFields.Select(text => text.text).ToArray();
        Action<string> readHover = method =>
        {
            output.Append("hover\t").Append(method).Append('\n');
            for (var i = 0; i < hoverFields.Length; i++)
                field(hoverFieldNames[i], hoverFields[i], hoverPanel);
        };
        try
        {
            if (book != null)
                book.SB.Spellbook.SetActive(true);
            if (skillbook != null)
                skillbook.SB.Skillbook.SetActive(true);
            var timer = System.Diagnostics.Stopwatch.StartNew();
            for (var index = start; index < end; index++)
            {
                if (timer.ElapsedMilliseconds > 4000)
                    throw new TimeoutException("Tooltip collection batch exceeded four seconds.");
                if (kind == "items")
                {
                    var item = items[index];
                    var equipment =
                        item.RequiredSlot != Item.SlotType.General
                        && item.RequiredSlot != Item.SlotType.Charm
                        && item.Aura == null
                        && item.TeachSpell == null
                        && item.TeachSkill == null;
                    foreach (
                        var quantity in equipment
                            ? new[] { 1, 11, 12, 13, 14, 15, 2, 3 }
                            : new[] { 1 }
                    )
                    {
                        output
                            .Append("item\t")
                            .Append(index)
                            .Append('\t')
                            .Append(encode(item.Id))
                            .Append('\t')
                            .Append(encode(item.name))
                            .Append('\t')
                            .Append(quantity)
                            .Append('\n');
                        window.CloseItemWindow();
                        window.DisplayItem(item, Vector2.zero, quantity);
                        foreach (var member in typeof(ItemInfoWindow).GetFields())
                        {
                            if (
                                member.FieldType == typeof(TMPro.TextMeshProUGUI)
                                && !member.Name.StartsWith("SpellDetails")
                            )
                                field(
                                    member.Name,
                                    (TMPro.TextMeshProUGUI)member.GetValue(window),
                                    window.ParentWindow.transform
                                );
                        }
                        field(
                            "ReqLvl",
                            window.ReqLvl.GetComponent<TMPro.TextMeshProUGUI>(),
                            window.ParentWindow.transform
                        );
                        field(
                            "OtherTextParent",
                            window.OtherTextParent.GetComponent<TMPro.TextMeshProUGUI>(),
                            window.ParentWindow.transform
                        );
                        var effect = (Spell)effectField.GetValue(window);
                        if (effect != null)
                            details(effect, (bool)wornField.GetValue(window));
                    }
                }
                else if (kind == "spells")
                {
                    var spell = spells[index];
                    output
                        .Append("spell\t")
                        .Append(index)
                        .Append('\t')
                        .Append(encode(spell.Id))
                        .Append('\t')
                        .Append(encode(spell.name))
                        .Append('\n');
                    book.AssignedSpell = spell;
                    book.ToggleSelect(true);
                    field("Name", book.Name, book.SB.transform);
                    field("Desc", book.Desc, book.SB.transform);
                    details(spell, false);
                    if (
                        spell.Type == Spell.SpellType.SongDissonance
                        || spell.Type == Spell.SpellType.SongInspiration
                    )
                    {
                        songHover.reference = spell;
                        songHover.OnPointerEnter(null);
                        readHover("MouseOverSpellTooltip.OnPointerEnter");
                    }
                    else
                    {
                        hotkey.thisHK = Hotkeys.HKType.Spell;
                        hotkey.AssignedSpell = spell;
                        hotkeyNameField.SetValue(hotkey, spell.SpellName);
                        hotkey.OnPointerEnter(null);
                        readHover("Hotkeys.OnPointerEnter");
                    }
                }
                else if (kind == "skills")
                {
                    var skill = skills[index];
                    output
                        .Append("skill\t")
                        .Append(index)
                        .Append('\t')
                        .Append(encode(skill.Id))
                        .Append('\t')
                        .Append(encode(skill.name))
                        .Append('\t')
                        .Append(encode(skill.StanceToUse == null ? "" : skill.StanceToUse.name))
                        .Append('\n');
                    skillbook.AssignedSkill = skill;
                    skillbook.ToggleSelect(true);
                    field("Name", skillbook.Name, skillbook.SB.transform);
                    field("Desc", skillbook.Desc, skillbook.SB.transform);
                    hotkey.thisHK = Hotkeys.HKType.Skill;
                    hotkey.AssignedSkill = skill;
                    hotkeyNameField.SetValue(hotkey, skill.SkillName);
                    hotkey.OnPointerEnter(null);
                    readHover("Hotkeys.OnPointerEnter");
                }
            }
        }
        finally
        {
            if (hotkey != null)
            {
                hotkey.thisHK = oldHotkeyType;
                hotkey.AssignedSpell = oldHotkeySpell;
                hotkey.AssignedSkill = oldHotkeySkill;
                hotkeyNameField.SetValue(hotkey, oldHotkeyName);
                for (var i = 0; i < hoverFields.Length; i++)
                    hoverFields[i].text = oldHoverText[i];
                hoverPanel.SetSiblingIndex(hoverSibling);
                hoverPanel.position = hoverPosition;
            }
            if (songHover != null)
                songHover.reference = oldSongSpell;
            if (book != null)
            {
                book.AssignedSpell = assignedSpell;
                book.SB.CurrentSelection = bookSelection;
                book.SlotBG.color = bookColor;
                book.Name.text = bookName;
                book.Desc.text = bookDesc;
                book.SB.Spellbook.SetActive(bookOpen);
            }
            if (skillbook != null)
            {
                skillbook.AssignedSkill = assignedSkill;
                skillbook.SB.CurrentSelection = skillSelection;
                skillbook.SlotBG.color = skillColor;
                skillbook.Name.text = skillName;
                skillbook.Desc.text = skillDesc;
                skillbook.SB.Skillbook.SetActive(skillbookOpen);
            }
            if (kind == "items")
            {
                window.CloseItemWindow();
                if (originalItemOpen)
                    window.DisplayItem(originalItem, Vector2.zero, originalQuantity, originalHome);
                window.Compare1Script.gameObject.SetActive(compareOne);
                window.Compare2Script.gameObject.SetActive(compareTwo);
                window.CurrentlyDisplaying = originalItem;
                quantityField.SetValue(window, originalQuantity);
                homeField.SetValue(window, originalHome);
                effectField.SetValue(window, originalEffect);
                wornField.SetValue(window, originalWorn);
                window.ParentWindow.transform.position = itemPosition;
            }
            if (kind != "skills")
            {
                window.CloseSpellDetailsWindow();
                if (originalDetailsOpen)
                    window.LoadSpellDetails(originalEffect, originalWorn);
                window.SpellDetailsWindow.transform.position = detailPosition;
            }
            if (
                window.ParentWindow.activeSelf != originalItemOpen
                || window.SpellDetailsWindow.activeSelf != originalDetailsOpen
            )
                throw new InvalidOperationException("Tooltip window state was not restored.");
        }
        return output.ToString();
    }
}
