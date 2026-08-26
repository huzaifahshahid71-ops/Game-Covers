from .online import *

# ---------------------------- artwork selection / cache ----------------------------

def artwork_score(g):
    try:
        w, h = int(g.get("width") or 0), int(g.get("height") or 0)
    except Exception:
        return -10**12
    if not w or not h or h <= w:
        return -10**12

    ratio = w / h
    preferred = [(2160, 3840), (1080, 1920)]
    exact_bonus = 0
    for pw, ph in preferred:
        if (w, h) == (pw, ph):
            exact_bonus = 50000 if pw == 2160 else 40000
            break

    # Both 9:16 and classic 2:3 are acceptable portrait-cover shapes.
    ratio_error = min(abs(ratio - 9/16), abs(ratio - 2/3), abs(ratio - 342/482))
    area_score = math.log2(max(w * h, 1)) * 1000
    ratio_score = max(0.0, 7000.0 - ratio_error * 24000.0)

    # SGDB's community score/likes can help choose a more representative cover.
    community = g.get("score")
    try:
        community = float(community or 0) * 40.0
    except Exception:
        community = 0.0

    # Prefer static art for Windows icons.
    mime = str(g.get("mime") or "").lower()
    animated_penalty = 5000 if "webp" in mime and g.get("animated") else 0
    return exact_bonus + area_score + ratio_score + community - animated_penalty


def choose_artwork(grids):
    portrait = []
    for g in grids:
        try:
            if int(g.get("height") or 0) > int(g.get("width") or 0):
                portrait.append(g)
        except Exception:
            pass
    return max(portrait, key=artwork_score) if portrait else None


def download(url):
    r = session.get(url, timeout=90)
    r.raise_for_status()
    return r.content


def validate_image(image_bytes, portrait_required=True):
    with Image.open(BytesIO(image_bytes)) as im:
        w, h = im.size
        if portrait_required and h <= w:
            raise RuntimeError(f"Artwork is not portrait ({w}x{h})")
        if min(w, h) < 256:
            raise RuntimeError(f"Artwork is too small ({w}x{h})")
        return w, h


def image_candidate_score(width, height, source):
    """Compare already-downloaded portrait candidates from different sources."""
    if not width or not height or height <= width:
        return -10**12
    ratio = width / height
    ratio_error = min(abs(ratio - 9/16), abs(ratio - 2/3), abs(ratio - 342/482))
    area = math.log2(max(width * height, 1)) * 1000
    ratio_bonus = max(0.0, 7000.0 - ratio_error * 24000.0)
    exact = 50000 if (width, height) == (2160, 3840) else 40000 if (width, height) == (1080, 1920) else 0
    official_bonus = 1200 if source == "Steam official" else 0
    return exact + area + ratio_bonus + official_bonus


def steam_cover_urls(appid):
    bases = [
        "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps",
        "https://cdn.cloudflare.steamstatic.com/steam/apps",
        "https://cdn.akamai.steamstatic.com/steam/apps",
    ]
    names = ["library_600x900_2x.jpg", "library_600x900_2x.png", "library_600x900.jpg"]
    return [f"{base}/{appid}/{name}" for base in bases for name in names]


def fetch_steam_official_cover(appid):
    if not appid:
        return None
    for url in steam_cover_urls(appid):
        try:
            r = session.get(url, timeout=25)
            if r.status_code != 200 or not r.content:
                continue
            ctype = r.headers.get("Content-Type", "")
            if "image" not in ctype.lower():
                continue
            w, h = validate_image(r.content, portrait_required=True)
            return {"bytes": r.content, "url": url, "width": w, "height": h, "source": "Steam official"}
        except Exception:
            continue
    return None


def safe_file_part(s):
    s = re.sub(r'[<>:"/\\|?*]', "_", str(s))
    return re.sub(r"\s+", " ", s).strip()[:120] or "game"


def make_icon(image_bytes, ico_path):
    source = Image.open(BytesIO(image_bytes)).convert("RGBA")
    source.thumbnail((256, 256), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    canvas.alpha_composite(source, ((256 - source.width) // 2, (256 - source.height) // 2))
    canvas.save(
        ico_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )


def cache_artwork(cache, name, image_bytes, source_tag, keep_original=True):
    art_dir = cache / "artwork"
    art_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(image_bytes).hexdigest()[:10]
    stem = f"{safe_file_part(name)}__{safe_file_part(source_tag)}__{digest}"
    png = art_dir / f"{stem}.png"
    ico = art_dir / f"{stem}.ico"
    if keep_original and not png.exists():
        with Image.open(BytesIO(image_bytes)) as im:
            im.convert("RGBA").save(png, "PNG")
    make_icon(image_bytes, ico)
    return (png if keep_original else None), ico


def load_overrides(cache):
    path = cache / "cover_overrides.json"
    if not path.exists():
        path.write_text(
            json.dumps({
                "_examples": {
                    "007": {"search": "007 First Light"},
                    "Some Game": {"sgdb_game_id": 12345},
                    "Another Game": {"steam_appid": 123456},
                    "Local Cover Example": {"image": r"C:\\Path\\cover.jpg"},
                    "Direct Image Example": {"url": "https://example.com/cover.jpg"}
                }
            }, indent=2),
            encoding="utf-8",
        )
        return {}, path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}, path
    except Exception:
        return {}, path


def resolve_override(api_key, override, name):
    if not override:
        return None
    if override.get("image"):
        p = Path(os.path.expandvars(override["image"]))
        if not p.is_file():
            raise RuntimeError(f"Override image not found: {p}")
        b = p.read_bytes()
        w, h = validate_image(b)
        return {"bytes": b, "source": "Local override", "width": w, "height": h, "identity": name}
    if override.get("url"):
        b = download(override["url"])
        w, h = validate_image(b)
        return {"bytes": b, "source": "URL override", "width": w, "height": h, "identity": name}
    if override.get("steam_appid"):
        appid = int(override["steam_appid"])
        game = sgdb_game_by_steam(api_key, appid)
        return {"game": game, "steam_appid": appid, "identity": game.get("name") if game else name, "reason": "Override Steam AppID"}
    if override.get("sgdb_game_id"):
        gid = int(override["sgdb_game_id"])
        return {"game": {"id": gid, "name": name}, "steam_appid": None, "identity": name, "reason": "Override SGDB game id"}
    if override.get("search"):
        return {"search": str(override["search"])}
    return None


# ---------------------------- Explorer overlays ----------------------------

def refresh_explorer():
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass


def create_blank_ico(path):
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    img.save(path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])


def remove_shortcut_arrows(cache_dir):
    if winreg is None:
        raise RuntimeError("winreg is unavailable")
    blank = cache_dir / "_blank_arrow.ico"
    if not blank.exists():
        create_blank_ico(blank)
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "29", 0, winreg.REG_SZ, str(blank))
    refresh_explorer()


def restore_shortcut_arrows():
    if winreg is None:
        return
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, "29")
    except FileNotFoundError:
        pass
    refresh_explorer()

