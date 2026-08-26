from gamecovers_app_shell import *

class AppUI(AppShell):
    def toggle_key(self):
        self.key_entry.configure(show="" if self.key_entry.cget("show") else "•")

    def pick_folder(self):
        p = filedialog.askdirectory(title="Select the folder containing your .lnk game shortcuts")
        if p:
            self.folder.set(p)
            self.refresh_shortcuts()

    def open_preferences(self):
        webbrowser.open(PREFERENCES_URL)

    def refresh_shortcuts(self):
        folder = Path(self.folder.get().strip())
        self.items = []
        self.tree.delete(*self.tree.get_children())
        self.preview_placeholder(None)
        if not folder.is_dir():
            self.total_var.set("0")
            self.found_var.set("0")
            self.skipped_var.set("0")
            self.progress_var.set("0%")
            return
        shortcuts = sorted(folder.glob("*.lnk"), key=lambda p: p.name.lower())
        for p in shortcuts:
            item = {
                "path": p,
                "name": clean_game_name(p.stem),
                "status": "Ready",
                "source": "",
                "detail": "",
                "preview_image": None,
                "preview_bytes": None,
                "manual_source": "",
            }
            self.items.append(item)
            self.tree.insert("", "end", iid=str(p), values=(item["name"], item["status"], "", ""))
        self.total_var.set(str(len(shortcuts)))
        self.found_var.set("0")
        self.skipped_var.set("0")
        self.progress_var.set("0%")
        self.status.set(f"Ready to process {len(shortcuts)} shortcuts." if shortcuts else "No .lnk shortcuts found in this folder.")

    def find_item(self, iid):
        for item in self.items:
            if str(item["path"]) == iid:
                return item
        return None

    def on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.find_item(sel[0])
        if not item:
            return
        self.preview_placeholder(item)

    def choose_selected_cover(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Choose cover", "Select a game in the Results list first.")
            return
        item = self.find_item(sel[0])
        if not item:
            return
        path = filedialog.askopenfilename(
            parent=self,
            title=f"Choose a cover image for {item['name']}",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All files", "*.*")],
        )
        if path:
            try:
                self.assign_manual_cover(item, image_path=Path(path))
            except Exception as e:
                messagebox.showerror("Could not apply cover", str(e))

    def preview_placeholder(self, item):
        if item and item.get("preview_image") is not None:
            img = item["preview_image"].copy()
        else:
            name = item["name"] if item else "Game Covers"
            img = placeholder_poster(name)
        self.preview_ref = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self.preview_ref, text="")
        info = []
        if item:
            info.append(f"Game: {item['name']}")
            info.append(f"Status: {item.get('status', '')}")
            if item.get("source"):
                info.append(f"Source: {item['source']}")
            if item.get("detail"):
                info.append(f"Notes: {item['detail']}")
        else:
            info.append("Select a game to preview its current cover and status.")
        self.preview_info.configure(state="normal")
        self.preview_info.delete("1.0", "end")
        self.preview_info.insert("1.0", "\n".join(info))
        self.preview_info.configure(state="disabled")

    def set_item_status(self, item, status=None, source=None, detail=None, image_bytes=None):
        if status is not None:
            item["status"] = status
        if source is not None:
            item["source"] = source
        if detail is not None:
            item["detail"] = detail
        if image_bytes is not None:
            item["preview_bytes"] = image_bytes
            try:
                item["preview_image"] = make_preview_image(image_bytes)
            except Exception:
                pass
        iid = str(item["path"])
        if self.tree.exists(iid):
            self.tree.item(iid, values=(item["name"], item["status"], item.get("source", ""), item.get("detail", "")))
        if self.tree.selection() and self.tree.selection()[0] == iid:
            self.preview_placeholder(item)

    def update_stats(self):
        total = len(self.items)
        found = sum(1 for x in self.items if x.get("status") == "Found")
        skipped = sum(1 for x in self.items if x.get("status") == "Skipped")
        done = found + skipped
        self.total_var.set(str(total))
        self.found_var.set(str(found))
        self.skipped_var.set(str(skipped))
        self.progress_var.set(f"{round(done / total * 100) if total else 0}%")
        self.progress.configure(value=(done / total * 100) if total else 0)

    def write_log(self, text):
        self.logs.append(text)
        self.after(0, self._write_log, text)

    def _write_log(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.status.set(text if len(text) <= 120 else text[:117] + "…")

    def open_overrides(self):
        folder = Path(self.folder.get().strip())
        if not folder.is_dir():
            messagebox.showerror("Folder required", "Select your shortcut folder first.")
            return
        cache = folder / ".game_cover_cache"
        cache.mkdir(exist_ok=True)
        _, path = load_overrides(cache)
        try:
            os.startfile(path)
        except Exception:
            webbrowser.open(path.as_uri())

    def open_cover_manager(self, auto_prompt=False):
        if not self.items:
            if not auto_prompt:
                messagebox.showinfo("Manage Game Covers", "Choose a shortcut folder first.")
            return
        CoverManagerDialog(self, auto_open=auto_prompt)

    # Backward-compatible name used by the skipped-game prompt.
    def open_missing_dialog(self, auto_prompt=False):
        self.open_cover_manager(auto_prompt=auto_prompt)

    def restore_arrows_clicked(self):
        try:
            restore_shortcut_arrows()
            messagebox.showinfo("Shortcut arrows", "The custom arrow override was removed. Explorer may need a restart to redraw icons.")
        except Exception as e:
            messagebox.showerror("Could not restore arrows", str(e))

