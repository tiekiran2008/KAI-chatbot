"""
Human-in-the-Loop (HITL) Approval API Endpoints.

Provides REST endpoints to check pending approvals, and to approve, reject,
or submit an edited version of an action that was interrupted by LangGraph.

All endpoints resume the graph using Command(resume=...) with the same
thread_id (chat_id) that was used when the graph was originally interrupted.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user
from app.models.user import User
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request Schemas ────────────────────────────────────────────────────────────

class EditRequest(BaseModel):
    edited_content: str


class ApprovalResponse(BaseModel):
    status: str
    chat_id: str
    message: Optional[str] = None
    final_response: Optional[str] = None


# ── Helper: resume graph ───────────────────────────────────────────────────────

async def _resume_graph(chat_id: uuid.UUID, resume_value: str) -> dict:
    """
    Resumes an interrupted LangGraph run for the given chat_id using Command(resume=...).
    Returns the final state after resumption.
    """
    from langgraph.types import Command
    from app.graph.graph import graph_app

    config = {"configurable": {"thread_id": str(chat_id)}}
    command = Command(resume=resume_value)

    try:
        logger.info(f"[HITL] Resuming graph for chat_id={chat_id}, resume='{resume_value[:40]}'")
        final_state = await graph_app.ainvoke(command, config=config)
        return final_state
    except Exception as e:
        logger.error(f"[HITL] Failed to resume graph for chat_id={chat_id}: {e}")
        raise


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/{chat_id}/pending", summary="Check if a chat has a pending HITL approval")
async def get_pending_approval(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Returns the pending action details if the graph is currently interrupted for this chat.
    Returns 404 if no interrupt is pending.
    """
    if not settings.HITL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HITL is disabled."
        )

    try:
        from app.graph.checkpointer import get_checkpointer
        from app.graph.graph import graph_app

        checkpointer = get_checkpointer()
        config = {"configurable": {"thread_id": str(chat_id)}}
        state_snapshot = await graph_app.aget_state(config)

        if state_snapshot and state_snapshot.tasks:
            # Check for interrupt payload in pending tasks
            for task in state_snapshot.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    interrupt_payload = task.interrupts[0].value
                    return {
                        "status": "hitl_pending",
                        "chat_id": str(chat_id),
                        "pending_action": interrupt_payload.get("pending_action", ""),
                        "pending_action_type": interrupt_payload.get("pending_action_type", "unknown"),
                        "message": interrupt_payload.get("message", ""),
                        "actions": interrupt_payload.get("actions", ["approve", "edit", "reject"])
                    }

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending approval found for this chat."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HITL] get_pending_approval failed for chat_id={chat_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check pending approval state."
        )


@router.post("/{chat_id}/approve", response_model=ApprovalResponse, summary="Approve a pending action")
async def approve_action(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Approves the pending action for the given chat and resumes LangGraph execution.
    The graph will execute the approved action and return the final response.
    """
    if not settings.HITL_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HITL is disabled.")

    try:
        final_state = await _resume_graph(chat_id, "approved")
        final_response = final_state.get("final_response", "Action executed successfully.")
        logger.info(f"[HITL] Action APPROVED for chat_id={chat_id}")
        return ApprovalResponse(
            status="approved",
            chat_id=str(chat_id),
            message="Action has been approved and executed.",
            final_response=final_response,
        )
    except Exception as e:
        logger.error(f"[HITL] approve_action failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve and resume action: {str(e)}"
        )


@router.post("/{chat_id}/reject", response_model=ApprovalResponse, summary="Reject a pending action")
async def reject_action(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Rejects the pending action for the given chat and resumes LangGraph execution
    with a cancellation response.
    """
    if not settings.HITL_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HITL is disabled.")

    try:
        final_state = await _resume_graph(chat_id, "rejected")
        final_response = final_state.get("final_response", "Action has been cancelled.")
        logger.info(f"[HITL] Action REJECTED for chat_id={chat_id}")
        return ApprovalResponse(
            status="rejected",
            chat_id=str(chat_id),
            message="Action has been rejected.",
            final_response=final_response,
        )
    except Exception as e:
        logger.error(f"[HITL] reject_action failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject and resume action: {str(e)}"
        )


@router.post("/{chat_id}/edit", response_model=ApprovalResponse, summary="Submit an edited action and approve it")
async def edit_and_approve_action(
    chat_id: uuid.UUID,
    request: EditRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Approves the action with user-edited content. The edited version replaces
    the original draft when the graph resumes.
    """
    if not settings.HITL_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HITL is disabled.")

    if not request.edited_content or not request.edited_content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="edited_content must not be empty."
        )

    try:
        resume_value = f"edited:{request.edited_content.strip()}"
        final_state = await _resume_graph(chat_id, resume_value)
        final_response = final_state.get("final_response", "Action executed with your edits.")
        logger.info(f"[HITL] Action EDITED+APPROVED for chat_id={chat_id}")
        return ApprovalResponse(
            status="edited",
            chat_id=str(chat_id),
            message="Action approved with your edits and executed.",
            final_response=final_response,
        )
    except Exception as e:
        logger.error(f"[HITL] edit_and_approve_action failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to edit and resume action: {str(e)}"
        )
