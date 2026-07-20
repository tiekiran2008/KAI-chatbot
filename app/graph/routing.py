import logging
from typing import Literal

from app.graph.state import GraphState

logger = logging.getLogger(__name__)

def route_orchestrator(state: GraphState) -> Literal["execute_rag_search", "execute_tool_node", "research_agent_node", "coding_agent_node", "detect_action_required"]:
    """
    Decides the next node based on the orchestrator's output.
    """
    next_agent = state.get("next_agent", "FINISH")
    
    if next_agent == "rag_agent":
        logger.info("[Orchestrator] Routing to RAG Agent")
        return "execute_rag_search"
    elif next_agent == "tool_agent":
        logger.info("[Orchestrator] Routing to Tool Agent")
        return "execute_tool_node"
    elif next_agent == "research_agent":
        logger.info("[Orchestrator] Routing to Research Agent")
        return "research_agent_node"
    elif next_agent == "coding_agent":
        logger.info("[Orchestrator] Routing to Coding Agent")
        return "coding_agent_node"
    else:
        logger.info("[Orchestrator] Task complete. Routing to HITL detection.")
        return "detect_action_required"


def route_after_detect(
    state: GraphState,
) -> Literal["human_approval_node", "generate_final_answer"]:
    """
    Routes AFTER detect_action_required.
    If a pending_action was detected, pause for human approval.
    Otherwise, proceed directly to answer generation.
    """
    if state.get("pending_action"):
        logger.info("[HITL] Routing to human_approval_node — action requires approval.")
        return "human_approval_node"
    logger.info("[HITL] No irreversible action detected — routing to generate_final_answer.")
    return "generate_final_answer"


def route_after_approval(
    state: GraphState,
) -> Literal["execute_approved_action", "generate_final_answer"]:
    """
    Routes AFTER human_approval_node.
    If approved or edited, run the action executor.
    If rejected, skip to generation (which will output the refusal from execute_approved_action).
    """
    approval_status = state.get("approval_status")
    if approval_status in ("approved", "edited", "rejected"):
        logger.info(f"[HITL] Approval status={approval_status} — routing to execute_approved_action.")
        return "execute_approved_action"
    logger.info("[HITL] No approval status — routing to generate_final_answer.")
    return "generate_final_answer"
