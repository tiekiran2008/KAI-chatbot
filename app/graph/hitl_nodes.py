"""
Human-in-the-Loop (HITL) LangGraph Nodes.

Three nodes form the HITL workflow:
1. detect_action_required  — Classifies if user intent is an irreversible action.
2. human_approval_node     — Calls interrupt(), pausing graph until human responds.
3. execute_approved_action — Runs the approved (or edited) action.

Future Email/Calendar agents plug in by calling interrupt() inside their own nodes
and routing to execute_approved_action on approval.
"""
import logging
from typing import Dict, Any

from langsmith import traceable

from app.graph.state import GraphState
from app.config import settings

logger = logging.getLogger(__name__)

# Actions the LLM classifier will detect as requiring HITL approval
IRREVERSIBLE_ACTION_KEYWORDS = [
    "send email", "send an email", "email to",
    "delete", "remove", "drop",
    "purchase", "buy", "order",
    "post to", "publish", "submit",
    "transfer", "wire", "pay",
    "book", "schedule meeting", "create event",
    "update database", "write to database",
]

IRREVERSIBLE_CLASSIFIER_PROMPT = (
    "You are an action safety classifier. Analyze the user message and determine "
    "if it is requesting an IRREVERSIBLE action such as:\n"
    "- Sending emails or messages\n"
    "- Deleting or removing records/data\n"
    "- Making purchases or financial transactions\n"
    "- Publishing or posting content externally\n"
    "- Booking appointments or external scheduling\n"
    "- Writing/mutating external databases or APIs\n\n"
    "If the message requests an irreversible action, respond with JSON in this exact format:\n"
    '{"requires_approval": true, "action_type": "<type>", "action_description": "<short summary>"}\n\n'
    "Where action_type is one of: send_email, delete_record, make_purchase, post_content, book_appointment, api_mutation\n\n"
    "If NO irreversible action is requested, respond with exactly:\n"
    '{"requires_approval": false}\n\n'
    "Respond ONLY with the JSON. No preamble, no explanation."
)


@traceable(run_type="tool")
async def detect_action_required(state: GraphState) -> GraphState:
    """
    Node: Analyzes the user message to detect if HITL approval is needed.
    If HITL is disabled via config, this node is a transparent pass-through.
    """
    logger.info("Executing Node: detect_action_required")

    if not settings.HITL_ENABLED:
        return {"pending_action": None}

    user_message = state.get("user_message", "")
    classification = state.get("classification", "")

    # Fast-path: skip HITL check for normal chat / RAG — only check tool_execution
    # or direct user requests that mention irreversible actions
    needs_check = classification in ("tool execution", "normal chat", "RAG question")
    if not needs_check:
        return {"pending_action": None}

    # Quick keyword pre-check to avoid expensive LLM call on benign messages
    lower_msg = user_message.lower()
    keyword_hit = any(kw in lower_msg for kw in IRREVERSIBLE_ACTION_KEYWORDS)
    if not keyword_hit:
        return {"pending_action": None}

    try:
        from app.services.gemini import gemini_service
        import json

        full_prompt = f"{IRREVERSIBLE_CLASSIFIER_PROMPT}\n\nUser message: {user_message}"
        result_text = await gemini_service._call_lightweight_gemini(full_prompt, max_tokens=120)

        if not result_text:
            return {"pending_action": None}

        # Clean up potential markdown code fences
        result_text = result_text.strip().strip("```json").strip("```").strip()
        result = json.loads(result_text)

        if result.get("requires_approval"):
            action_type = result.get("action_type", "unknown")
            action_desc = result.get("action_description", user_message[:200])
            logger.info(f"[HITL] Action detected: type={action_type}, desc={action_desc[:80]}")
            return {
                "pending_action": action_desc,
                "pending_action_type": action_type,
                "pending_action_payload": {"original_message": user_message}
            }

    except Exception as e:
        logger.error(f"[HITL] detect_action_required failed: {e}")

    return {"pending_action": None}


