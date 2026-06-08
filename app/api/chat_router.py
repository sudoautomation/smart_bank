# app/api/chat.py — northstar-bank

from fastapi import APIRouter, HTTPException

from app.api.chat_service import chat
from app.models import ChatRequest, ChatResponse, SourceReference, SQLResult
from fastapi.responses import StreamingResponse
from app.api.chat_service import chat_stream


router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """Run the agent and return a response."""
    try:
        result = chat(message=request.message)
    except Exception as exc:
        print(f"Agent error: {exc}")
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    sources = [
        SourceReference(
            source=src["source"],
            score=src["score"],
            section=src["section"],
            page_number=src["page_number"],
        )
        for src in result["sources"]
    ]

    sql_result = None
    if result["sql_result"] and result["sql_result"]["columns"]:
        sr = result["sql_result"]
        sql_result = SQLResult(
            query=sr["query"],
            columns=sr["columns"],
            rows=sr["rows"],
        )

    return ChatResponse(
        answer=result["answer"],
        intent=result["intent"],
        sources=sources,
        sql_result=sql_result,
    )

@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    async def generate():
        async for token in chat_stream(request.message):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")