from .core import *
# ---------------------------- modern GUI ----------------------------

BG = "#07111d"
PANEL = "#0c1826"
PANEL_2 = "#101f30"
CARD = "#0d1a28"
BORDER = "#1d344b"
TEXT = "#f3f7ff"
MUTED = "#9cafc4"
BLUE = "#2f8cff"
PURPLE = "#8b3dff"
GREEN = "#1fd27a"
AMBER = "#ffbd3d"
RED = "#ff4c5d"


def resource_path(relative):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def open_path(path):
    try:
        os.startfile(str(path))
    except Exception:
        webbrowser.open(Path(path).resolve().as_uri())


def placeholder_cover(name, size=(180, 260)):
    w, h = size
    img = Image.new("RGB", size, "#101d2b")
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(11 + 18 * t)
        g = int(24 + 10 * t)
        b = int(39 + 30 * t)
        draw.line((0, y, w, y), fill=(r, g, b))
    draw.rounded_rectangle((10, 10, w - 10, h - 10), 18, outline="#254663", width=2)
    initials = "".join(p[0] for p in re.findall(r"[A-Za-z0-9]+", name)[:3]).upper() or "GC"
    try:
        font = ImageFont.truetype("segoeuib.ttf", 44)
        small = ImageFont.truetype("segoeui.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    box = draw.textbbox((0, 0), initials, font=font)
    draw.text(((w - (box[2] - box[0])) / 2, h * 0.39), initials, fill="#6fb4ff", font=font)
    short = name if len(name) <= 22 else name[:20] + "…"
    box2 = draw.textbbox((0, 0), short, font=small)
    draw.text(((w - (box2[2] - box2[0])) / 2, h * 0.66), short, fill="#b9c9da", font=small)
    return img


def make_preview_image(image_bytes, size=(156, 220)):
    with Image.open(BytesIO(image_bytes)) as im:
        im = im.convert("RGB")
        contained = ImageOps.contain(im, size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "#07111d")
    x = (size[0] - contained.width) // 2
    y = (size[1] - contained.height) // 2
    canvas.paste(contained, (x, y))
    return canvas


class CoverCard(ctk.CTkFrame):
    def __init__(self, master, item, app):
        super().__init__(master, fg_color=CARD, corner_radius=13, border_width=1, border_color=BORDER)
        self.app = app
        self.item = item
        self._cover_ref = None
        self.grid_columnconfigure(0, weight=1)

        image = item.get("preview") or placeholder_cover(item["name"], (156, 220))
        self.set_cover_image(image)
        self.image_label = ctk.CTkLabel(self, text="", image=self._cover_ref, corner_radius=9)
        self.image_label.grid(row=0, column=0, padx=8, pady=(8, 5))

        self.name_label = ctk.CTkLabel(
            self, text=item["name"], text_color=TEXT, font=ctk.CTkFont(size=12, weight="bold"),
            wraplength=158, justify="left", anchor="w"
        )
        self.name_label.grid(row=1, column=0, sticky="ew", padx=9, pady=(1, 0))

        self.status_label = ctk.CTkLabel(
            self, text="● Ready", text_color=MUTED, font=ctk.CTkFont(size=11), anchor="w"
        )
        self.status_label.grid(row=2, column=0, sticky="ew", padx=9, pady=(2, 8))
        self.refresh_status()

    def set_cover_image(self, pil_image):
        self._cover_ref = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(156, 220))
        if hasattr(self, "image_label"):
            self.image_label.configure(image=self._cover_ref)

    def refresh_status(self):
        status = self.item.get("status", "ready")
        detail = self.item.get("detail", "")
        mapping = {
            "ready": ("● Ready", MUTED),
            "working": ("● Searching…", BLUE),
            "found": ("● Found", GREEN),
            "skipped": ("● Skipped", AMBER),
            "failed": ("● Failed", RED),
        }
        text, color = mapping.get(status, ("● Ready", MUTED))
        if detail and status in ("skipped", "failed"):
            text += "  ⓘ"
        self.status_label.configure(text=text, text_color=color)
        if detail:
            self.status_label.bind("<Button-1>", lambda _e: messagebox.showinfo(self.item["name"], detail))
            self.status_label.configure(cursor="hand2")

