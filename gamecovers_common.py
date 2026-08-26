import ctypes
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import struct
import threading
import unicodedata
import webbrowser
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import win32com.client

try:
    import win32api
except Exception:
    win32api = None

try:
    import winreg
except Exception:
    winreg = None


APP_NAME = "Game Covers"
APP_VERSION = "1.3"
BASE_URL = "https://www.steamgriddb.com/api/v2"
PREFERENCES_URL = "https://www.steamgriddb.com/profile/preferences"
STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
RUNAS_LINK_FLAG = 0x00002000

session = requests.Session()
session.headers.update({
    "User-Agent": "GameCovers/1.3",
    "Accept": "application/json,image/*,*/*;q=0.8",
})


# ---------------------------- title / identity helpers ----------------------------

def clean_game_name(name):
    name = re.sub(r"\.lnk$", "", name, flags=re.I)
    name = re.sub(r"\b(shortcut|launcher)\b", "", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip(" -_")


def normalize_title(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = s.replace("™", " ").replace("®", " ").replace("©", " ")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_aliases(name):
    out = []

    def add(v):
        v = clean_game_name(v)
        if v and v not in out:
            out.append(v)

    add(name)
    add(re.sub(r"\s*[-–—:]\s*", " ", name))

    m = re.match(r"^(.*?\D)\s+(\d+)\s*[-–—:]\s*(.+)$", name)
    if m:
        add(f"{m.group(1)} {m.group(3)}")
        add(f"{m.group(1)} {m.group(2)} {m.group(3)}")

    substitutions = {
        r"\brequim\b": "requiem",
        r"\bassasins\b": "assassins",
        r"\bbeam\s*ng\s*drive\b": "beamng drive",
    }
    for current in list(out):
        fixed = current
        for pat, repl in substitutions.items():
            fixed = re.sub(pat, repl, fixed, flags=re.I)
        add(fixed)

    canon = {
        "resident evil 8 village": "Resident Evil Village",
        "resident evil 9 requiem": "Resident Evil Requiem",
        "resident evil 9 requim": "Resident Evil Requiem",
        "angry birds classic": "Angry Birds",
        "doom the dark ages": "DOOM: The Dark Ages",
        "elden ring nightreign": "ELDEN RING NIGHTREIGN",
        "expedition 33": "Clair Obscur: Expedition 33",
        "beam ng drive": "BeamNG.drive",
    }
    for current in list(out):
        key = normalize_title(current)
        if key in canon:
            add(canon[key])

    return out


def token_f1(a, b):
    aa, bb = set(normalize_title(a).split()), set(normalize_title(b).split())
    if not aa or not bb:
        return 0.0
    overlap = len(aa & bb)
    p = overlap / len(bb)
    r = overlap / len(aa)
    return 2 * p * r / (p + r) if (p + r) else 0.0


def numeric_tokens(s):
    return set(re.findall(r"\b\d+\b", normalize_title(s)))


def similarity(a, b):
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    f1 = token_f1(na, nb)
    score = max(seq * 100.0, (0.55 * seq + 0.45 * f1) * 100.0)

    nums_a, nums_b = numeric_tokens(na), numeric_tokens(nb)
    if nums_a and nums_b and nums_a != nums_b:
        score -= 35.0
    elif nums_a and not nums_b:
        score -= 7.0
    return score


def best_alias_score(aliases, candidate):
    return max((similarity(a, candidate) for a in aliases), default=0.0)


# ---------------------------- shortcut preservation ----------------------------

def read_runas_flag(path):
    try:
        data = Path(path).read_bytes()
        if len(data) < 0x18:
            return False
        flags = struct.unpack_from("<I", data, 0x14)[0]
        return bool(flags & RUNAS_LINK_FLAG)
    except Exception:
        return False


def clear_runas_flag(path):
    p = Path(path)
    data = bytearray(p.read_bytes())
    if len(data) < 0x18:
        return
    flags = struct.unpack_from("<I", data, 0x14)[0]
    flags &= ~RUNAS_LINK_FLAG
    struct.pack_into("<I", data, 0x14, flags)
    p.write_bytes(data)


def shortcut_info(path):
    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(path))
    return {
        "target": sc.Targetpath or "",
        "arguments": sc.Arguments or "",
        "working_directory": sc.WorkingDirectory or "",
        "description": sc.Description or "",
        "icon_location": sc.IconLocation or "",
        "name": clean_game_name(Path(path).stem),
        "run_as_admin": read_runas_flag(path),
    }


def vbs_unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('""', '"')
    return ""


def recover_v3_wrapper(info):
    target = Path(info.get("target") or "").name.lower()
    if target not in ("wscript.exe", "cscript.exe"):
        return info, None

    args = info.get("arguments") or ""
    m = re.search(r'"([^"]+\.vbs)"', args, flags=re.I)
    if not m:
        return info, None
    vbs = Path(m.group(1))
    if not vbs.exists():
        return info, None

    try:
        text = vbs.read_text(encoding="utf-8", errors="replace")
        run_m = re.search(r"(?im)^\s*shell\.Run\s+(.+?),\s*1\s*,\s*False\s*$", text)
        cwd_m = re.search(r"(?im)^\s*shell\.CurrentDirectory\s*=\s*(.+?)\s*$", text)
        recovered_target = vbs_unquote(run_m.group(1)) if run_m else ""
        recovered_cwd = vbs_unquote(cwd_m.group(1)) if cwd_m else ""
        if recovered_target:
            new = dict(info)
            new["target"] = recovered_target
            new["arguments"] = ""
            new["working_directory"] = recovered_cwd or str(Path(recovered_target).parent)
            new["run_as_admin"] = False
            return new, "Detected an old v3 WScript wrapper; target was recovered, but the old shortcut may already have lost its original arguments."
    except Exception:
        pass
    return info, None


def backup_shortcut(shortcut, backup_dir):
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / shortcut.name
    if not dest.exists():
        shutil.copy2(shortcut, dest)
    return dest


def vbs_string(s):
    return '"' + str(s).replace('"', '""') + '"'


def create_vbs_launcher(cache_dir, game_name, original):
    launchers = cache_dir / "launchers"
    launchers.mkdir(exist_ok=True)
    safe = re.sub(r'[^A-Za-z0-9._ -]', "_", game_name)
    vbs = launchers / f"{safe}.vbs"

    target = original.get("target") or ""
    args = original.get("arguments") or ""
    working = original.get("working_directory") or ""
    if not working and target and Path(target).suffix.lower() in (".exe", ".com", ".bat", ".cmd"):
        working = str(Path(target).parent)
    verb = "runas" if original.get("run_as_admin") else ""

    script = (
        'On Error Resume Next\n'
        'Set sh = CreateObject("Shell.Application")\n'
        f'sh.ShellExecute {vbs_string(target)}, {vbs_string(args)}, {vbs_string(working)}, {vbs_string(verb)}, 1\n'
        'If Err.Number <> 0 Then\n'
        f'  MsgBox "Unable to launch the game: " & Err.Description, 16, "{APP_NAME}"\n'
        'End If\n'
    )
    vbs.write_text(script, encoding="utf-8")
    return vbs


def apply_icon_only(shortcut, icon):
    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(shortcut))
    sc.IconLocation = f"{icon},0"
    sc.Save()


