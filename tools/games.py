# =========================================================================
#  Game Launcher Tools
#  Query RetroPie and custom games database
# =========================================================================

import os
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Paths for the EmulationStation system configurations
SYSTEMS_CFG = "/etc/emulationstation/es_systems.cfg"
USER_SYSTEMS_CFG = os.path.expanduser("~/.emulationstation/es_systems.cfg")


def _get_active_es_config() -> str:
    """Returns the custom user config path if it exists, otherwise the system-wide path."""
    if os.path.exists(USER_SYSTEMS_CFG):
        return USER_SYSTEMS_CFG
    return SYSTEMS_CFG

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


def query_retropie_games(cfg_path: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Query RetroPie for available games via es_systems.cfg ROM directories.
    
    Args:
        cfg_path: Optional path to an es_systems.cfg file; defaults to the
            active user/system EmulationStation config
        
    Returns:
        Dictionary with system names and available games
    """
    games_by_system = {}

    cfg_path = cfg_path or _get_active_es_config()
    if not os.path.exists(cfg_path):
        logger.debug(f"es_systems.cfg not found at: {cfg_path}")
        return games_by_system

    try:
        tree = ET.parse(cfg_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"Error parsing system configuration: {e}")
        return games_by_system

    for system in root.findall("system"):
        name_node = system.find("name")
        path_node = system.find("path")
        ext_node = system.find("extension")

        if name_node is None or path_node is None:
            continue

        system_name = name_node.text
        if not system_name or system_name.lower() == "retropie" or system_name.lower() == "adventuretime":
            continue

        rom_dir = os.path.expanduser(path_node.text)

        # Parse the allowed extensions into a set (e.g., ".sfc .zip .SFC")
        valid_extensions = set()
        if ext_node is not None and ext_node.text:
            valid_extensions = {ext.lower().strip(".") for ext in ext_node.text.split()}

        if not os.path.isdir(rom_dir):
            continue

        try:
            all_files = os.listdir(rom_dir)
            roms = []
            for f in all_files:
                if os.path.isfile(os.path.join(rom_dir, f)):
                    _, ext = os.path.splitext(f)
                    clean_ext = ext.lower().strip(".")
                    if not valid_extensions or clean_ext in valid_extensions:
                        roms.append(f)

            if roms:
                games_by_system[system_name] = [
                    {"name": Path(rom).stem, "file": os.path.join(rom_dir, rom), "system": system_name}
                    for rom in roms
                ]
        except PermissionError:
            logger.debug(f"Permission denied reading ROM directory: {rom_dir}")
        except Exception as e:
            logger.debug(f"Failed to query {system_name} ROMs: {e}")
    
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
        
        # Query RetroPie via es_systems.cfg (only if the config is present)
        retropie_games = {}
        if os.path.exists(_get_active_es_config()):
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
        # Load the games database if not already loaded
        list_games()
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
            rom_path = game.get("file")
            system_name = game.get("system")

            logger.info(f"Launching RetroPie game: {game.get('name')}")
            subprocess.Popen(
                [
                    "env", "-u", "WAYLAND_DISPLAY",
                    "/opt/retropie/supplementary/runcommand/runcommand.sh",
                    "0", "_SYS_", system_name, rom_path,
                ]
            )
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
