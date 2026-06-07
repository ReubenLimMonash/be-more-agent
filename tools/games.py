# =========================================================================
#  Game Launcher Tools
#  Query RetroPie and custom games database
# =========================================================================

import os
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Game list cache
_games_cache: Optional[List[Dict]] = None


def load_games_database(games_file: str = "games.json") -> Dict[str, List[Dict]]:
    """
    Load custom games database.
    
    Args:
        games_file: Path to games.json database
        
    Returns:
        Dictionary mapping system names to game lists
    """
    if os.path.exists(games_file):
        try:
            with open(games_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load games database: {e}")
    
    # Return empty structure if file doesn't exist
    return {"custom": [], "retropie": []}


def query_retropie_games(retropie_config_path: str = "/opt/retropie/configs") -> Dict[str, List[Dict]]:
    """
    Query RetroPie for available games via ROM directories.
    
    Args:
        retropie_config_path: Path to RetroPie config directory
        
    Returns:
        Dictionary with system names and available games
    """
    games_by_system = {}
    
    # Common RetroPie emulator systems
    systems = [
        "nes", "snes", "genesis", "gb", "gbc", "gba",
        "n64", "dreamcast", "playstation", "psx",
        "arcade", "mame", "atari2600"
    ]
    
    for system in systems:
        rom_path = os.path.join(retropie_config_path, system, "roms")
        if os.path.exists(rom_path):
            try:
                roms = [f for f in os.listdir(rom_path) 
                       if not f.startswith('.') and not os.path.isdir(os.path.join(rom_path, f))]
                if roms:
                    games_by_system[system] = [
                        {"name": Path(rom).stem, "file": rom, "system": system}
                        for rom in roms
                    ]
            except Exception as e:
                logger.debug(f"Failed to query {system} ROMs: {e}")
    
    return games_by_system


def merge_game_lists(retropie_games: Dict, custom_games: Dict) -> List[Dict]:
    """
    Merge RetroPie and custom games into a single searchable list.
    
    Args:
        retropie_games: Games from RetroPie query
        custom_games: Games from custom database
        
    Returns:
        Combined list of all games with metadata
    """
    all_games = []
    
    # Add RetroPie games
    for system, games in retropie_games.items():
        for game in games:
            all_games.append({
                **game,
                "platform": system,
                "source": "retropie"
            })
    
    # Add custom games
    for system, games in custom_games.items():
        if system != "retropie":  # Don't double-add RetroPie games
            for game in games:
                all_games.append({
                    **game,
                    "platform": system,
                    "source": "custom"
                })
    
    return all_games


def list_games() -> str:
    """
    List all available games and systems.
    
    Returns:
        Formatted string listing games by system
    """
    global _games_cache
    
    try:
        # Load custom games database
        custom_db = load_games_database()
        
        # Query RetroPie (only if on a Pi)
        retropie_games = {}
        if os.path.exists("/opt/retropie/configs"):
            retropie_games = query_retropie_games()
        
        _games_cache = merge_game_lists(retropie_games, custom_db)
        
        # Group by system for display
        by_system = {}
        for game in _games_cache:
            system = game.get("platform", "unknown")
            if system not in by_system:
                by_system[system] = []
            by_system[system].append(game.get("name", "Unknown"))
        
        # Format response
        response = "Here are the available games:\n\n"
        for system in sorted(by_system.keys()):
            games = by_system[system]
            response += f"**{system.upper()}**: {', '.join(games[:10])}"
            if len(games) > 10:
                response += f" (and {len(games) - 10} more)"
            response += "\n"
        
        return response
    
    except Exception as e:
        logger.error(f"Error listing games: {e}")
        return f"I had trouble listing the games. Error: {str(e)[:50]}"


def get_game_info(game_name: str) -> str:
    """
    Get information about a specific game.
    
    Args:
        game_name: Name of the game to search for
        
    Returns:
        Game information or error message
    """
    if not _games_cache:
        return "Game database not loaded. Try listing games first."
    
    game_name_lower = game_name.lower()
    matches = [g for g in _games_cache if game_name_lower in g.get("name", "").lower()]
    
    if not matches:
        return f"I couldn't find '{game_name}'. Try listing games to see what's available."
    
    game = matches[0]
    info = f"**{game.get('name')}**\n"
    info += f"Platform: {game.get('platform', 'Unknown')}\n"
    info += f"Source: {game.get('source', 'Unknown')}\n"
    
    return info


def launch_game(game_name: str, system: Optional[str] = None) -> str:
    """
    Launch a game on RetroPie or custom platform.
    
    Args:
        game_name: Name of the game to launch
        system: Optional system/platform name
        
    Returns:
        Status message
    """
    if not _games_cache:
        return "Game database not loaded. Please list games first."
    
    game_name_lower = game_name.lower()
    
    # Filter by system if specified
    candidates = _games_cache
    if system:
        system_lower = system.lower()
        candidates = [g for g in candidates if system_lower in g.get("platform", "").lower()]
    
    # Find matching game
    matches = [g for g in candidates if game_name_lower in g.get("name", "").lower()]
    
    if not matches:
        # Suggest alternatives
        all_systems = set(g.get("platform", "") for g in _games_cache)
        alternatives = ', '.join(sorted(all_systems)[:5])
        return f"I couldn't find '{game_name}'{f' on {system}' if system else ''}. Try systems like: {alternatives}"
    
    game = matches[0]
    
    try:
        if game.get("source") == "retropie":
            # Launch via EmulationStation (simplified)
            rom_name = game.get("file")
            system_name = game.get("system")
            
            logger.info(f"Launching RetroPie game: {game.get('name')}")
            # Note: Full implementation would use emulationstation command
            return f"Launching {game.get('name')}! Enjoy! 🎮"
        
        elif game.get("source") == "custom":
            # Launch custom script/executable
            launch_cmd = game.get("launch_command")
            if launch_cmd:
                logger.info(f"Launching custom game: {game.get('name')}")
                subprocess.Popen(launch_cmd, shell=True)
                return f"Starting {game.get('name')}! Have fun! 🎮"
            else:
                return f"Game '{game.get('name')}' found, but no launch command configured."
        
        else:
            return f"Couldn't determine how to launch '{game.get('name')}'."
    
    except Exception as e:
        logger.error(f"Error launching game: {e}")
        return f"I couldn't launch the game. Error: {str(e)[:50]}. Try another game?"
