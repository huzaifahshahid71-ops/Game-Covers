# 🎮 Game Covers

**Game Covers** turns an ordinary folder of Windows game shortcuts into a clean, cover-art-style game library.

Instead of small executable icons, repeated generic icons, shortcut arrows, and UAC shield overlays, Game Covers finds genuine portrait artwork, builds Windows `.ico` files, and applies them to your existing `.lnk` shortcuts while preserving how those shortcuts launch.

> Windows 10/11 only.

## ✨ What it does

- Scans a folder containing Windows `.lnk` game shortcuts.
- Identifies each game using multiple signals instead of blindly trusting one database search.
- Uses embedded Steam AppIDs when they are available.
- Cross-checks names against the Steam Store before falling back to strict SteamGridDB title matching.
- Uses executable metadata such as Product Name/File Description as extra identity evidence.
- Rejects ambiguous matches instead of assigning an obviously wrong cover.
- Detects duplicate-match collisions so two different shortcuts do not silently receive the same game's artwork.
- Prefers genuine high-resolution portrait artwork.
- Prioritizes 2160×3840 and 1080×1920 when those originals actually exist.
- Can use both SteamGridDB portrait grids and official Steam portrait library artwork.
- Creates multi-resolution Windows `.ico` files.
- Caches artwork and icons locally.
- Backs up shortcuts before changing them.
- Can remove the Windows shortcut-arrow overlay for the current Windows account.
- Can visually hide the UAC shield from the shortcut while preserving normal Windows elevation behavior.
- Includes manual overrides for difficult or ambiguous titles.

## 🧠 Smarter matching

The original prototype relied too heavily on SteamGridDB autocomplete. That can produce bad results for sequels and similar franchise names.

Game Covers now resolves identity in this order:

1. **Steam AppID already present in the shortcut** (`steam://rungameid/...`, `steam://run/...`, `-applaunch ...`).
2. **Nearby `steam_appid.txt`** when a game launches its executable directly.
3. **Steam Store corroboration** using the shortcut name and local executable metadata.
4. **Strict SteamGridDB title matching** with sequel-number penalties, typo aliases, confidence thresholds, and ambiguity checks.
5. **Manual override** when a title is genuinely unclear.

A missing cover is preferable to a confident-looking wrong cover.

## 🖼️ Artwork selection

Game Covers prefers portrait cover art and scores candidates using:

- resolution,
- portrait aspect ratio,
- exact preferred resolutions,
- SteamGridDB community score when available,
- and official Steam portrait art as a second source.

Preferred originals:

1. `2160 × 3840`
2. `1080 × 1920`
3. otherwise the strongest genuine portrait original available

The app does **not** upscale a tiny image just to report a larger resolution.

## 🛡️ UAC and security

Game Covers does **not** bypass UAC.

When **Hide UAC shield** is enabled, the shortcut points to a tiny local launcher instead of directly exposing the elevated executable as the shortcut target. The launcher preserves:

- original target,
- original arguments,
- original working directory,
- and the original shortcut's explicit *Run as administrator* behavior.

The launcher uses Windows `ShellExecute`. If the original shortcut was explicitly marked to run as administrator, the launcher requests the normal `runas` verb. If the game executable itself has a manifest requiring elevation, Windows still shows the normal UAC prompt.

The goal is only to clean up the **visual shortcut overlay**, not weaken Windows security.

### Important note about old v3-wrapped shortcuts

An older prototype changed shortcuts without preserving every original field. Game Covers can recover the original target from those v3 VBS wrappers, but arguments already discarded by the old version cannot be reconstructed automatically. For that reason, the final app creates backups before modifying shortcuts.

## ↗ Shortcut arrow setting

Windows shortcut arrows are removed using the per-user registry location:

`HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons`

value `29` is pointed to a transparent icon.

This affects shortcut arrows **globally for the current Windows account**, not only the game folder. Game Covers includes a **Restore Windows shortcut arrows** option in Settings.

Explorer may occasionally require a restart/sign-out to fully refresh its icon cache.

## 🔑 SteamGridDB API key

Game Covers uses the SteamGridDB v2 API:

`https://www.steamgriddb.com/api/v2`

Create/copy your API key from your SteamGridDB profile preferences, then paste it into the app. Authentication is sent as a Bearer API key.

The key is not written into the repository or bundled into the executable.

## 🚀 Running from source

Requirements:

- Windows 10 or Windows 11
- Python 3.11+

Install and run:

```bat
py -m pip install -r requirements.txt
py Game_Covers.py
```

Or simply double-click:

`run_source.bat`

## 🏗️ Build the EXE automatically

Double-click:

`build.bat`

The script automatically:

1. updates pip,
2. installs the runtime dependencies and PyInstaller,
3. cleans the previous build,
4. compiles a windowed one-file executable,
5. embeds the Game Covers icon,
6. bundles CustomTkinter assets.

Output:

`dist\Game Covers.exe`

No manual PyInstaller command is required.

## ☁️ GitHub Actions build

The repository also contains `.github/workflows/build-windows.yml`.

Every relevant push to `main` can build the Windows executable on a Windows GitHub runner and upload it as the `Game-Covers-Windows` workflow artifact.

## 🛠️ Manual overrides

Some shortcut names are inherently ambiguous. A shortcut named only `007`, for example, should not be guessed automatically.

Click **Open Overrides** after choosing the shortcut folder. Game Covers creates:

`.game_cover_cache\cover_overrides.json`

Supported override types include:

```json
{
  "007": {
    "search": "007 First Light"
  },
  "Example Steam Game": {
    "steam_appid": 123456
  },
  "Example SGDB Game": {
    "sgdb_game_id": 12345
  },
  "Local Artwork": {
    "image": "C:\\Covers\\my-cover.jpg"
  },
  "Direct Artwork": {
    "url": "https://example.com/cover.jpg"
  }
}
```

## 📁 Cache structure

By default the cache is stored beside your shortcut folder:

`.game_cover_cache\`

It contains generated icons, downloaded artwork (when enabled), launcher scripts, overrides, and original shortcut backups.

Artwork filenames include a content hash so an old incorrect cover cannot silently poison a corrected match later.

## 🖥️ Best Explorer view

For the clean cover-library effect:

**File Explorer → View → Extra large icons**

Portrait icons naturally retain transparent space on the sides because Windows icons themselves are square.

## ⚠️ Limitations

- Some third-party launchers may use unusual shortcut structures that require a manual override or icon-only mode.
- Microsoft Store/UWP-style shortcuts can behave differently from standard executable shortcuts.
- Games missing from both SteamGridDB and Steam's portrait assets need manual artwork.
- SteamGridDB artwork is community-provided; the app improves identity matching but cannot guarantee every submitted image is perfect.
- Removing the shortcut arrow changes the overlay globally for the current Windows account.
- Windows may temporarily display a cached icon until Explorer refreshes.

## 📦 Main files

- `Game_Covers.py` — application source
- `build.bat` — one-click Windows EXE builder
- `run_source.bat` — installs dependencies and launches the source version
- `requirements.txt` — runtime dependencies
- `requirements-dev.txt` — build dependencies
- `assets/game_covers.ico` — Windows app icon
- `.github/workflows/build-windows.yml` — automatic GitHub Windows build

## 🙏 Credits

Artwork discovery uses [SteamGridDB](https://www.steamgriddb.com/) and, when available, official Steam library artwork.

SteamGridDB, Steam, and individual game names/artwork belong to their respective owners. Game Covers is an independent utility and is not affiliated with Valve or SteamGridDB.

## 📄 License

MIT License. See `LICENSE`.
