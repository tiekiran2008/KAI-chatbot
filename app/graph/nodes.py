import asyncio
import logging
import uuid
from typing import Dict, Any

from app.graph.state import GraphState
from app.services.gemini import gemini_service
from app.services.rag import rag_service
from app.services.prompt_builder import prompt_builder
from app.tools.registry import execute_tool
from app.memory.service import memory_service

logger = logging.getLogger(__name__)

# Note: We reuse the existing CONTEXT_WINDOW_LIMIT logic from chat_service.
# In a real microservice, we'd extract this into a shared config.
CONTEXT_WINDOW_LIMIT = 12

async def receive_user_input(state: GraphState) -> GraphState:
    """
    Initializes the state by formatting the chat history.
    """
    logger.info("Executing Node: receive_user_input")
    return state

async def retrieve_memory(state: GraphState) -> GraphState:
    """
    Retrieves long-term semantic and episodic memories from Supabase
    and injects them into the state so generate_final_answer can use them.
    This runs before classify/RAG to give the LLM full context.
    """
    logger.info("Executing Node: retrieve_memory")
    user_id_str = state.get("user_id")
    if not user_id_str:
        return {"agent_memories": None}
    try:
        user_id = uuid.UUID(user_id_str)
        memories = await memory_service.get_memories(user_id)
        return {"agent_memories": memories if memories else None}
    except Exception as e:
        logger.error(f"[Memory] retrieve_memory node failed: {e}")
        return {"agent_memories": None}

async def extract_memory(state: GraphState) -> GraphState:
    """
    Spawns memory extraction as a fire-and-forget background task.
    This guarantees the streaming response is NEVER delayed by memory writes.
    """
    logger.info("Executing Node: extract_memory (fire-and-forget)")
    user_id_str = state.get("user_id")
    history = state.get("history", [])
    user_message = state.get("user_message", "")

    # We need the assistant's response, which is in the final_response (non-streaming path)
    # For streaming path, we pass an empty string so analysis still runs for semantic memory
    assistant_response = state.get("final_response") or ""

    if user_id_str and history:
        try:
            user_id = uuid.UUID(user_id_str)
            # Fire-and-forget: does NOT await, so streaming isn't blocked
            asyncio.create_task(
                memory_service.analyze_and_store(
                    user_id=user_id,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    history=history
                )
            )
        except Exception as e:
            logger.error(f"[Memory] extract_memory task creation failed: {e}")

    # Always pass through — memory extraction is non-blocking
    return {}

async def decide_action(state: GraphState) -> GraphState:
    """
    Analyzes the user's input to determine if we need RAG, a Tool, or direct response.
    We reuse the gemini_service.classify_query, but augment it to check for tool usage
    if necessary, or simply rely on the RAG vs Chat distinction for now.
    """
    logger.info("Executing Node: decide_action")
    content = state["user_message"]
    
    # 1. Use the existing classifier
    classification = await gemini_service.classify_query(content)
    logger.info(f"LangGraph Classifier: '{content}' -> '{classification}'")
    
    # We will let the routing logic decide based on this classification.
    # To support the Tool node natively, we could add a LLM tool-binding call here,
    # but to preserve Gemini's implicit tool execution without breaking existing flows,
    # we'll use a lightweight heuristic or an extra prompt if needed.
    # For now, we store the classification.
    return {"classification": classification}

async def execute_rag_search(state: GraphState) -> GraphState:
    """
    Retrieves contexts from the RAG service if the classification requires it.
    """
    logger.info("Executing Node: execute_rag_search")
    content = state["user_message"]
    classification = state.get("classification", "RAG question")
    user_id = state["user_id"]
    history = state.get("history", [])
    
    retrieval_query = content
    if classification == "follow-up question":
        try:
            retrieval_query = await gemini_service.reformulate_query(history, content)
            logger.info(f"Reformulated query: '{retrieval_query}'")
        except Exception as e:
            logger.error(f"Query reformulation failed: {e}")
            
    contexts = []
    try:
        contexts = await rag_service.retrieve_context(user_id=user_id, query=retrieval_query)
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        
    scratchpad = state.get("scratchpad", [])
    new_entry = {"agent": "RAG Agent", "content": f"Retrieved {len(contexts)} contexts."}
    return {"contexts": contexts, "scratchpad": scratchpad + [new_entry], "active_agent": "rag_agent"}

