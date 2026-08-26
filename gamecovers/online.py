from .shortcuts import *

# ---------------------------- API / online sources ----------------------------

def api_get(api_key, endpoint):
    r = session.get(
        BASE_URL + endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
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
        r = session.get(
            STEAM_SEARCH_URL,
            params={"term": query, "l": "english", "cc": "US"},
            timeout=20,
        )
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
    for q in extra_identity_queries(info):
        if normalize_title(q) not in {normalize_title(x) for x in aliases}:
            aliases.append(q)

    # Strongest signal: a Steam app id embedded directly in the shortcut.
    appid = extract_steam_appid(info)
    if appid:
        game = sgdb_game_by_steam(api_key, appid)
        if game:
            return game, "Steam shortcut AppID", 100.0, appid, aliases

    # Second signal: independently resolve the title against Steam Store, then map
    # that exact app id back into SteamGridDB. This avoids title-only SGDB mistakes.
    steam_item, steam_score, steam_margin = best_steam_store_match(aliases)
    if steam_item and steam_score >= 88 and steam_margin >= 4:
        steam_appid = int(steam_item["id"])
        game = sgdb_game_by_steam(api_key, steam_appid)
        if game:
            return game, f"Steam Store corroboration ({steam_item.get('name')})", steam_score, steam_appid, aliases

    # Final route: strict multi-query SGDB matching, not "first result wins".
    games = sgdb_candidates(api_key, aliases)
    scored = []
    for g in games:
        gid = int(g.get("id"))
        score = best_alias_score(aliases, g.get("name", ""))
        # Prevent two differently named shortcuts from silently collapsing to the
        # same game entry (the Resident Evil repetition seen in v3).
        if gid in used_game_ids and normalize_title(used_game_ids[gid]) != normalize_title(name):
            score -= 28.0
        scored.append((score, g))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return None, "No candidates", 0.0, None, aliases

    best_score, best = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_score - second

    # Be intentionally conservative. A missing icon is better than the wrong game.
    if best_score < 76:
        return None, f"Low-confidence match ({best_score:.1f})", best_score, None, aliases
    if best_score < 94 and margin < 5:
        return None, f"Ambiguous match ({best_score:.1f}, margin {margin:.1f})", best_score, None, aliases

    return best, "Strict SteamGridDB title match", best_score, None, aliases