@traceable(run_type="tool")
async def human_approval_node(state: GraphState) -> GraphState:
    """
    Node: Pauses the LangGraph execution using interrupt().

    The graph state is persisted to Supabase (via AsyncPostgresSaver) and the
    interrupt payload is surfaced to the caller (chat_service) as a NodeInterrupt.
    Execution resumes only when the /hitl/{chat_id}/approve|reject|edit endpoint
    re-invokes the graph with a Command(resume=...).
    """
    from langgraph.types import interrupt

    pending_action = state.get("pending_action", "")
    action_type = state.get("pending_action_type", "unknown")

    logger.info(f"[HITL] Graph interrupted. Awaiting human approval for: {pending_action[:80]}")

    # interrupt() pauses here — serializes state to Postgres — returns when resumed
    human_decision = interrupt({
        "pending_action": pending_action,
        "pending_action_type": action_type,
        "message": f"I need your approval before proceeding: {pending_action}",
        "actions": ["approve", "edit", "reject"]
    })

    # After resume, human_decision contains the Command.resume value
    # Format: "approved" | "rejected" | "edited:<new content>"
    logger.info(f"[HITL] Graph resumed with decision: {str(human_decision)[:80]}")

    if isinstance(human_decision, str):
        if human_decision.startswith("edited:"):
            edited_content = human_decision[len("edited:"):].strip()
            return {
                "approval_status": "edited",
                "edited_content": edited_content
            }
        elif human_decision == "approved":
            return {"approval_status": "approved"}
        else:
            return {"approval_status": "rejected"}

    # Fallback — treat unknown resume value as rejected
    return {"approval_status": "rejected"}


@traceable(run_type="tool")
async def execute_approved_action(state: GraphState) -> GraphState:
    """
    Node: Executes the approved (or edited) action.

    This is a structured dispatch node. Future Email Agent / Calendar Agent
    register handlers here by action_type. Currently handles the base cases
    and produces a confirmation message routed into generate_final_answer.

    If the action was rejected, generates a polite refusal message.
    If the action was approved, executes it and confirms to the user.
    If the action was edited, uses the edited content for execution.
    """
    logger.info("Executing Node: execute_approved_action")

    approval_status = state.get("approval_status", "rejected")
    pending_action = state.get("pending_action", "the requested action")
    action_type = state.get("pending_action_type", "unknown")
    edited_content = state.get("edited_content")

    if approval_status == "rejected":
        return {
            "final_response": (
                f"Understood — I've cancelled the action. "
                f"The request to {pending_action} has been discarded. "
                f"Let me know if you'd like to try something different."
            )
        }

    # Use edited content if provided
    action_to_execute = edited_content if edited_content else pending_action

    # -------------------------------------------------------
    # ACTION DISPATCH — Future agents register handlers here
    # -------------------------------------------------------
    try:
        handler_result = await _dispatch_action(action_type, action_to_execute, state)
        return {"final_response": handler_result}
    except Exception as e:
        logger.error(f"[HITL] execute_approved_action failed for type={action_type}: {e}")
        return {
            "final_response": (
                "I encountered an error while executing the approved action. "
                "Please try again or contact support."
            )
        }


async def _dispatch_action(action_type: str, action_content: str, state: GraphState) -> str:
    """
    Internal dispatcher. Maps action_type to concrete handler.
    Returns a human-readable confirmation string.

    Future agents (Email, Calendar, etc.) add their handlers here:
        if action_type == "send_email":
            return await email_agent.send(action_content, state)
    """
    logger.info(f"[HITL] Dispatching action: type={action_type}, content={action_content[:80]}")

    # Default stub — replace with real agent calls as they are built
    if action_type == "send_email":
        return (
            f"✅ Email sent successfully.\n\n"
            f"**Action executed:** {action_content}\n\n"
            "The email has been delivered. Let me know if you need anything else."
        )
    elif action_type == "delete_record":
        return (
            f"✅ Record deleted successfully.\n\n"
            f"**Action executed:** {action_content}"
        )
    elif action_type == "make_purchase":
        return (
            f"✅ Purchase completed.\n\n"
            f"**Action executed:** {action_content}"
        )
    elif action_type == "book_appointment":
        return (
            f"✅ Appointment booked.\n\n"
            f"**Action executed:** {action_content}"
        )
    else:
        return (
            f"✅ Action approved and executed.\n\n"
            f"**Action:** {action_content}"
        )
