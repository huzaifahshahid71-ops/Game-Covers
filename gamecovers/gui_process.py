from .core import *
from .widgets import *


class GameCoversProcessMixin:
    # ---------- processing ----------
    def start(self):
        if self.running:
            return
        folder = Path(self.folder_var.get().strip())
        key = self.api_key_var.get().strip()
        if not folder.is_dir():
            messagebox.showerror("Folder required", "Select the folder containing your .lnk game shortcuts.")
            return
        if not key:
            messagebox.showerror("API key required", "Open SteamGridDB Preferences, generate your API key, then paste it here.")
            return
        if not self.items:
            self.refresh_shortcuts()
        if not self.items:
            messagebox.showinfo("No shortcuts", "No .lnk files were found in that folder.")
            return

        self.validate_switches()
        self.running = True
        self.run_button.configure(state="disabled", text="Working…")
        self.logs = []
        self.stats.update(found=0, skipped=0, failed=0)
        for item in self.items:
            item.update(status="ready", detail="", preview=None)
        self.update_stats()
        self.render_cards()
        threading.Thread(target=self.process, args=(folder, key), daemon=True).start()

    def validate_api_key(self, key):
        api_get(key, "/search/autocomplete/Portal")
        self.after(0, lambda: (self.api_status_var.set("● Connected"), self._set_api_status_color(GREEN)))

    def _set_api_status_color(self, color):
        try:
            self.api_status_label.configure(text_color=color)
        except Exception:
            pass

    def process(self, folder, key):
        cache = self.resolve_cache(folder)
        try:
            cache.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.after(0, lambda: self.finish_with_error(f"Could not create cache folder: {e}"))
            return

        try:
            self.validate_api_key(key)
        except Exception as e:
            self.after(0, lambda err=str(e): (self.api_status_var.set("● Connection failed"), self._set_api_status_color(RED), self.finish_with_error(err)))
            return

        backup_dir = cache / "original_shortcuts"
        overrides, override_path = load_overrides(cache)
        used_game_ids = {}
        self.log(f"Found {len(self.items)} shortcuts. Cache: {cache}")
        self.log(f"Overrides: {override_path}")
        self.log("Identity order: shortcut Steam AppID → Steam Store corroboration → strict SteamGridDB title match.")

        for idx, item in enumerate(self.items, 1):
            shortcut = item["path"]
            stage = "matching"
            self.after(0, lambda it=item: self.update_card(it, status="working", detail=""))
            self.log(f"[{idx}/{len(self.items)}] {item['name']}")
            try:
                backup_shortcut(shortcut, backup_dir)

                raw = shortcut_info(shortcut)
                info, recovery_note = recover_v3_wrapper(raw)
                name = info["name"]
                if recovery_note:
                    self.log(f"  WARNING: {recovery_note}")

                override = overrides.get(name)
                resolved_override = resolve_override(key, override, name) if override else None
                image_bytes = None
                source_desc = ""
                width = height = 0
                game = None
                steam_appid = None
                reason = ""
                gid = None

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

                    stage = "artwork"
                    art_candidates = []
                    art = choose_artwork(get_grids(key, gid))
                    if art and art.get("url"):
                        try:
                            b = download(art["url"])
                            w, h = validate_image(b)
                            art_candidates.append({"bytes": b, "width": w, "height": h, "source": "SteamGridDB", "desc": f"SteamGridDB {w}×{h}"})
                        except Exception as e:
                            self.log(f"  SGDB art rejected: {e}")

                    if not steam_appid:
                        steam_item, steam_score, steam_margin = best_steam_store_match(aliases)
                        if steam_item and steam_score >= 90 and steam_margin >= 4:
                            steam_appid = int(steam_item["id"])
                    official = fetch_steam_official_cover(steam_appid)
                    if official:
                        art_candidates.append({"bytes": official["bytes"], "width": official["width"], "height": official["height"], "source": "Steam official", "desc": f"Steam official {official['width']}×{official['height']}"})

                    if not art_candidates:
                        raise RuntimeError("No usable portrait cover found on SteamGridDB or Steam's official library assets")

                    chosen = max(art_candidates, key=lambda c: image_candidate_score(c["width"], c["height"], c["source"]))
                    image_bytes = chosen["bytes"]
                    width, height = chosen["width"], chosen["height"]
                    source_desc = chosen["desc"]
                    used_game_ids[gid] = name

                stage = "icon"
                _, ico = cache_artwork(cache, name, image_bytes, source_desc, keep_original=self.keep_originals_var.get())

                stage = "apply"
                if self.hide_shields_var.get() and self.smart_launcher_var.get():
                    if not info.get("target"):
                        apply_icon_only(shortcut, ico)
                        self.log("  Target unresolved; applied icon only.")
                    else:
                        launcher = create_vbs_launcher(cache, name, info)
                        apply_icon_via_launcher(shortcut, ico, launcher, info)
                else:
                    apply_icon_only(shortcut, ico)

                matched_name = game.get("name") if game else name
                detail = f"{matched_name}\n{width}×{height}\n{source_desc}\nIdentity: {reason or 'manual artwork'}"
                self.stats["found"] += 1
                self.after(0, lambda it=item, d=detail, b=image_bytes: (self.update_card(it, status="found", detail=d, image_bytes=b), self.update_stats()))
                self.log(f"  FOUND: {matched_name} | {width}×{height} | {source_desc}")

            except Exception as e:
                text = str(e)
                expected_skip = stage in ("matching", "artwork") and not any(x in text.lower() for x in ("unauthorized", "connection", "timed out"))
                status = "skipped" if expected_skip else "failed"
                self.stats[status] += 1
                self.after(0, lambda it=item, st=status, d=text: (self.update_card(it, status=st, detail=d), self.update_stats()))
                self.log(f"  {status.upper()}: {text}")

        if self.hide_arrows_var.get():
            try:
                remove_shortcut_arrows(cache)
                self.log("Shortcut arrow overlay override applied for this Windows user account.")
            except Exception as e:
                self.log(f"Could not remove shortcut arrows: {e}")

        refresh_explorer()
        self.after(0, self.finish_success)

    def finish_success(self):
        self.running = False
        self.run_button.configure(state="normal", text="🚀  Find Covers & Apply Icons")
        self.update_stats()
        self.status_var.set(f"Finished — {self.stats['found']} covers applied, {self.stats['skipped']} skipped, {self.stats['failed']} failed. Set Explorer to Extra large icons.")

    def finish_with_error(self, text):
        self.running = False
        self.run_button.configure(state="normal", text="🚀  Find Covers & Apply Icons")
        self.status_var.set(text)
        messagebox.showerror("Game Covers", text)
