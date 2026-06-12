# orchestrator/state.py — northstar-bank

from typing import Annotated, Optional

from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages:          Annotated[list, add_messages]
    original_question: str
    question:          str
    retry_count:       int
    sources:           list[dict]
    sql_result:        Optional[dict]
    intent:            str
    tool_call_id:       Optional[str]
    scores:       Optional[float]
