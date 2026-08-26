import ctypes
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import threading
import unicodedata
import webbrowser
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageOps
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
APP_VERSION = "1.0.0"
BASE_URL = "https://www.steamgriddb.com/api/v2"
PREFERENCES_URL = "https://www.steamgriddb.com/profile/preferences"
STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
RUNAS_LINK_FLAG = 0x00002000

session = requests.Session()
session.headers.update({
    "User-Agent": "GameCovers/1.0",
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
    # Make common punctuation differences irrelevant (BeamNG.drive, RE:Verse, etc.).
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_aliases(name):
    """Produce conservative alternate titles without silently changing game identity."""
    out = []

    def add(v):
        v = clean_game_name(v)
        if v and v not in out:
            out.append(v)

    add(name)
    add(re.sub(r"\s*[-–—:]\s*", " ", name))

    # Common naming pattern: "Series 8 - Subtitle" while the official title is
    # often simply "Series Subtitle" (e.g. Resident Evil 8 - Village).
    m = re.match(r"^(.*?\D)\s+(\d+)\s*[-–—:]\s*(.+)$", name)
    if m:
        add(f"{m.group(1)} {m.group(3)}")
        add(f"{m.group(1)} {m.group(2)} {m.group(3)}")

    # Mild typo aliases that are common in hand-renamed shortcuts.
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

    # A few canonical franchise aliases that are otherwise needlessly ambiguous.
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
    # Wrong sequel numbers are a very strong negative signal. Missing numbers are
    # less severe because official titles sometimes omit the informal sequel number.
    if nums_a and nums_b and nums_a != nums_b:
        score -= 35.0
    elif nums_a and not nums_b:
        score -= 7.0
    return score


def best_alias_score(aliases, candidate):
    return max((similarity(a, candidate) for a in aliases), default=0.0)

