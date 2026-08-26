from .core import *
from .widgets import *


class GameCoversWindowMixin:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=BG)
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1500x900")
        self.minsize(1180, 760)

        try:
            ico = resource_path("assets/game_covers.ico")
            if ico.exists():
                self.iconbitmap(str(ico))
        except Exception:
            pass

        self.folder_var = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.cache_var = tk.StringVar()
        self.hide_arrows_var = tk.BooleanVar(value=True)
        self.hide_shields_var = tk.BooleanVar(value=True)
        self.smart_launcher_var = tk.BooleanVar(value=True)
        self.keep_originals_var = tk.BooleanVar(value=True)
        self.filter_var = tk.StringVar(value="All")
        self.status_var = tk.StringVar(value="Select a shortcut folder to begin.")
        self.shortcut_count_var = tk.StringVar(value="0 shortcuts found")
        self.api_status_var = tk.StringVar(value="Not tested")

        self.items = []
        self.cards = {}
        self.logs = []
        self.running = False
        self.stats = {"total": 0, "found": 0, "skipped": 0, "failed": 0}

        self._build_window()

    # ---------- layout ----------
    def _build_window(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=330, fg_color="#091624", corner_radius=0, border_width=1, border_color="#10263b")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self._build_sidebar()

        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew", padx=(0, 0))
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(3, weight=1)
        self._build_main()

    def section_label(self, parent, text, row):
        label = ctk.CTkLabel(parent, text=text.upper(), text_color="#c8d7e7", font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        label.grid(row=row, column=0, sticky="ew", padx=18, pady=(14, 8))
        return label

    def _build_sidebar(self):
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        brand.grid_columnconfigure(1, weight=1)
        logo_img = placeholder_cover("GC", (42, 42)).resize((42, 42))
        self.sidebar_logo = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(42, 42))
        ctk.CTkLabel(brand, text="", image=self.sidebar_logo).grid(row=0, column=0, rowspan=2, padx=(0, 10))
        ctk.CTkLabel(brand, text="Game Covers", text_color=TEXT, font=ctk.CTkFont(size=20, weight="bold"), anchor="w").grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(brand, text=f"v{APP_VERSION}", text_color="#71aefb", font=ctk.CTkFont(size=11), anchor="w").grid(row=1, column=1, sticky="w")

        self.section_label(self.sidebar, "1. Select shortcut folder", 1)
        folder_box = ctk.CTkFrame(self.sidebar, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        folder_box.grid(row=2, column=0, sticky="ew", padx=16)
        folder_box.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(folder_box, textvariable=self.folder_var, height=40, fg_color="#081421", border_color="#1e3850").grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=(10, 6))
        ctk.CTkButton(folder_box, text="📁", width=42, height=40, command=self.pick_folder, fg_color="#102238", hover_color="#173350").grid(row=0, column=1, padx=(0, 10), pady=(10, 6))
        self.folder_status = ctk.CTkLabel(folder_box, textvariable=self.shortcut_count_var, text_color=MUTED, font=ctk.CTkFont(size=11), anchor="w")
        self.folder_status.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 9))

        self.section_label(self.sidebar, "2. SteamGridDB API key", 3)
        key_box = ctk.CTkFrame(self.sidebar, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        key_box.grid(row=4, column=0, sticky="ew", padx=16)
        key_box.grid_columnconfigure(0, weight=1)
        self.key_entry = ctk.CTkEntry(key_box, textvariable=self.api_key_var, show="•", height=40, fg_color="#081421", border_color="#1e3850")
        self.key_entry.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=(10, 6))
        ctk.CTkButton(key_box, text="◉", width=42, height=40, command=self.toggle_key, fg_color="#102238", hover_color="#173350").grid(row=0, column=1, padx=(0, 10), pady=(10, 6))
        self.api_status_label = ctk.CTkLabel(key_box, textvariable=self.api_status_var, text_color=MUTED, font=ctk.CTkFont(size=11), anchor="w")
        self.api_status_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 3))
        ctk.CTkButton(key_box, text="Open SteamGridDB Preferences ↗", command=self.open_preferences, height=34, fg_color="#11263b", hover_color="#193752").grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 10))

        self.section_label(self.sidebar, "3. Icon & launcher settings", 5)
        settings_box = ctk.CTkFrame(self.sidebar, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        settings_box.grid(row=6, column=0, sticky="ew", padx=16)
        self._switch_row(settings_box, 0, "Remove shortcut arrows", "Removes the small arrow overlay", self.hide_arrows_var)
        self._switch_row(settings_box, 1, "Hide UAC shield", "UAC is still enforced when required", self.hide_shields_var)
        self._switch_row(settings_box, 2, "Use smart launcher", "Preserves target, arguments and working dir", self.smart_launcher_var)

        self.section_label(self.sidebar, "4. Cache & advanced", 7)
        cache_box = ctk.CTkFrame(self.sidebar, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        cache_box.grid(row=8, column=0, sticky="ew", padx=16)
        cache_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cache_box, text="Cache location", text_color="#c9d8e8", font=ctk.CTkFont(size=11), anchor="w").grid(row=0, column=0, sticky="ew", padx=11, pady=(9, 3))
        ctk.CTkEntry(cache_box, textvariable=self.cache_var, height=34, placeholder_text="Shortcut folder\\.game_cover_cache", fg_color="#081421", border_color="#1e3850").grid(row=1, column=0, sticky="ew", padx=(10, 6), pady=(0, 6))
        ctk.CTkButton(cache_box, text="📁", width=40, height=34, command=self.pick_cache, fg_color="#102238", hover_color="#173350").grid(row=1, column=1, padx=(0, 10), pady=(0, 6))
        self._switch_row(cache_box, 2, "Keep original images", "Stores downloaded artwork in the cache", self.keep_originals_var, compact=True)
        ctk.CTkButton(cache_box, text="Open Overrides", command=self.open_overrides, height=32, fg_color="#11263b", hover_color="#193752").grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 10))

        self.sidebar.grid_rowconfigure(9, weight=1)
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.grid(row=10, column=0, sticky="sew", padx=14, pady=14)
        for i, (txt, cmd) in enumerate((("⚙\nSettings", self.show_settings), ("▤\nLogs", self.show_logs), ("?\nHelp", self.show_help), ("ⓘ\nAbout", self.show_about))):
            bottom.grid_columnconfigure(i, weight=1)
            ctk.CTkButton(bottom, text=txt, height=58, width=65, command=cmd, fg_color="#0e1d2d", hover_color="#17314a", font=ctk.CTkFont(size=11)).grid(row=0, column=i, padx=3, sticky="ew")

    def _switch_row(self, parent, row, title, subtitle, variable, compact=False):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=(6 if compact else 8, 3))
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, text_color=TEXT, font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(frame, text=subtitle, text_color=MUTED, font=ctk.CTkFont(size=10), anchor="w", wraplength=220).grid(row=1, column=0, sticky="ew", pady=(1, 0))
        ctk.CTkSwitch(frame, text="", variable=variable, width=43, command=self.validate_switches).grid(row=0, column=1, rowspan=2, padx=(8, 0))
