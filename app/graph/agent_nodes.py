import logging
import json
from typing import Dict, Any

from google.genai import types

from app.graph.state import GraphState
from app.services.gemini import gemini_service
from app.tools import TOOLS_LIST, execute_tool

logger = logging.getLogger(__name__)


async def orchestrator_node(state: GraphState) -> GraphState:
    """
    The Orchestrator evaluates the user request and delegates to a specialist agent
    or decides to generate the final response.

    When routing to tool_agent, also extracts which tool to call and with what args
    so that tool_agent_node can execute without an extra LLM round-trip.
    """
    logger.info("Executing Node: orchestrator_node")
    user_message = state.get("user_message", "")
    scratchpad = state.get("scratchpad", [])

    # Format scratchpad to see what has been done
    scratchpad_text = "None"
    if scratchpad:
        scratchpad_text = "\n".join([f"- {s['agent']} completed task." for s in scratchpad])

    system_prompt = f"""You are the Orchestrator Agent. Your job is to route the user's request to the correct specialist.
Available specialists:
- "rag_agent": For answering questions using our internal knowledge base / documents.
- "tool_agent": For math calculations, checking the current time/date, or Wikipedia lookups.
- "research_agent": For general research and deep-dive analysis.
- "coding_agent": For writing, analyzing, or debugging code.
- "FINISH": If the request has been fully handled by specialists OR if you can answer it directly without specialists.

IMPORTANT: Always route to "tool_agent" when the user asks about:
- The current time, date, day of the week, or timezone
- Mathematical calculations or expressions
- Wikipedia / factual lookups

Previous actions taken: {scratchpad_text}

Return a valid JSON object. For tool_agent, also include "tool_name" and "tool_args".
Available tools:
- "get_current_time": no arguments needed — use {{}} for args
- "calculate": requires {{"expression": "<math expression>"}}
- "search_wikipedia": requires {{"query": "<search query>"}}

Examples:
{{"next_agent": "tool_agent", "tool_name": "get_current_time", "tool_args": {{}}}}
{{"next_agent": "tool_agent", "tool_name": "calculate", "tool_args": {{"expression": "325 * 487"}}}}
{{"next_agent": "tool_agent", "tool_name": "search_wikipedia", "tool_args": {{"query": "LangGraph"}}}}
{{"next_agent": "rag_agent"}}
{{"next_agent": "FINISH"}}
"""

    try:
        response = await gemini_service.client.aio.models.generate_content(
            model=gemini_service.model_name,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            )
        )

        result = json.loads(response.text)
        next_agent = result.get("next_agent", "FINISH")
        tool_name = result.get("tool_name", None)
        tool_args = result.get("tool_args", {})

        logger.info(
            f"[Orchestrator] Decision: next_agent={next_agent!r}  "
            f"tool_name={tool_name!r}  tool_args={tool_args!r}"
        )
        return {
            "next_agent": next_agent,
            "active_agent": "orchestrator",
            "tool_name": tool_name,
            "tool_args": tool_args,
        }
    except Exception as e:
        logger.error(f"Orchestrator failed to parse JSON: {e}")
        return {"next_agent": "FINISH"}


