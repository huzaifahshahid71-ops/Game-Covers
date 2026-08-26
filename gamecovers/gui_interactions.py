from .core import *
from .widgets import *


class GameCoversInteractionMixin:
    def validate_switches(self):
        if self.hide_shields_var.get() and not self.smart_launcher_var.get():
            self.smart_launcher_var.set(True)
            self.status_var.set("Smart launcher is required to hide the shield while preserving launch behavior.")

    def toggle_key(self):
        self.key_entry.configure(show="" if self.key_entry.cget("show") else "•")

    def pick_folder(self):
        p = filedialog.askdirectory(title="Select the folder containing your .lnk game shortcuts")
        if p:
            self.folder_var.set(p)
            self.refresh_shortcuts()

    def pick_cache(self):
        p = filedialog.askdirectory(title="Choose cache folder")
        if p:
            self.cache_var.set(p)

    def resolve_cache(self, folder):
        raw = self.cache_var.get().strip()
        if raw:
            return Path(os.path.expandvars(raw)).expanduser()
        return folder / ".game_cover_cache"

    def refresh_shortcuts(self):
        if self.running:
            return
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            self.items = []
            self.stats = {"total": 0, "found": 0, "skipped": 0, "failed": 0}
            self.shortcut_count_var.set("0 shortcuts found")
            self.render_cards()
            self.update_stats()
            return
        shortcuts = sorted(folder.glob("*.lnk"), key=lambda p: p.name.lower())
        self.items = [{"path": p, "name": clean_game_name(p.stem), "status": "ready", "detail": "", "preview": None} for p in shortcuts]
        self.stats = {"total": len(shortcuts), "found": 0, "skipped": 0, "failed": 0}
        self.shortcut_count_var.set(f"●  {len(shortcuts)} shortcuts found")
        self.folder_status.configure(text_color=GREEN if shortcuts else AMBER)
        self.status_var.set(f"Ready to process {len(shortcuts)} shortcuts." if shortcuts else "No .lnk shortcuts found in this folder.")
        self.progress.set(0)
        self.update_stats()
        self.render_cards()

    def filtered_items(self):
        filt = self.filter_var.get().lower()
        if filt == "all":
            return self.items
        return [x for x in self.items if x.get("status") == filt]

    def render_cards(self):
        for child in self.preview_scroll.winfo_children():
            child.destroy()
        self.cards = {}
        width = max(self.preview_scroll.winfo_width(), 850)
        cols = max(3, min(7, width // 185))
        for c in range(cols):
            self.preview_scroll.grid_columnconfigure(c, weight=1)
        visible = self.filtered_items()
        if not visible:
            ctk.CTkLabel(self.preview_scroll, text="No items in this view.", text_color=MUTED, font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=20, pady=40)
            return
        for idx, item in enumerate(visible):
            card = CoverCard(self.preview_scroll, item, self)
            card.grid(row=idx // cols, column=idx % cols, padx=6, pady=6, sticky="n")
            self.cards[str(item["path"])] = card

    def update_card(self, item, status=None, detail=None, image_bytes=None):
        if status:
            item["status"] = status
        if detail is not None:
            item["detail"] = detail
        if image_bytes:
            try:
                item["preview"] = make_preview_image(image_bytes)
            except Exception:
                pass
        card = self.cards.get(str(item["path"]))
        if card:
            if item.get("preview") is not None:
                card.set_cover_image(item["preview"])
            card.refresh_status()

    def update_stats(self):
        total = self.stats["total"]
        found = self.stats["found"]
        skipped = self.stats["skipped"]
        failed = self.stats["failed"]
        done = found + skipped + failed
        rate = round(found / total * 100) if total else 0
        self.stat_labels["total"].configure(text=str(total))
        self.stat_labels["found"].configure(text=str(found))
        self.stat_labels["skipped"].configure(text=str(skipped))
        self.stat_labels["failed"].configure(text=str(failed))
        self.stat_labels["rate"].configure(text=f"{rate}%")
        self.progress.set(done / total if total else 0)

    def log(self, text):
        self.logs.append(text)
        self.status_var.set(text if len(text) <= 120 else text[:117] + "…")

    def open_preferences(self):
        webbrowser.open(PREFERENCES_URL)

    def open_overrides(self):
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            messagebox.showerror("Folder required", "Select your shortcut folder first.")
            return
        cache = self.resolve_cache(folder)
        cache.mkdir(parents=True, exist_ok=True)
        _, path = load_overrides(cache)
        open_path(path)

    def show_logs(self):
        win = ctk.CTkToplevel(self)
        win.title("Game Covers — Logs")
        win.geometry("900x600")
        box = ctk.CTkTextbox(win, fg_color="#07111b", text_color="#e7eef8", font=("Consolas", 12))
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", "\n".join(self.logs) if self.logs else "No logs yet.")
        box.configure(state="disabled")

    def show_help(self):
        messagebox.showinfo("Game Covers — Help", "1. Choose the folder containing your .lnk game shortcuts.\n2. Paste a SteamGridDB API key.\n3. Keep Smart Launcher enabled if you want the UAC shield hidden.\n4. Click Find Covers & Apply Icons.\n\nAmbiguous games are skipped instead of guessed. Use Open Overrides for difficult titles such as '007'.")

    def show_about(self):
        messagebox.showinfo("About Game Covers", f"Game Covers v{APP_VERSION}\n\nTurns Windows game shortcuts into a clean cover-art library using Steam metadata, SteamGridDB, and official Steam portrait artwork.\n\nWindows 10/11 only.")

    def show_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Game Covers — Settings")
        win.geometry("520x360")
        win.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(win, text="Advanced Settings", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        ctk.CTkButton(win, text="Restore Windows shortcut arrows", command=self.restore_arrows_clicked, height=40).grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        ctk.CTkButton(win, text="Open cache folder", command=self.open_cache, height=40).grid(row=2, column=0, sticky="ew", padx=20, pady=8)
        ctk.CTkLabel(win, text="Tip: if Explorer keeps showing an older icon, restart Explorer or sign out/in to force the shell icon cache to refresh.", text_color=MUTED, wraplength=460, justify="left").grid(row=3, column=0, sticky="ew", padx=20, pady=14)

    def open_cache(self):
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            messagebox.showerror("Folder required", "Select your shortcut folder first.")
            return
        cache = self.resolve_cache(folder)
        cache.mkdir(parents=True, exist_ok=True)
        open_path(cache)

    def restore_arrows_clicked(self):
        try:
            restore_shortcut_arrows()
            messagebox.showinfo("Shortcut arrows", "The custom shortcut-arrow override was removed. Explorer may need a restart to redraw icons.")
        except Exception as e:
            messagebox.showerror("Could not restore arrows", str(e))
