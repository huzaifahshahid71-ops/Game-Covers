# 🎮 Game Covers

**Game Covers v1.3** turns an ordinary folder of Windows game shortcuts into a clean, cover-art-style game library.

It identifies your games, finds genuine portrait artwork, generates Windows `.ico` files, and applies them to your existing `.lnk` shortcuts. If you dislike an automatic cover—or a game cannot be matched—you can replace it with **any image you choose**.

> Windows 10/11 only.

## ✨ Highlights

- Scans a folder containing Windows `.lnk` game shortcuts.
- Matches games using shortcut metadata, Steam information, the Steam Store, and SteamGridDB instead of blindly trusting one search result.
- Uses Steam AppIDs when they can be recovered from the shortcut or nearby `steam_appid.txt` files.
- Penalizes wrong sequel numbers and rejects ambiguous matches instead of assigning obviously incorrect artwork.
- Detects duplicate match collisions such as multiple Resident Evil shortcuts resolving to the same game.
- Prefers genuine high-resolution portrait artwork.
- Prioritizes `2160×3840` and `1080×1920` when originals at those sizes actually exist.
- Uses SteamGridDB portrait grids and official Steam portrait library artwork.
- Generates multi-resolution Windows `.ico` files.
- Backs up shortcuts before modifying them.
- Caches downloaded/generated artwork locally.
- Can remove the Windows shortcut-arrow overlay.
- Can visually hide the UAC/admin shield while preserving normal Windows elevation behavior.
- Supports **custom covers for every game**, not only games that were skipped.

## 🖼️ Custom covers for any game

v1.3 gives you full manual control over the artwork.

After choosing a shortcut folder, use **Manage / Replace Covers** to see every game—whether its automatic cover was found or not. Select a game and either:

- choose a local PNG/JPG/JPEG/WebP/BMP image, or
- paste a direct image URL.

You can also select a game in the main Results list and click **Choose / Replace This Cover…**.

Manual choices are written to:

```text
.game_cover_cache\cover_overrides.json
```

Local custom images are copied into the Game Covers cache so the override keeps working even if the original file is later moved or deleted.

If you remove a saved custom choice, the current icon remains until the next automatic scan; the next run will return that game to automatic matching/artwork selection.

## 🧠 Smarter matching

Automatic identity resolution follows this general order:

1. Steam AppID embedded in the shortcut (`steam://rungameid/...`, `steam://run/...`, `-applaunch ...`).
2. Nearby `steam_appid.txt` where available.
3. Steam Store corroboration using the shortcut title and executable metadata.
4. Strict SteamGridDB title matching with typo aliases, sequel-number penalties, confidence thresholds, and ambiguity checks.
5. Manual override whenever you prefer your own choice.

A missing cover is preferable to a confident-looking wrong cover.

## 🎨 Artwork selection

Game Covers scores portrait candidates using resolution, aspect ratio, preferred exact resolutions, SteamGridDB metadata, and official Steam portrait art.

Preferred originals:

1. `2160 × 3840`
2. `1080 × 1920`
3. otherwise the strongest genuine portrait original available

It does **not** upscale a tiny image merely to claim a larger resolution.

## 🔑 SteamGridDB API key

Game Covers uses the SteamGridDB v2 API:

```text
https://www.steamgriddb.com/api/v2
```

Generate/copy an API key from your SteamGridDB profile preferences and paste it into the app. Authentication is sent using Bearer API-key authentication.

Your API key is not hard-coded into the source or bundled in the repository.

## 🛡️ UAC and shortcut behavior

Game Covers does **not** bypass UAC.

When the shield-hiding option is enabled, a small local launcher is used so the shortcut can display the chosen cover cleanly while preserving the original launch target, arguments, working directory, and explicit Run-as-administrator behavior as far as the source shortcut still contains them.

If the original shortcut explicitly requires administrator rights, Windows still uses its normal elevation prompt. If the game executable itself requests elevation through its manifest, Windows still handles that normally.

