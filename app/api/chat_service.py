# app/api/chat_service.py — northstar-bank

from langchain_core.messages import AIMessage, HumanMessage

from app.orchestrator.graph import get_graph
from app.models.models import ChatRequest
from typing import AsyncGenerator
from app.utils.guardrails import guard_output


async def chat_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
        history_messages = []
        for msg in request.conversation_history:
            if msg.role == "user":
                history_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history_messages.append(AIMessage(content=msg.content))

        messages = history_messages + [HumanMessage(content=request.message)]

        initial_state = {
            "messages":          messages,
            "original_question": request.message,
            "question":          request.message,
            "retry_count":       0,
            "sources":           [],
            "sql_result":        None,
            "intent":            "chat",
        }
        async for event in get_graph().astream_events(initial_state, version="v2"):
            if (
                event["event"] == "on_chat_model_stream"
                and event.get("metadata", {}).get("langgraph_node") == "agent"
            ):
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield guard_output(chunk.content)

