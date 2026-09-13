"""
Shared state object passed between every node in the LangGraph workflow.

Using a TypedDict (rather than a plain dict) gives LangGraph a schema it can
validate against, and gives you autocomplete everywhere else in the codebase.
"""
from typing import TypedDict, List, Optional, Any


class AgentState(TypedDict):
    messages: List[Any]            # running LangChain message history for this turn
    user_query: str                # the raw question the user typed
    intent: str                    # "data_question" | "greeting" | "unsupported"
    plan: Optional[str]            # (reserved) natural-language plan, if you want to surface it
    tool_result: Optional[str]     # raw output returned by whichever tool(s) ran
    final_response: Optional[str]  # the natural-language answer shown to the user
    dataframe_loaded: bool         # whether a dataset is currently loaded