async def tool_agent_node(state: GraphState) -> GraphState:
    """
    Specialist Tool Agent.

    Executes the tool that was identified by the orchestrator (tool_name / tool_args
    are already set in state).  If for some reason they are missing, falls back to
    letting Gemini select the right tool through native function-calling.

    Detailed diagnostic logging is emitted at every step so you can trace:
      - which agent was selected
      - which tool was requested
      - the tool input
      - the tool output
      - whether Gemini actually requested a tool
      - why a tool was or was not called
    """
    logger.info("Executing Node: tool_agent_node")
    user_message = state.get("user_message", "")
    tool_name = state.get("tool_name", None)
    tool_args = state.get("tool_args", {})
    scratchpad = state.get("scratchpad", [])

    # ── Path A: orchestrator already resolved tool name + args ────────────────
    if tool_name:
        logger.info(f"[Tool Agent] ✅ Orchestrator pre-selected tool: {tool_name!r} with args: {tool_args!r}")
        result = execute_tool(tool_name, tool_args)
        logger.info(f"[Tool Agent] ✅ Tool '{tool_name}' executed. Result: {result!r}")
        new_entry = {
            "agent": "Tool Agent",
            "content": f"Tool '{tool_name}' was called with args {tool_args}. Result: {result}"
        }
        return {
            "tool_result": result,
            "scratchpad": scratchpad + [new_entry],
            "active_agent": "tool_agent",
        }

    # ── Path B: fallback — let Gemini decide via native function-calling ──────
    logger.warning(
        "[Tool Agent] ⚠️  No tool_name in state — falling back to Gemini native "
        "function-calling to select a tool."
    )
    try:
        tool_system = (
            "You are a Tool Agent. You have access to the following tools:\n"
            "- get_current_time(): returns the current date and time\n"
            "- calculate(expression): evaluates a math expression\n"
            "- search_wikipedia(query): searches Wikipedia\n\n"
            "You MUST call the appropriate tool to answer the user's question. "
            "Never answer from memory when a tool exists for it."
        )
        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=user_message)]
            )
        ]
        config = types.GenerateContentConfig(
            system_instruction=tool_system,
            tools=TOOLS_LIST,
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",  # Force Gemini to always call a tool
                )
            ),
        )

        logger.info(f"[Tool Agent] Sending to Gemini with tools bound. User message: {user_message!r}")
        response = await gemini_service.client.aio.models.generate_content(
            model=gemini_service.model_name,
            contents=contents,
            config=config,
        )

        # Check if Gemini called a function
        fc = None
        if (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    break

        if fc:
            fc_name = fc.name
            fc_args = {k: v for k, v in fc.args.items()} if fc.args else {}
            logger.info(f"[Tool Agent] ✅ Gemini requested tool: {fc_name!r} with args: {fc_args!r}")
            result = execute_tool(fc_name, fc_args)
            logger.info(f"[Tool Agent] ✅ Tool '{fc_name}' executed. Result: {result!r}")
            new_entry = {
                "agent": "Tool Agent",
                "content": f"Tool '{fc_name}' was called with args {fc_args}. Result: {result}"
            }
            return {
                "tool_name": fc_name,
                "tool_args": fc_args,
                "tool_result": result,
                "scratchpad": scratchpad + [new_entry],
                "active_agent": "tool_agent",
            }
        else:
            logger.warning(
                f"[Tool Agent] ⚠️  Gemini did NOT call a tool. Response text: {response.text!r}. "
                "This means no suitable tool was found or Gemini answered directly."
            )
            new_entry = {
                "agent": "Tool Agent",
                "content": response.text or "(no response)"
            }
            return {
                "scratchpad": scratchpad + [new_entry],
                "active_agent": "tool_agent",
            }
    except Exception as e:
        logger.error(f"[Tool Agent] ❌ Tool execution failed: {e}")
        new_entry = {"agent": "Tool Agent", "content": f"Error: {e}"}
        return {"scratchpad": scratchpad + [new_entry], "active_agent": "tool_agent"}


async def research_agent_node(state: GraphState) -> GraphState:
    """
    Specialist agent for conducting research.
    """
    logger.info("Executing Node: research_agent_node")
    user_message = state.get("user_message", "")
    
    system_prompt = "You are an expert Research Agent. Analyze the user's request, gather facts, and provide a detailed research summary."
    
    try:
        response = await gemini_service.generate_response(
            history=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt
        )
        
        scratchpad = state.get("scratchpad", [])
        new_entry = {"agent": "Research Agent", "content": response["content"]}
        return {"scratchpad": scratchpad + [new_entry], "active_agent": "research_agent"}
    except Exception as e:
        logger.error(f"Research agent failed: {e}")
        return {}


async def coding_agent_node(state: GraphState) -> GraphState:
    """
    Specialist agent for coding tasks.
    """
    logger.info("Executing Node: coding_agent_node")
    user_message = state.get("user_message", "")
    
    system_prompt = "You are an expert Coding Agent. Write robust, clean, and well-documented code to solve the user's request."
    
    try:
        response = await gemini_service.generate_response(
            history=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt
        )
        
        scratchpad = state.get("scratchpad", [])
        new_entry = {"agent": "Coding Agent", "content": response["content"]}
        return {"scratchpad": scratchpad + [new_entry], "active_agent": "coding_agent"}
    except Exception as e:
        logger.error(f"Coding agent failed: {e}")
        return {}
