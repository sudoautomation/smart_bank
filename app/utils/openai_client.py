# app/utils/openai_client.py — northstar-bank

from openai import OpenAI
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY, OPENAI_CHAT_MODEL, CHAT_TEMPERATURE

_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def get_chat_llm(temperature: float = CHAT_TEMPERATURE) -> ChatOpenAI:
    return ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=temperature, api_key=OPENAI_API_KEY)
