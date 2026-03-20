"""Quest guide generation pipeline.

Reads quest data from the processed SQLite database, builds structured
quest guide entries with auto-generated steps, merges with manual curation
layer, and produces the final quest-guide.json for the BepInEx mod.
"""
