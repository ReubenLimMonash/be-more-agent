# =========================================================================
#  Async/Sync Bridge
#  Allows GUI (sync/threaded) to call Pydantic AI agent (async)
# =========================================================================

import asyncio
import threading
import logging
import time
from typing import Optional, Callable
from bmo_agent import run_bmo_async, create_bmo_agent_deps, BMOResponse
from config import CURRENT_CONFIG, RETROPIE_CONFIG_PATH, GAMES_LIST_FILE

logger = logging.getLogger(__name__)


class AgentBridge:
    """Bridge between sync GUI thread and async Pydantic AI agent."""
    
    def __init__(self, on_thinking: Optional[Callable] = None, on_response: Optional[Callable] = None):
        """
        Initialize the bridge.
        
        Args:
            on_thinking: Callback when agent starts thinking (no args)
            on_response: Callback when response arrives (takes text: str, tool_name: Optional[str])
        """
        self.on_thinking = on_thinking or (lambda: None)
        self.on_response = on_response or (lambda text, tool: None)
        
        # Create agent dependencies
        self.deps = create_bmo_agent_deps(
            retropie_config=RETROPIE_CONFIG_PATH,
            games_db=GAMES_LIST_FILE
        )
        
        # Event loop for async operations
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_event_loop()
    
    def _start_event_loop(self):
        """Start a background event loop for async operations."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        
        # Give thread time to start
        time.sleep(0.1)
    
    def run_agent(self, user_input: str) -> BMOResponse:
        """
        Run the agent with user input (synchronous call from GUI).
        
        Args:
            user_input: User's message
            
        Returns:
            BMOResponse from the agent
        """
        if self._loop is None:
            logger.error("Event loop not started")
            return BMOResponse(
                text="I'm not ready yet. Please try again.",
                success=False
            )
        
        # Show thinking state
        self.on_thinking()
        
        try:
            # Submit async task to background event loop
            future = asyncio.run_coroutine_threadsafe(
                run_bmo_async(user_input, self.deps),
                self._loop
            )
            
            # Wait for result (with timeout)
            response = future.result(timeout=30)
            
            # Callback with response
            self.on_response(response.text, response.used_tool)
            
            return response
        
        except asyncio.TimeoutError:
            logger.error("Agent call timed out")
            return BMOResponse(
                text="I'm thinking too hard! Let me try again.",
                success=False
            )
        except Exception as e:
            logger.error(f"Bridge error: {e}")
            return BMOResponse(
                text=f"Something went wrong: {str(e)[:50]}",
                success=False
            )
    
    def shutdown(self):
        """Clean up event loop."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
