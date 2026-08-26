from .common import *

# ---------------------------- shortcut preservation ----------------------------

def read_runas_flag(path):
    """Read the Shell Link RunAsUser bit without changing the shortcut."""
    try:
        data = Path(path).read_bytes()
        if len(data) < 0x18:
            return False
        flags = struct.unpack_from("<I", data, 0x14)[0]
        return bool(flags & RUNAS_LINK_FLAG)
    except Exception:
        return False


def clear_runas_flag(path):
    """Clear RunAsUser only on the wrapper link; the launcher preserves elevation."""
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
    """Recover what v3 stored. v3 unfortunately did not preserve original arguments."""
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
            new["arguments"] = ""  # v3 did not store them, so they cannot be recovered here.
            new["working_directory"] = recovered_cwd or str(Path(recovered_target).parent)
            new["run_as_admin"] = False  # v3 also did not preserve this reliably.
            return new, "Detected an old v3 WScript wrapper; target was recovered, but any original arguments/run-as flag were already lost by v3."
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
    """Create a launcher that preserves target, args, cwd and elevation semantics."""
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

    # ShellExecute preserves manifest-based elevation. If the old .lnk itself had
    # RunAsUser set, we explicitly use the runas verb so that UAC behavior remains.
    script = (
        'On Error Resume Next\n'
        'Set sh = CreateObject("Shell.Application")\n'
        f'sh.ShellExecute {vbs_string(target)}, {vbs_string(args)}, {vbs_string(working)}, {vbs_string(verb)}, 1\n'
        'If Err.Number <> 0 Then\n'
        '  MsgBox "Unable to launch the game: " & Err.Description, 16, "Game Covers"\n'
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
    # If the original shortcut had RunAsUser set, WScript COM may preserve the flag.
    # Clear it on the wrapper itself; the VBS uses the runas verb instead.
    clear_runas_flag(shortcut)


def extract_steam_appid(info):
    text = " ".join([info.get("target", ""), info.get("arguments", "")])
    patterns = [
        r"steam://rungameid/(\d+)",
        r"steam://run/(\d+)",
        r"(?:^|\s)-applaunch\s+(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return int(m.group(1))

    # Some games ship steam_appid.txt next to the executable (or one/two folders
    # above it). This gives us an exact identity even when the shortcut launches
    # the EXE directly instead of going through steam.exe.
    target = info.get("target") or ""
    try:
        tp = Path(target)
        if tp.suffix.lower() == ".exe":
            folders = [tp.parent]
            folders.extend(list(tp.parents)[1:4])
            seen = set()
            for folder in folders:
                if str(folder).lower() in seen:
                    continue
                seen.add(str(folder).lower())
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
    if product and normalize_title(product) not in {
        "launcher", "game", "shipping", "win64 shipping", "unreal engine", "unity"
    }:
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

