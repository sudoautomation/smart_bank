# app/api/chat.py — northstar-bank

from fastapi import APIRouter, HTTPException

from app.models import ChatRequest
from fastapi.responses import StreamingResponse
from app.api.chat_service import chat_stream
from app.utils.guardrails import guard_input, GuardrailViolation


router = APIRouter()


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    # try:
    #     guard_input(request.message)
    # except GuardrailViolation as exc:
    #     raise HTTPException(status_code=400, detail=exc.message)

    async def generate():
        async for token in chat_stream(request):
            yield token

    return StreamingResponse(generate(), media_type="text/plain")