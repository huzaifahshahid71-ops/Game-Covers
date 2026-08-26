from gamecovers_services import *

# ---------------------------- GUI helpers ----------------------------

def placeholder_poster(name, size=(210, 300)):
    w, h = size
    img = Image.new("RGB", size, "#162132")
    draw = Image.new("RGBA", size)
    base = Image.new("RGB", size, "#162132")
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(base)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(18 + 20 * t)
        g = int(32 + 18 * t)
        b = int(50 + 30 * t)
        d.line((0, y, w, y), fill=(r, g, b))
    d.rounded_rectangle((12, 12, w - 12, h - 12), 18, outline="#5c7aa5", width=2)
    initials = "".join(p[0] for p in re.findall(r"[A-Za-z0-9]+", name)[:3]).upper() or "GC"
    try:
        font_big = ImageFont.truetype("segoeuib.ttf", 54)
        font_small = ImageFont.truetype("segoeui.ttf", 16)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    bb = d.textbbox((0, 0), initials, font=font_big)
    d.text(((w - (bb[2]-bb[0]))/2, h*0.34), initials, fill="#8fc2ff", font=font_big)
    short = name if len(name) <= 26 else name[:24] + "…"
    bb2 = d.textbbox((0, 0), short, font=font_small)
    d.text(((w - (bb2[2]-bb2[0]))/2, h*0.70), short, fill="#d7e6ff", font=font_small)
    return base


def make_preview_image(image_bytes, size=(210, 300)):
    with Image.open(BytesIO(image_bytes)) as im:
        im = im.convert("RGB")
        im.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, "#0f1723")
        x = (size[0] - im.width) // 2
        y = (size[1] - im.height) // 2
        canvas.paste(im, (x, y))
        return canvas


class CoverManagerDialog(tk.Toplevel):
    """Simple cover manager for every game, whether auto-matched or skipped."""
    def __init__(self, master, auto_open=False):
        super().__init__(master)
        self.app = master
        self.title("Manage Game Covers")
        self.geometry("900x500")
        self.configure(bg="#101826")
        self.transient(master)
        self.grab_set()

        ttk.Label(self, text="Manage Game Covers", style="Title.TLabel").pack(anchor="w", padx=18, pady=(16, 2))
        ttk.Label(
            self,
            text="Choose or replace the cover for any game — including games that already have an automatic cover. Manual choices are saved and reused on future runs.",
            style="Sub.TLabel",
            wraplength=850,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 12))

        frame = ttk.Frame(self, style="Card.TFrame", padding=12)
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        cols = ("game", "status", "source", "manual")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=13)
        self.tree.heading("game", text="Game")
        self.tree.heading("status", text="Status")
        self.tree.heading("source", text="Current source")
        self.tree.heading("manual", text="Custom cover")
        self.tree.column("game", width=250)
        self.tree.column("status", width=95, anchor="center")
        self.tree.column("source", width=230)
        self.tree.column("manual", width=260)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        self.refresh_rows()

        btns = ttk.Frame(self, style="Base.TFrame")
        btns.pack(fill="x", padx=16, pady=(0, 16))
        ttk.Button(btns, text="Choose Image…", command=self.choose_image).pack(side="left")
        ttk.Button(btns, text="Image URL…", command=self.choose_url).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Remove Custom Choice", command=self.remove_custom).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Open Overrides File", command=self.app.open_overrides).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")

        self.tree.bind("<Double-1>", lambda _e: self.choose_image())
        if auto_open and not self.tree.get_children():
            self.after(50, self.destroy)

    def refresh_rows(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self.app.items:
            manual = item.get("manual_source", "")
            if not manual and item["name"] in self.app.overrides:
                override = self.app.overrides.get(item["name"], {})
                manual = override.get("image") or ("URL override" if override.get("url") else "")
            self.tree.insert(
                "", "end", iid=str(item["path"]),
                values=(item["name"], item.get("status", "Ready"), item.get("source", ""), manual),
            )

    def selected_item(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Manage Game Covers", "Select a game first.", parent=self)
            return None
        iid = sel[0]
        for item in self.app.items:
            if str(item["path"]) == iid:
                return item
        return None

    def choose_image(self):
        item = self.selected_item()
        if not item:
            return
        path = filedialog.askopenfilename(
            parent=self,
            title=f"Choose a cover image for {item['name']}",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All files", "*.*")],
        )
        if not path:
            return
        self.apply_manual(item, image_path=Path(path))

    def choose_url(self):
        item = self.selected_item()
        if not item:
            return
        url = simpledialog.askstring("Image URL", f"Paste an image URL for {item['name']}", parent=self)
        if not url:
            return
        self.apply_manual(item, url=url.strip())

    def apply_manual(self, item, image_path=None, url=None):
        try:
            self.app.assign_manual_cover(item, image_path=image_path, url=url)
            self.refresh_rows()
            if self.tree.exists(str(item["path"])):
                self.tree.selection_set(str(item["path"]))
                self.tree.see(str(item["path"]))
        except Exception as e:
            messagebox.showerror("Could not apply cover", str(e), parent=self)

    def remove_custom(self):
        item = self.selected_item()
        if not item:
            return
        if item["name"] not in self.app.overrides:
            messagebox.showinfo("Manage Game Covers", "This game does not currently have a saved custom cover.", parent=self)
            return
        if not messagebox.askyesno(
            "Remove custom cover",
            f"Remove the saved custom cover for {item['name']}?\n\nThe current icon will stay until you run Find Covers & Apply Icons again.",
            parent=self,
        ):
            return
        self.app.remove_manual_override(item)
        self.refresh_rows()


