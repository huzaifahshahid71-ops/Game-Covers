from .core import *
from .widgets import *


class GameCoversMainLayoutMixin:
    def _build_main(self):
        hero = ctk.CTkFrame(self.main, fg_color="#0a1727", corner_radius=16, border_width=1, border_color="#17334d")
        hero.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 10))
        hero.grid_columnconfigure(0, weight=1)
        hero.grid_columnconfigure(1, weight=0)

        title_box = ctk.CTkFrame(hero, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="nsew", padx=28, pady=22)
        ctk.CTkLabel(title_box, text="Game Covers", text_color="#61b5ff", font=ctk.CTkFont(size=34, weight="bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(title_box, text="Beautiful Game Covers. Clean Shortcuts.", text_color="#c8d6e6", font=ctk.CTkFont(size=17), anchor="w").pack(anchor="w", pady=(4, 18))
        feature_row = ctk.CTkFrame(title_box, fg_color="transparent")
        feature_row.pack(fill="x")
        for i, (icon, head, sub) in enumerate((("◇", "High Quality", "Up to 2160×3840"), ("◉", "Smart Matching", "Steam + metadata + SGDB"), ("✦", "Clean & Beautiful", "No arrows. No shields."))):
            box = ctk.CTkFrame(feature_row, fg_color="#0d1d2e", corner_radius=10, border_width=1, border_color="#18354e")
            box.pack(side="left", padx=(0 if i == 0 else 8, 0), fill="x", expand=True)
            ctk.CTkLabel(box, text=f"{icon}  {head}", text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(anchor="w", padx=12, pady=(9, 0))
            ctk.CTkLabel(box, text=sub, text_color=MUTED, font=ctk.CTkFont(size=10), anchor="w").pack(anchor="w", padx=12, pady=(1, 9))

        art_panel = ctk.CTkFrame(hero, fg_color="#101629", width=310, height=180, corner_radius=14)
        art_panel.grid(row=0, column=1, sticky="nse", padx=(8, 18), pady=14)
        art_panel.grid_propagate(False)
        ctk.CTkLabel(art_panel, text="🎮", font=ctk.CTkFont(size=64), text_color="#8e63ff").place(relx=.5, rely=.42, anchor="center")
        ctk.CTkLabel(art_panel, text="Turn shortcuts into a cover library", font=ctk.CTkFont(size=11, weight="bold"), text_color="#d7e2ef").place(relx=.5, rely=.78, anchor="center")

        stats = ctk.CTkFrame(self.main, fg_color="transparent")
        stats.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        for i in range(5):
            stats.grid_columnconfigure(i, weight=1)
        self.stat_labels = {}
        stat_defs = [("total", "🎮", "Total Shortcuts", BLUE), ("found", "✓", "Covers Found", GREEN), ("skipped", "!", "Skipped", AMBER), ("failed", "×", "Failed", RED), ("rate", "◔", "Success Rate", BLUE)]
        for i, (key, icon, label, color) in enumerate(stat_defs):
            box = ctk.CTkFrame(stats, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0))
            ctk.CTkLabel(box, text=icon, text_color=color, font=ctk.CTkFont(size=25, weight="bold"), width=40).grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=9)
            value = ctk.CTkLabel(box, text="0" if key != "rate" else "0%", text_color=TEXT, font=ctk.CTkFont(size=22, weight="bold"), anchor="w")
            value.grid(row=0, column=1, sticky="sw", padx=(0, 8), pady=(8, 0))
            ctk.CTkLabel(box, text=label, text_color=MUTED, font=ctk.CTkFont(size=10), anchor="w").grid(row=1, column=1, sticky="nw", padx=(0, 8), pady=(0, 8))
            box.grid_columnconfigure(1, weight=1)
            self.stat_labels[key] = value

        result_panel = ctk.CTkFrame(self.main, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
        result_panel.grid(row=2, column=0, rowspan=2, sticky="nsew", padx=16, pady=(0, 10))
        result_panel.grid_columnconfigure(0, weight=1)
        result_panel.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(result_panel, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=9)
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(toolbar, text="🎮  PREVIEW & RESULTS", text_color="#c7d6e7", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(toolbar, text="↻  Refresh List", width=120, height=34, command=self.refresh_shortcuts, fg_color="#11253a", hover_color="#1a3855").grid(row=0, column=1, padx=5)
        self.filter_menu = ctk.CTkOptionMenu(toolbar, variable=self.filter_var, values=["All", "Found", "Skipped", "Failed", "Ready"], command=lambda _v: self.render_cards(), width=112, height=34, fg_color="#11253a", button_color="#17416a")
        self.filter_menu.grid(row=0, column=2, padx=5)
        ctk.CTkButton(toolbar, text="▦", width=40, height=34, command=lambda: self.render_cards(), fg_color="#164c8c", hover_color="#1f65b4").grid(row=0, column=3, padx=(5, 2))

        self.preview_scroll = ctk.CTkScrollableFrame(result_panel, fg_color="#091522", corner_radius=9)
        self.preview_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        footer = ctk.CTkFrame(self.main, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
        footer.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 14))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, textvariable=self.status_var, text_color="#c1d0e0", font=ctk.CTkFont(size=11), anchor="w").grid(row=0, column=0, sticky="ew", padx=14, pady=(9, 2))
        self.progress = ctk.CTkProgressBar(footer, height=10, progress_color=BLUE, fg_color="#122236")
        self.progress.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.progress.set(0)
        self.run_button = ctk.CTkButton(footer, text="🚀  Find Covers & Apply Icons", width=360, height=52, command=self.start, font=ctk.CTkFont(size=16, weight="bold"), fg_color=PURPLE, hover_color="#6d30cf", border_width=1, border_color="#8ea8ff")
        self.run_button.grid(row=0, column=1, rowspan=2, padx=12, pady=10)