async def execute_tool_node(state: GraphState) -> GraphState:
    """
    Legacy fallback tool execution node.
    Executes a specific tool based on the state (tool_name / tool_args must already be set).
    """
    logger.info("Executing Node: execute_tool_node (legacy fallback)")
    tool_name = state.get("tool_name")
    tool_args = state.get("tool_args", {})

    if tool_name:
        logger.info(f"[Tool Node] Executing tool: {tool_name!r} with args: {tool_args!r}")
        result = execute_tool(tool_name, tool_args)
        logger.info(f"[Tool Node] Tool '{tool_name}' result: {result!r}")
        scratchpad = state.get("scratchpad", [])
        new_entry = {"agent": "Tool Agent", "content": f"Executed tool '{tool_name}' with result: {result}"}
        return {"tool_result": result, "scratchpad": scratchpad + [new_entry], "active_agent": "tool_agent"}
    logger.warning("[Tool Node] execute_tool_node called but no tool_name in state — skipping.")
    return {}

async def generate_final_answer(state: GraphState) -> GraphState:
    """
    Generates the final answer using the Gemini LLM.
    Logs every step of tool usage so the pipeline is fully traceable.
    """
    logger.info("Executing Node: generate_final_answer")

    # ── Diagnostic: show which agent ran and what tool (if any) was used ──────
    active_agent = state.get("active_agent", "(none)")
    tool_name = state.get("tool_name", None)
    tool_args = state.get("tool_args", {})
    tool_result = state.get("tool_result", None)
    classification = state.get("classification", "normal chat")

    logger.info(f"[Final Answer] Active agent  : {active_agent!r}")
    logger.info(f"[Final Answer] Classification: {classification!r}")
    logger.info(f"[Final Answer] Tool name     : {tool_name!r}")
    logger.info(f"[Final Answer] Tool args     : {tool_args!r}")
    logger.info(f"[Final Answer] Tool result   : {tool_result!r}")
    if tool_name and not tool_result:
        logger.warning(
            f"[Final Answer] ⚠️  tool_name is set ({tool_name!r}) but tool_result is empty. "
            "The tool may not have been executed correctly."
        )

    raw_history = state.get("history", [])
    contexts = state.get("contexts", [])
    system_prompt_raw = state.get("system_prompt", None)
    history_summary = state.get("history_summary", None)

    # 1. Format history with prompt builder
    formatted_history = prompt_builder.format_history_for_gemini(
        history=raw_history,
        contexts=contexts if classification != "normal chat" else None
    )

    # 2. If a tool was executed, inject its result into the conversation so Gemini
    #    knows the tool output and can compose a natural final answer.
    if tool_name and tool_result:
        from google.genai import types
        logger.info(
            f"[Final Answer] ✅ Injecting tool result into history for Gemini. "
            f"Tool: {tool_name!r}  Result: {tool_result!r}"
        )
        fc_part = types.Part.from_function_call(name=tool_name, args=tool_args or {})
        formatted_history.append(types.Content(role="model", parts=[fc_part]))

        fr_part = types.Part.from_function_response(name=tool_name, response={"result": tool_result})
        formatted_history.append(types.Content(role="user", parts=[fr_part]))
    else:
        logger.info(
            "[Final Answer] No tool result to inject — Gemini will answer from context/memory."
        )

    # 3. Build system prompt (includes agent memories if present)
    agent_memories = state.get("agent_memories", None)
    system_prompt = prompt_builder.build_system_prompt(
        custom_prompt=system_prompt_raw,
        history_summary=history_summary,
        agent_memories=agent_memories
    )

    # Inject multi-agent scratchpad findings
    scratchpad = state.get("scratchpad", [])
    if scratchpad:
        scratchpad_text = "\n\n".join([f"--- {entry['agent']} ---\n{entry['content']}" for entry in scratchpad])
        system_prompt += f"\n\n[Expert Agent Findings]\nThe following specialist agents have contributed to this task:\n{scratchpad_text}\n\nUse their findings to formulate your final response to the user."
        logger.info(f"[Final Answer] Scratchpad injected with {len(scratchpad)} entries.")

    # 4. Request the response from Gemini
    is_streaming = state.get("is_streaming", True)
    logger.info(
        f"[Final Answer] Calling Gemini ({'streaming' if is_streaming else 'non-streaming'}). "
        f"Tools will be passed: {[f.__name__ for f in __import__('app.tools', fromlist=['TOOLS_LIST']).TOOLS_LIST]}"
    )

    if is_streaming:
        response_stream = gemini_service.generate_stream_response(
            history=formatted_history,
            system_prompt=system_prompt
        )
        return {"response_stream": response_stream}
    else:
        ai_response = await gemini_service.generate_response(
            history=formatted_history,
            system_prompt=system_prompt
        )
        return {
            "final_response": ai_response["content"],
            "final_tokens": {
                "prompt_tokens": ai_response.get("prompt_tokens", 0),
                "completion_tokens": ai_response.get("completion_tokens", 0)
            }
        }
