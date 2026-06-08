# app/api/chat_service.py — northstar-bank

from langchain_core.messages import AIMessage, HumanMessage

from app.orchestrator.state import AgentState
from app.orchestrator.graph import get_graph
from typing import AsyncGenerator

def chat(message: str) -> dict:
    """Run one agent turn and return the structured response."""
    initial_state: AgentState = {
        "messages": [HumanMessage(content=message)],
        "original_question": message,
        "question": message,
        "retry_count": 0,
        "sources": [],
        "sql_result": None,
        "intent": "chat",
    }

    final_state = get_graph().invoke(initial_state)

    return {
        "answer": _extract_answer(final_state),
        "intent": final_state["intent"],
        "sources": final_state["sources"],
        "sql_result": final_state["sql_result"],
    }

async def chat_stream(message: str) -> AsyncGenerator[str, None]:
        initial_state = {
            "messages":          [HumanMessage(content=message)],
            "original_question": message,
            "question":          message,
            "retry_count":       0,
            "sources":           [],
            "sql_result":        None,
            "intent":            "chat",
        }
        async for event in get_graph().astream_events(initial_state, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield chunk.content


def _extract_answer(state: AgentState) -> str:
    """Return the last AIMessage content that is not a tool call."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            return msg.content
    return ""
