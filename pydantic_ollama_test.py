import os
import logging
from typing import Optional
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic import BaseModel, Field
from config import BMO_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

os.environ["OLLAMA_API_KEY"] = "a084e34d69a44c98a1be08f9a4f2cdee.xNsU0z5b_k9UHxmt4CH99Imb"  # Replace with your actual API key
os.environ["OLLAMA_BASE_URL"] = "https://ollama.com/v1"  # Replace with your actual base URL if different

@dataclass
class BMODeps:
    """Dependencies available to the agent and tools."""
    retropie_config_path: str = "/opt/retropie/configs"
    games_db_file: str = "games.json"
    logger: logging.Logger = None

class BMOResponse(BaseModel):
    """Structured response from BMO agent."""
    text: str = Field(description="The main response text to speak to user")
    used_tool: Optional[str] = Field(default=None, description="Which tool was used, if any")
    success: bool = Field(default=True, description="Whether the operation succeeded")
    
# 1. Initialize the Ollama Cloud model
# Ensure your chosen model natively supports tool calling (e.g., llama3.1)
model = OllamaModel(
    model_name="gemma3:4b-cloud",
    provider=OllamaProvider(base_url=os.getenv("OLLAMA_BASE_URL")),
    # api_key=os.getenv("OLLAMA_API_KEY")
)

# 2. Define the Agent
agent = Agent(
    model=model,
    system_prompt="You are a helpful assistant. Use your tools to answer questions precisely.",
    deps_type=BMODeps,
    output_type=BMOResponse,
    name="BMO Agent"
)

# 3. Register a tool using the @agent.tool decorator
@agent.tool
def get_current_weather(ctx: RunContext[None], location: str) -> str:
    """Get the current weather for a specific location.

    Args:
        location: The city and state, e.g. San Francisco, CA
    """
    # Dummy tool logic for demonstration purposes
    if "london" in location.lower():
        return "The weather in London is 15°C and rainy."
    return f"The weather in {location} is 22°C and sunny."

# 4. Run the Agent
if __name__ == "__main__":
    # The agent will recognize it needs a tool call to answer this query
    # result = agent.run_sync("What is the weather like in London right now?")
    
    # print("Agent Response:")
    # print(result.output)

    try:
        user_input = "What is the weather like in London right now?"
        deps = BMODeps()
        result = agent.run_sync(user_input, deps=deps)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        
    print("Agent Response:")
    print(result.output)
