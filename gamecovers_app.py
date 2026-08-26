from gamecovers_app_ui import *

class App(AppUI):
    def start(self):
        folder = Path(self.folder.get().strip())
        key = self.api_key.get().strip()
        if not folder.is_dir():
            messagebox.showerror("Folder required", "Select the folder containing your game shortcuts.")
            return
        if not key:
            messagebox.showerror("API key required", "Open SteamGridDB Preferences, generate your API key, then paste it here.")
            return
        shortcuts = sorted(folder.glob("*.lnk"))
        if not shortcuts:
            messagebox.showinfo("No shortcuts", "No .lnk files were found in that folder.")
            return
        self.refresh_shortcuts()
        self.running = True
        self.run.configure(state="disabled")
        self.progress.configure(value=0)
        self.log.delete("1.0", "end")
        self.status.set("Working…")
        threading.Thread(target=self.process, args=(folder, key, shortcuts), daemon=True).start()

    def process(self, folder, key, shortcuts):
        cache = folder / ".game_cover_cache"
        cache.mkdir(exist_ok=True)
        self.last_cache = cache
        backup_dir = cache / "original_shortcuts_v4"
        overrides, override_path = load_overrides(cache)
        self.overrides = overrides
        total = len(shortcuts)
        used_game_ids = {}

        self.write_log(f"Found {total} shortcuts.")
        self.write_log(f"Overrides: {override_path}")
        self.write_log("Matching order: shortcut Steam AppID → Steam Store corroboration → strict SteamGridDB title match.")
        self.write_log("")

        for i, shortcut in enumerate(shortcuts, 1):
            item = self.find_item(str(shortcut))
            try:
                backup_shortcut(shortcut, backup_dir)
                raw = shortcut_info(shortcut)
                info, recovery_note = recover_v3_wrapper(raw)
                name = info["name"]
                self.after(0, lambda it=item: self.set_item_status(it, status="Working", detail="Searching for a cover…"))
                self.write_log(f"[{i}/{total}] {name}")
                if recovery_note:
                    self.write_log(f"    ⚠ {recovery_note}")

                override = overrides.get(name)
                resolved_override = resolve_override(key, override, name) if override else None

                image_bytes = None
                source_desc = ""
                width = height = 0
                game = None
                steam_appid = None
                reason = ""

                if resolved_override and resolved_override.get("bytes"):
                    image_bytes = resolved_override["bytes"]
                    source_desc = resolved_override["source"]
                    width, height = resolved_override["width"], resolved_override["height"]
                    reason = "Manual artwork override"
                else:
                    search_name = name
                    if resolved_override and resolved_override.get("search"):
                        search_name = resolved_override["search"]
                    if resolved_override and resolved_override.get("game"):
                        game = resolved_override.get("game")
                        steam_appid = resolved_override.get("steam_appid")
                        reason = resolved_override.get("reason", "Override")
                        aliases = title_aliases(search_name)
                    else:
                        game, reason, score, steam_appid, aliases = choose_sgdb_game(key, search_name, info, used_game_ids)

                    if not game:
                        raise RuntimeError(reason or "Game could not be identified confidently")

                    gid = int(game.get("id"))
                    if gid in used_game_ids and normalize_title(used_game_ids[gid]) != normalize_title(name):
                        raise RuntimeError(f"Match collision with '{used_game_ids[gid]}'. Add an override instead of guessing.")

                    art_candidates = []
                    art = choose_artwork(get_grids(key, gid))
                    if art and art.get("url"):
                        try:
                            b = download(art["url"])
                            w, h = validate_image(b)
                            art_candidates.append({"bytes": b, "width": w, "height": h, "source": "SteamGridDB", "desc": f"SteamGridDB {w}×{h}"})
                        except Exception as e:
                            self.write_log(f"      SGDB art rejected: {e}")

                    if not steam_appid:
                        steam_item, steam_score, steam_margin = best_steam_store_match(aliases)
                        if steam_item and steam_score >= 90 and steam_margin >= 4:
                            steam_appid = int(steam_item["id"])
                    official = fetch_steam_official_cover(steam_appid)
                    if official:
                        art_candidates.append({"bytes": official["bytes"], "width": official["width"], "height": official["height"], "source": "Steam official", "desc": f"Steam official {official['width']}×{official['height']}"})

                    if not art_candidates:
                        raise RuntimeError("No usable portrait art found in SteamGridDB or Steam's official library assets")

                    chosen = max(art_candidates, key=lambda c: image_candidate_score(c["width"], c["height"], c["source"]))
                    image_bytes = chosen["bytes"]
                    width, height = chosen["width"], chosen["height"]
                    source_desc = chosen["desc"]
                    used_game_ids[gid] = name

                _, ico = cache_artwork(cache, name, image_bytes, source_desc)
                if self.hide_shields.get():
                    if not info.get("target"):
                        apply_icon_only(shortcut, ico)
                        self.write_log("    ⚠ Target could not be resolved, so only the icon was changed.")
                    else:
                        launcher = create_vbs_launcher(cache, name, info)
                        apply_icon_via_launcher(shortcut, ico, launcher, info)
                else:
                    apply_icon_only(shortcut, ico)

                matched_name = game.get("name") if game else name
                detail = f"{matched_name} | {width}×{height} | {reason or 'Matched'}"
                self.after(0, lambda it=item, d=detail, s=source_desc, b=image_bytes: (self.set_item_status(it, status="Found", source=s, detail=d, image_bytes=b), self.update_stats()))
                self.write_log(f"    ✓ {matched_name} | {width}×{height} | {source_desc}")

            except Exception as e:
                msg = str(e)
                self.after(0, lambda it=item, d=msg: (self.set_item_status(it, status="Skipped", source="", detail=d), self.update_stats()))
                self.write_log(f"    ⚠ SKIPPED: {msg}")
                self.write_log("      Tip: use Manage / Replace Covers to choose your own image for this game.")

        if self.hide_arrows.get():
            try:
                remove_shortcut_arrows(cache)
                self.write_log("")
                self.write_log("✓ Shortcut-arrow overlay override applied globally for this Windows account.")
            except Exception as e:
                self.write_log(f"⚠ Could not remove shortcut arrows: {e}")

        refresh_explorer()
        self.after(0, self.finish_processing)

    def finish_processing(self):
        self.running = False
        self.run.configure(state="normal")
        self.update_stats()
        found = sum(1 for x in self.items if x.get("status") == "Found")
        skipped = sum(1 for x in self.items if x.get("status") == "Skipped")
        self.status.set(f"Finished — {found} updated, {skipped} skipped.")
        self.write_log("")
        self.write_log("Finished. Explorer → View → Extra large icons gives the cleanest cover layout.")
        if skipped:
            if messagebox.askyesno("Choose custom covers", f"{skipped} games were skipped. Open the cover manager now? You can also replace covers for games that were found automatically."):
                self.open_cover_manager(auto_prompt=True)

    def assign_manual_cover(self, item, image_path=None, url=None):
        folder = Path(self.folder.get().strip())
        key = self.api_key.get().strip()
        if not folder.is_dir():
            raise RuntimeError("Shortcut folder is no longer available.")
        cache = self.last_cache or (folder / ".game_cover_cache")
        cache.mkdir(exist_ok=True)
        backup_dir = cache / "original_shortcuts_v4"
        backup_shortcut(item["path"], backup_dir)
        raw = shortcut_info(item["path"])
        info, _ = recover_v3_wrapper(raw)

        if image_path is not None:
            source_path = Path(image_path)
            b = source_path.read_bytes()
            w, h = validate_image(b, portrait_required=False)
            if h <= w and not messagebox.askyesno("Non-portrait image", f"This image is {w}×{h} and is not portrait. Use it anyway?"):
                return
            # Keep a durable copy in the cache so a future run still works even if
            # the user's original Downloads/Desktop image is moved or deleted.
            manual_dir = cache / "manual_covers"
            manual_dir.mkdir(exist_ok=True)
            suffix = source_path.suffix.lower() if source_path.suffix else ".png"
            digest = hashlib.sha1(b).hexdigest()[:10]
            saved = manual_dir / f"{safe_file_part(item['name'])}__{digest}{suffix}"
            if not saved.exists():
                saved.write_bytes(b)
            override = {"image": str(saved.resolve())}
            source_desc = f"Manual image {w}×{h}"
        elif url:
            b = download(url)
            w, h = validate_image(b, portrait_required=False)
            if h <= w and not messagebox.askyesno("Non-portrait image", f"This image is {w}×{h} and is not portrait. Use it anyway?"):
                return
            override = {"url": url}
            source_desc = f"Manual URL {w}×{h}"
        else:
            raise RuntimeError("No manual image source was provided.")

        self.overrides[item["name"]] = override
        save_overrides(cache, self.overrides)
        _, ico = cache_artwork(cache, item["name"], b, source_desc)

        if self.hide_shields.get():
            if not info.get("target"):
                apply_icon_only(item["path"], ico)
            else:
                launcher = create_vbs_launcher(cache, item["name"], info)
                apply_icon_via_launcher(item["path"], ico, launcher, info)
        else:
            apply_icon_only(item["path"], ico)

        self.set_item_status(item, status="Found", source="Manual", detail="Manual cover applied", image_bytes=b)
        item["manual_source"] = override.get("image") or "URL override"
        self.update_stats()
        refresh_explorer()
        self.write_log(f"    ✓ Manual cover applied for {item['name']}")


    def remove_manual_override(self, item):
        if item["name"] in self.overrides:
            del self.overrides[item["name"]]
        folder = Path(self.folder.get().strip())
        if folder.is_dir():
            cache = self.last_cache or (folder / ".game_cover_cache")
            cache.mkdir(exist_ok=True)
            save_overrides(cache, self.overrides)
        item["manual_source"] = ""
        self.write_log(f"    • Custom cover choice removed for {item['name']}; run the automatic scan again to restore an automatic cover.")



