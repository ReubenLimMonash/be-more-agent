# =========================================================================
#  BMO Agent - Pydantic AI Implementation
#  Core agent logic with tool integration
# =========================================================================

import logging
from typing import Optional
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic import BaseModel, Field

# Import tools
from tools.games import launch_game, list_games, get_game_info
from tools.system import get_time, search_web#, capture_image

from config import BMO_SYSTEM_PROMPT, GROQ_API_KEY, TEXT_MODEL

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# =========================================================================
# DEPENDENCY INJECTION
# =========================================================================

@dataclass
class BMODeps:
    """Dependencies available to the agent and tools."""
    retropie_config_path: str = "/opt/retropie/configs"
    games_db_file: str = "games.json"
    logger: logging.Logger = None
    
    def __post_init__(self):
        if self.logger is None:
            self.logger = logger


# =========================================================================
# OUTPUT MODELS
# =========================================================================

class BMOResponse(BaseModel):
    """Structured response from BMO agent."""
    text: str = Field(description="The main response text to speak to user")
    used_tool: Optional[str] = Field(default=None, description="Which tool was used, if any")
    success: bool = Field(default=True, description="Whether the operation succeeded")


# =========================================================================
# AGENT SETUP
# =========================================================================

# Create the Pydantic AI agent
bmo_agent = Agent(
    model=GroqModel(TEXT_MODEL, provider=GroqProvider(api_key=GROQ_API_KEY)),
    deps_type=BMODeps,
    output_type=BMOResponse,
    system_prompt=BMO_SYSTEM_PROMPT,
    name="BMO"
)


# =========================================================================
# TOOL REGISTRATION
# =========================================================================

@bmo_agent.tool_plain
def list_available_games() -> str:
    """List all games available to play. Use when user asks 'what games' or 'what can we play'."""
    return list_games()


@bmo_agent.tool_plain
def get_game_details(game_name: str) -> str:
    """Get information about a specific game. Use to show game details."""
    return get_game_info(game_name)


@bmo_agent.tool_plain
def play_game(game_name: str, system: Optional[str] = None) -> str:
    """Launch a game to play. Call this when user wants to play something!
    
    Args:
        game_name: Name of the game to launch
        system: Optional system/platform (nes, snes, custom, etc)
    """
    return launch_game(game_name, system)


@bmo_agent.tool_plain
def tell_time() -> str:
    """Get the current time. Use when user asks 'what time' or similar."""
    return get_time()


@bmo_agent.tool_plain
def search_for_info(query: str) -> str:
    """Search the internet for information.
    
    Args:
        query: What to search for
    """
    return search_web(query)


# @bmo_agent.tool_plain
# def take_picture(image_path: str = "current_image.jpg") -> str:
#     """Capture a photo with the camera. Use when user asks to take a picture or 'what do you see'."""
#     return capture_image(image_path)


# =========================================================================
# HELPER: Run agent synchronously
# =========================================================================

async def run_bmo_async(user_input: str, deps: BMODeps) -> BMOResponse:
    """
    Run the BMO agent asynchronously.
    
    Args:
        user_input: The user's message
        deps: Dependency injection with config
        
    Returns:
        BMOResponse with text and metadata
    """
    try:
        result = await bmo_agent.run(user_input, deps=deps)
        return result.output
    except Exception as e:
        logger.error(f"Agent error: {e}")
        return BMOResponse(
            text=f"I had a brain freeze! {str(e)[:50]}",
            success=False
        )


def create_bmo_agent_deps(
    retropie_config: str = "/opt/retropie/configs",
    games_db: str = "games.json"
) -> BMODeps:
    """
    Create dependency injection object for the agent.
    
    Args:
        retropie_config: Path to RetroPie config
        games_db: Path to custom games database
        
    Returns:
        BMODeps object
    """
    return BMODeps(
        retropie_config_path=retropie_config,
        games_db_file=games_db,
        logger=logger
    )