def apply_icon_via_launcher(shortcut, icon, launcher, original):
    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(shortcut))
    sc.Targetpath = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "wscript.exe")
    sc.Arguments = f'//Nologo "{launcher}"'
    sc.WorkingDirectory = str(Path(launcher).parent)
    sc.IconLocation = f"{icon},0"
    sc.Description = original.get("description") or "Game launcher"
    sc.Save()
    clear_runas_flag(shortcut)


def extract_steam_appid(info):
    text = " ".join([info.get("target", ""), info.get("arguments", "")])
    for pat in (r"steam://rungameid/(\d+)", r"steam://run/(\d+)", r"(?:^|\s)-applaunch\s+(\d+)"):
        m = re.search(pat, text, flags=re.I)
        if m:
            return int(m.group(1))

    target = info.get("target") or ""
    try:
        tp = Path(target)
        if tp.suffix.lower() == ".exe":
            folders = [tp.parent]
            folders.extend(list(tp.parents)[1:4])
            seen = set()
            for folder in folders:
                key = str(folder).lower()
                if key in seen:
                    continue
                seen.add(key)
                candidate = folder / "steam_appid.txt"
                if candidate.is_file():
                    value = candidate.read_text(encoding="utf-8", errors="ignore").strip()
                    if value.isdigit():
                        return int(value)
    except Exception:
        pass
    return None


def exe_product_name(target):
    if not win32api or not target or not Path(target).is_file() or Path(target).suffix.lower() != ".exe":
        return ""
    try:
        trans = win32api.GetFileVersionInfo(target, r"\VarFileInfo\Translation")
        if not trans:
            return ""
        lang, codepage = trans[0]
        for field in ("ProductName", "FileDescription", "InternalName"):
            key = fr"\StringFileInfo\{lang:04x}{codepage:04x}\{field}"
            value = win32api.GetFileVersionInfo(target, key)
            if value and len(str(value).strip()) >= 3:
                return str(value).strip()
    except Exception:
        pass
    return ""


def extra_identity_queries(info):
    out = []
    product = exe_product_name(info.get("target", ""))
    if product and normalize_title(product) not in {"launcher", "game", "shipping", "win64 shipping", "unreal engine", "unity"}:
        out.append(product)

    target = info.get("target", "")
    if target:
        p = Path(target)
        stem = p.stem
        if len(stem) >= 4 and not re.search(r"(launcher|shipping|win64|win32|game|start|client)$", stem, flags=re.I):
            out.append(stem.replace("_", " ").replace("-", " "))
        if p.parent.name and len(p.parent.name) >= 4:
            out.append(p.parent.name)

    deduped = []
    seen = set()
    for q in out:
        n = normalize_title(q)
        if n and n not in seen:
            seen.add(n)
            deduped.append(q)
    return deduped


# ---------------------------- API / online sources ----------------------------

