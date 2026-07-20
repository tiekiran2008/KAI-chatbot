"""
LangGraph StateGraph definition for the AI Chatbot.

Build order:
  receive_user_input
    → retrieve_memory
    → decide_action  [conditional: RAG / Tool / Direct]
    → detect_action_required  [conditional: HITL / Direct]
    → [human_approval_node → execute_approved_action]  (HITL path)
    → generate_final_answer
    → extract_memory
    → END

The graph is rebuilt at startup with the live AsyncPostgresSaver checkpointer
injected, enabling interrupt()/resume() across HTTP requests.
"""
from langgraph.graph import StateGraph, END

from app.graph.state import GraphState
from app.graph.nodes import (
    receive_user_input,
    retrieve_memory,
    execute_rag_search,
    execute_tool_node,
    generate_final_answer,
    extract_memory,
)
from app.graph.agent_nodes import (
    orchestrator_node,
    tool_agent_node,
    research_agent_node,
    coding_agent_node,
)
from app.graph.hitl_nodes import (
    detect_action_required,
    human_approval_node,
    execute_approved_action,
)
from app.graph.routing import route_orchestrator, route_after_detect, route_after_approval


def build_graph(checkpointer=None):
    """
    Builds and compiles the LangGraph StateGraph for the chatbot.

    Args:
        checkpointer: Optional AsyncPostgresSaver. When provided, enables
                      interrupt()/resume() for HITL workflows. When None,
                      HITL interrupts will raise an error so pass None only
                      when HITL is disabled (HITL_ENABLED=false).
    """
    workflow = StateGraph(GraphState)

    # ── Nodes ────────────────────────────────────────────────────────────
    workflow.add_node("receive_user_input", receive_user_input)
    workflow.add_node("retrieve_memory", retrieve_memory)
    workflow.add_node("orchestrator_node", orchestrator_node)
    workflow.add_node("execute_rag_search", execute_rag_search)
    workflow.add_node("execute_tool_node", execute_tool_node)   # legacy fallback node
    workflow.add_node("tool_agent_node", tool_agent_node)       # primary tool execution node
    workflow.add_node("research_agent_node", research_agent_node)
    workflow.add_node("coding_agent_node", coding_agent_node)
    workflow.add_node("detect_action_required", detect_action_required)
    workflow.add_node("human_approval_node", human_approval_node)
    workflow.add_node("execute_approved_action", execute_approved_action)
    workflow.add_node("generate_final_answer", generate_final_answer)
    workflow.add_node("extract_memory", extract_memory)

    # ── Edges ─────────────────────────────────────────────────────────────
    workflow.set_entry_point("receive_user_input")
    workflow.add_edge("receive_user_input", "retrieve_memory")
    workflow.add_edge("retrieve_memory", "orchestrator_node")

    # Orchestrator decides which agent to route to, or FINISH
    workflow.add_conditional_edges(
        "orchestrator_node",
        route_orchestrator,
        {
            "execute_rag_search": "execute_rag_search",
            "execute_tool_node": "tool_agent_node",   # route tool_agent → tool_agent_node
            "research_agent_node": "research_agent_node",
            "coding_agent_node": "coding_agent_node",
            "detect_action_required": "detect_action_required",
        }
    )

    # All specialist agents return their findings back to the orchestrator
    workflow.add_edge("execute_rag_search", "orchestrator_node")
    workflow.add_edge("tool_agent_node", "orchestrator_node")   # tool results loop back
    workflow.add_edge("execute_tool_node", "orchestrator_node") # legacy fallback
    workflow.add_edge("research_agent_node", "orchestrator_node")
    workflow.add_edge("coding_agent_node", "orchestrator_node")

    # After HITL detection: pause for approval OR go straight to answer
    workflow.add_conditional_edges(
        "detect_action_required",
        route_after_detect,
        {
            "human_approval_node": "human_approval_node",
            "generate_final_answer": "generate_final_answer",
        }
    )

    # After human approval: execute action (covers approved, edited, rejected)
    workflow.add_conditional_edges(
        "human_approval_node",
        route_after_approval,
        {
            "execute_approved_action": "execute_approved_action",
            "generate_final_answer": "generate_final_answer",
        }
    )

    # execute_approved_action sets final_response directly; skip to memory extraction
    workflow.add_edge("execute_approved_action", "extract_memory")

    # Normal answer path
    workflow.add_edge("generate_final_answer", "extract_memory")
    workflow.add_edge("extract_memory", END)

    # Compile — inject checkpointer if provided (required for interrupt/resume)
    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    app = workflow.compile(**compile_kwargs)
    return app


# Initial singleton (no checkpointer) — replaced at startup by main.py
graph_app = build_graph(checkpointer=None)
