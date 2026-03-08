SELECT
    c.stable_key AS character_stable_key,
    c.display_name,
    cd.dialog_index,
    cd.dialog_text,
    cd.keywords,
    cd.give_item_stable_key,
    cd.assign_quest_stable_key,
    cd.complete_quest_stable_key,
    cd.repeating_quest_dialog,
    cd.kill_self_on_say,
    cd.required_quest_stable_key,
    cd.spawn_character_stable_key
FROM character_dialogs cd
JOIN characters c ON c.stable_key = cd.character_stable_key
ORDER BY c.display_name, c.stable_key, cd.dialog_index;
