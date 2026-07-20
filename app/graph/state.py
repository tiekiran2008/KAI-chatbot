from typing import TypedDict, List, Dict, Any, Optional

class GraphState(TypedDict, total=False):
    """
    Typed dictionary representing the state of the LangGraph execution.
    total=False allows for optional keys without explicitly setting them to None.
    """
    user_id: str
    user_message: str
    chat_id: str
    history: List[Dict[str, str]]
    contexts: List[Dict[str, Any]]
    
    # Decisions and Routing
    classification: str # e.g., "RAG question", "tool", "normal chat"
    
    # Multi-Agent Routing & Memory
    next_agent: Optional[str] # Determines next node in the graph (e.g. "rag_agent", "FINISH")
    active_agent: Optional[str] # Tracks which agent is currently executing
    scratchpad: List[Dict[str, Any]] # A list of intermediate messages/findings from specialist agents
    
    # Agent Memory (retrieved from Supabase at start of graph run)
    agent_memories: Optional[str]
    
    # Tools
    tool_name: Optional[str]
    tool_args: Optional[Dict[str, Any]]
    tool_result: Optional[str]
    
    # System context
    system_prompt: Optional[str]
    history_summary: Optional[str]
    is_streaming: bool

    # Human-in-the-Loop (HITL)
    pending_action: Optional[str]       # Description of action needing approval
    pending_action_type: Optional[str]  # e.g. "send_email", "delete_record"
    pending_action_payload: Optional[Dict[str, Any]]  # Structured data for the action
    approval_status: Optional[str]      # "approved" | "rejected" | "edited"
    edited_content: Optional[str]       # User-provided edited version of draft

    # Outcomes
    final_response: Optional[str]
    response_stream: Any  # Can hold an AsyncGenerator for streaming back to client
    final_tokens: Optional[Dict[str, int]]

