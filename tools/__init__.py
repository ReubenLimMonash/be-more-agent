# =========================================================================
#  BMO Agent Tools Registry
#  Central place to import and manage all tools
# =========================================================================

from .games import launch_game, list_games, get_game_info
from .system import get_time, search_web #, capture_image

__all__ = [
    "launch_game",
    "list_games",
    "get_game_info",
    "get_time",
    "search_web",
    # "capture_image",
]