The goal is to clean up the **visual shortcut icon**, not weaken Windows security.

### Old v3-wrapped shortcuts

An older prototype did not preserve every original shortcut field. Game Covers can recover the target from those old wrappers when possible, but arguments already discarded by that old version cannot be reconstructed. v1.3 therefore backs up shortcuts before changing them.

## ↗ Shortcut-arrow option

The arrow-hiding option uses the current-user Explorer registry location:

```text
HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons
```

Value `29` is pointed to a transparent icon. This affects shortcut arrows **globally for the current Windows account**, not only the selected game folder.

Game Covers includes a **Restore Shortcut Arrows** button. Explorer may sometimes need a restart/sign-out before every icon is redrawn.

## 🚀 Run from source

Requirements:

- Windows 10 or Windows 11
- Python 3.11+

Either double-click:

```text
run_source.bat
```

or run:

```bat
py -m pip install -r requirements.txt
py Game_Covers.py
```

## 🏗️ Build the EXE

Double-click:

```text
build.bat
```

The builder installs the required Python packages and PyInstaller, cleans old build output, and creates:

```text
dist\Game Covers.exe
```

No manual PyInstaller command is required.

## ☁️ GitHub Actions

`.github/workflows/build-windows.yml` can also build the Windows executable on a Windows GitHub runner whenever relevant files change on `main`, or when the workflow is started manually.

The compiled file is uploaded as the `Game-Covers-Windows` workflow artifact.

## 📦 Releases branch

The repository has a dedicated **`releases`** branch for prebuilt Windows binaries.

Source development lives on `main`. Prebuilt versions such as `Game Covers.exe` can be uploaded to the `releases` branch separately.

## 📁 Cache structure

By default Game Covers creates:

```text
<your shortcut folder>\.game_cover_cache\
```

The cache contains downloaded artwork, generated icons, manual-cover copies, launcher files, overrides, and original shortcut backups.

Artwork filenames include content hashes so an old incorrect cover cannot silently replace a corrected match later.

## 🖥️ Best Explorer view

For the cover-library look:

**File Explorer → View → Extra large icons**

Windows icons are square, so portrait artwork naturally has transparent space at the sides inside the generated icon.

## ⚠️ Notes and limitations

- Some unusual third-party launchers may require a manual cover/override.
- Microsoft Store/UWP-style shortcuts can behave differently from standard executable shortcuts.
- SteamGridDB artwork is community-provided, so manual replacement remains useful even when a game was identified correctly.
- Removing shortcut arrows changes the overlay globally for the current Windows account.
- Explorer can temporarily display an older cached icon until its icon cache refreshes.
- Game Covers does not redistribute the game artwork itself through this repository; artwork is fetched or chosen by the user at runtime.

## 📂 Source layout

- `Game_Covers.py` — application entry point
- `gamecovers_common.py` — title matching and shortcut helpers
- `gamecovers_services.py` — Steam/SteamGridDB, artwork, cache, and Explorer services
- `gamecovers_widgets.py` — cover-management dialog and preview helpers
- `gamecovers_app_shell.py` — main window construction
- `gamecovers_app_ui.py` — main UI interactions
- `gamecovers_app.py` — processing and manual-cover application logic
- `build.bat` — one-click Windows EXE builder
- `run_source.bat` — dependency install + source launcher
- `requirements.txt` — Python dependencies
- `assets/game_covers.ico` — application icon
- `.github/workflows/build-windows.yml` — Windows build workflow

## 🙏 Credits

Automatic artwork discovery uses [SteamGridDB](https://www.steamgriddb.com/) and, where available, official Steam library artwork.

SteamGridDB, Steam, and individual game names/artwork belong to their respective owners. Game Covers is an independent utility and is not affiliated with Valve or SteamGridDB.

## 📄 License

MIT License. See `LICENSE`.
