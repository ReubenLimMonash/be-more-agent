# =========================================================================
#  TEMPLATE: How to Add New Tools to BMO
#  
#  This file shows the pattern for adding new capabilities to the agent.
#  Copy this file and modify to create new tools.
# =========================================================================

from typing import Optional
import logging

logger = logging.getLogger(__name__)


def my_new_tool(param1: str, param2: Optional[int] = None) -> str:
    """
    Description of what this tool does. This docstring becomes the tool's help text!
    
    Args:
        param1: Description of first parameter
        param2: Description of optional second parameter
        
    Returns:
        Result of the tool execution (always return a string for now)
    """
    try:
        # Your implementation here
        result = f"Tool executed with param1={param1}, param2={param2}"
        logger.info(f"Tool success: {result}")
        return result
    
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return f"I encountered an error: {str(e)[:50]}. Try again?"


# =========================================================================
# HOW TO ADD YOUR TOOL TO BMO:
# =========================================================================
#
# 1. Define your function here (like my_new_tool above)
#    - Use type hints (str, int, bool, Optional[T], List[T])
#    - Write a clear docstring (becomes the tool description)
#    - Always return a string (this is what gets spoken to the user)
#    - Handle exceptions gracefully
#
# 2. Add import to tools/__init__.py:
#    from .template import my_new_tool
#    and add to __all__ list
#
# 3. Add mention to BMO_SYSTEM_PROMPT in config.py:
#    Add a line like:
#    6. My custom capability
#    And describe when to use it in INSTRUCTIONS FOR TOOL USE
#
# 4. Register with the Pydantic AI agent in bmo_agent.py:
#    Add a new @bmo_agent.tool_plain function that wraps your tool
#    (The agent decorator will pick it up automatically!)
#
# =========================================================================
# EXAMPLE: Weather Tool
# =========================================================================
#
# def get_weather(location: str, units: str = "celsius") -> str:
#     '''Get current weather for a location.
#     
#     Args:
#         location: City name (e.g. "New York")
#         units: "celsius" or "fahrenheit"
#     
#     Returns:
#         Weather information formatted as string
#     '''
#     try:
#         # In real implementation, call weather API
#         # For now, return a mock response
#         return f"It's sunny in {location}! 🌞 Temp: 72°F"
#     except Exception as e:
#         return f"Couldn't get weather for {location}"
#
# =========================================================================
# ADDING IT TO BMO_AGENT.PY:
# =========================================================================
#
# @bmo_agent.tool_plain
# def get_current_weather(location: str, units: str = "celsius") -> str:
#     """Get current weather for a location.
#     
#     Args:
#         location: City name
#         units: Temperature units (celsius or fahrenheit)
#     """
#     return get_weather(location, units)
#
# =========================================================================
