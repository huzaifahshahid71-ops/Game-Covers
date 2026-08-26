# Changelog

## v1.3 — 2026-08-26

### Added
- Custom cover replacement for **any** game, including games that were matched automatically.
- Manual cover manager for local images and direct image URLs.
- Persistent manual cover overrides stored in the local cache.
- Durable cached copies of user-selected local cover images.
- Automatic prompt to resolve skipped games after processing.

### Improved
- Cleaner, simpler GUI focused on folder selection, results, preview, activity log, and cover management.
- Safer game matching using shortcut metadata, Steam information, Steam Store corroboration, and SteamGridDB.
- Better sequel-number handling and duplicate-match detection.
- High-resolution portrait artwork selection with official Steam artwork as an additional source.

### Existing behavior retained
- Shortcut backups before modification.
- Multi-resolution `.ico` generation.
- Optional shortcut-arrow removal.
- Optional visual hiding of the UAC shield while retaining normal Windows elevation behavior.

## Earlier prototypes

Earlier versions were experimental builds used to develop matching, artwork selection, shortcut preservation, and the GUI. v1.3 is the first version intended to represent the current public project state.
