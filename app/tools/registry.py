import logging
from typing import Dict, Any, Callable
from langsmith import traceable

logger = logging.getLogger(__name__)

from .calculator import calculate
from .wikipedia_tool import search_wikipedia
from .time_tool import get_current_time

# Dictionary mapping tool names to their corresponding python functions
TOOL_REGISTRY: Dict[str, Callable] = {
    "calculate": calculate,
    "search_wikipedia": search_wikipedia,
    "get_current_time": get_current_time,
}

# The list of functions to pass to the Gemini SDK
TOOLS_LIST = [calculate, search_wikipedia, get_current_time]

@traceable(run_type="tool")
def execute_tool(name: str, args: Dict[str, Any]) -> str:
    """
    Executes a tool by name with the given arguments.
    Returns the result as a string, or an error message if it fails.
    """
    if name not in TOOL_REGISTRY:
        logger.error(f"Tool not found: {name}")
        return f"Error: Tool '{name}' not found in registry."
    
    func = TOOL_REGISTRY[name]
    try:
        # Some functions take no arguments, some take multiple
        logger.info(f"Executing tool: {name} with args: {args}")
        result = func(**args)
        # Ensure result is a string for the LLM
        return str(result)
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return f"Error executing tool {name}: {str(e)}"
