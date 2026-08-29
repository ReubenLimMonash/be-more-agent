import os
import logging
from typing import Optional
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic import BaseModel, Field
from config import BMO_SYSTEM_PROMPT, GROQ_API_KEY

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
    
# 1. Initialize the Groq model
# Ensure your chosen model natively supports tool calling (e.g., llama3.1)
model = GroqModel('qwen/qwen3.8-27b', provider=GroqProvider(api_key=GROQ_API_KEY))

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
        # result = agent.run_sync(user_input)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        result = None
    print("Agent Response:")
    print(result.output)

    for msg in result.new_messages():
        for part in getattr(msg, "parts", []):
            kind = type(part).__name__
            if kind == "ToolCallPart":
                print("Tool called:", part.tool_name, "args:", part.args)
            elif kind == "ToolReturnPart":
                print("Tool returned:", part.tool_name, "content:", part.content)
