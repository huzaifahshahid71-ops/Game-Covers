from gamecovers_common import *

def api_get(api_key, endpoint):
    r = session.get(BASE_URL + endpoint, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    if r.status_code == 401:
        raise RuntimeError("SteamGridDB rejected the API key (401 Unauthorized).")
    r.raise_for_status()
    return r.json()


def sgdb_game_by_steam(api_key, appid):
    try:
        data = api_get(api_key, f"/games/steam/{appid}").get("data")
        if isinstance(data, list):
            return data[0] if data else None
        return data if isinstance(data, dict) else None
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise


def sgdb_candidates(api_key, queries):
    found = {}
    for q in queries:
        if not q:
            continue
        try:
            data = api_get(api_key, f"/search/autocomplete/{quote(q)}")
            for g in data.get("data", []) or []:
                gid = g.get("id")
                if gid is not None:
                    found[int(gid)] = g
        except Exception:
            continue
    return list(found.values())


def get_grids(api_key, game_id):
    return api_get(api_key, f"/grids/game/{game_id}").get("data", []) or []


def steam_store_candidates(query):
    try:
        r = session.get(STEAM_SEARCH_URL, params={"term": query, "l": "english", "cc": "US"}, timeout=20)
        r.raise_for_status()
        return (r.json() or {}).get("items", []) or []
    except Exception:
        return []


def best_steam_store_match(aliases):
    merged = {}
    for q in aliases[:5]:
        for item in steam_store_candidates(q):
            appid = item.get("id")
            if appid is not None:
                merged[int(appid)] = item
    scored = []
    for item in merged.values():
        s = best_alias_score(aliases, item.get("name", ""))
        scored.append((s, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return None, 0.0, 0.0
    best_score, best = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    return best, best_score, best_score - second


def choose_sgdb_game(api_key, name, info, used_game_ids):
    aliases = title_aliases(name)
    alias_norms = {normalize_title(x) for x in aliases}
    for q in extra_identity_queries(info):
        if normalize_title(q) not in alias_norms:
            aliases.append(q)

    appid = extract_steam_appid(info)
    if appid:
        game = sgdb_game_by_steam(api_key, appid)
        if game:
            return game, "Steam shortcut AppID", 100.0, appid, aliases

    steam_item, steam_score, steam_margin = best_steam_store_match(aliases)
    if steam_item and steam_score >= 88 and steam_margin >= 4:
        steam_appid = int(steam_item["id"])
        game = sgdb_game_by_steam(api_key, steam_appid)
        if game:
            return game, f"Steam Store corroboration ({steam_item.get('name')})", steam_score, steam_appid, aliases

    games = sgdb_candidates(api_key, aliases)
    scored = []
    for g in games:
        gid = int(g.get("id"))
        score = best_alias_score(aliases, g.get("name", ""))
        if gid in used_game_ids and normalize_title(used_game_ids[gid]) != normalize_title(name):
            score -= 28.0
        scored.append((score, g))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return None, "No candidates", 0.0, None, aliases

    best_score, best = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_score - second

    if best_score < 76:
        return None, f"Low-confidence match ({best_score:.1f})", best_score, None, aliases
    if best_score < 94 and margin < 5:
        return None, f"Ambiguous match ({best_score:.1f}, margin {margin:.1f})", best_score, None, aliases

    return best, "Strict SteamGridDB title match", best_score, None, aliases


# ---------------------------- artwork / cache ----------------------------

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
    ratio_error = min(abs(ratio - 9/16), abs(ratio - 2/3), abs(ratio - 342/482))
    area_score = math.log2(max(w * h, 1)) * 1000
    ratio_score = max(0.0, 7000.0 - ratio_error * 24000.0)
    community = g.get("score")
    try:
        community = float(community or 0) * 40.0
    except Exception:
        community = 0.0
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
    canvas.save(ico_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def cache_artwork(cache, name, image_bytes, source_tag):
    art_dir = cache / "artwork"
    art_dir.mkdir(exist_ok=True)
    digest = hashlib.sha1(image_bytes).hexdigest()[:10]
    stem = f"{safe_file_part(name)}__{safe_file_part(source_tag)}__{digest}"
    png = art_dir / f"{stem}.png"
    ico = art_dir / f"{stem}.ico"
    if not png.exists():
        with Image.open(BytesIO(image_bytes)) as im:
            im.convert("RGBA").save(png, "PNG")
    make_icon(png.read_bytes(), ico)
    return png, ico


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


def save_overrides(cache, overrides):
    path = cache / "cover_overrides.json"
    payload = {k: v for k, v in overrides.items()}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            examples = {k: v for k, v in existing.items() if k.startswith("_")}
            payload = {**examples, **payload}
        except Exception:
            pass
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def resolve_override(api_key, override, name):
    if not override:
        return None
    if override.get("image"):
        p = Path(os.path.expandvars(override["image"]))
        if not p.is_file():
            raise RuntimeError(f"Override image not found: {p}")
        b = p.read_bytes()
        w, h = validate_image(b, portrait_required=False)
        return {"bytes": b, "source": "Local override", "width": w, "height": h, "identity": name}
    if override.get("url"):
        b = download(override["url"])
        w, h = validate_image(b, portrait_required=False)
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


