from .core import *
from .gui_window import GameCoversWindowMixin
from .gui_mainlayout import GameCoversMainLayoutMixin
from .gui_interactions import GameCoversInteractionMixin
from .gui_process import GameCoversProcessMixin


class GameCoversApp(GameCoversWindowMixin, GameCoversMainLayoutMixin, GameCoversInteractionMixin, GameCoversProcessMixin, ctk.CTk):
    pass
